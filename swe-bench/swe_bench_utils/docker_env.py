"""
Per-instance Docker container: ``docker run -d sleep`` keepalive +
``docker exec`` for everything. Pattern from mini-swe-agent.
"""

from __future__ import annotations

import logging
import os
import shlex
import subprocess
import tempfile
import threading
import uuid
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Image-name resolution
# ---------------------------------------------------------------------------

# Docker Hub disallows ``__`` in repo names; SWE-bench's official registry
# substitutes this token.
_DOCKERHUB_DUNDER = "_1776_"

DOCKERHUB_IMAGE_BASE = "swebench/sweb.eval.x86_64"

# Default to the official DockerHub registry pinned to ``v2`` -- an
# immutable tag that gives bit-identical bytes across runs.
DEFAULT_IMAGE_BASE = DOCKERHUB_IMAGE_BASE
DEFAULT_IMAGE_TAG = "v2"


def _munge_for_registry(instance_id: str, image_base: str) -> str:
    if image_base == DOCKERHUB_IMAGE_BASE:
        return instance_id.replace("__", _DOCKERHUB_DUNDER)
    return instance_id


def instance_image_name(
    instance_id: str,
    image_base: str = DEFAULT_IMAGE_BASE,
    tag: str = DEFAULT_IMAGE_TAG,
) -> str:
    """Per-instance image name for a SWE-bench instance_id."""
    return f"{image_base}.{_munge_for_registry(instance_id, image_base)}:{tag}"


def overlay_image_name(
    instance_id: str,
    prefix: str = "gemini-eval",
    image_base: str = DEFAULT_IMAGE_BASE,
) -> str:
    """Local overlay image name (locally built, so always tagged ``:latest``)."""
    return f"{prefix}/{_munge_for_registry(instance_id, image_base)}:latest"


# ---------------------------------------------------------------------------
# Container lifecycle
# ---------------------------------------------------------------------------

class DockerContainer:
    """
    Long-lived Docker container for one SWE-bench instance.

    Use as a context manager:

        with DockerContainer(image, workdir="/testbed") as c:
            c.exec(["bash", "-lc", "ls"])
    """

    def __init__(
        self,
        image: str,
        *,
        workdir: str = "/testbed",
        name: Optional[str] = None,
        bind_mounts: Optional[dict[str, str]] = None,
        run_args: Optional[list[str]] = None,
        keepalive_seconds: int = 24 * 60 * 60,
        executable: str = "docker",
    ):
        self.image = image
        self.workdir = workdir
        self.name = name or f"swebench-{uuid.uuid4().hex[:8]}"
        self.bind_mounts = bind_mounts or {}
        self.run_args = run_args or []
        self.keepalive_seconds = keepalive_seconds
        self.executable = executable
        self.container_id: Optional[str] = None

    # -- lifecycle ----------------------------------------------------------

    def start(self) -> str:
        cmd = [
            self.executable, "run", "-d",
            "--name", self.name,
            "-w", self.workdir,
        ]
        for host_path, container_path in self.bind_mounts.items():
            cmd.extend(["-v", f"{host_path}:{container_path}"])
        cmd.extend(self.run_args)
        cmd.extend([self.image, "sleep", str(self.keepalive_seconds)])

        log.info("docker run: %s", shlex.join(cmd))
        result = subprocess.run(
            cmd, capture_output=True, text=True, check=False,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"failed to start container: {result.stderr.strip() or result.stdout.strip()}"
            )
        self.container_id = result.stdout.strip()
        log.info("started container %s (%s)", self.name, self.container_id[:12])
        return self.container_id

    def cleanup(self) -> None:
        if not self.container_id:
            return
        # Best effort; don't raise on cleanup
        subprocess.run(
            [self.executable, "rm", "-f", self.container_id],
            capture_output=True, check=False, timeout=120,
        )
        log.info("removed container %s", self.name)
        self.container_id = None

    def __enter__(self) -> "DockerContainer":
        self.start()
        return self

    def __exit__(self, *exc) -> None:
        self.cleanup()

    # Note: no __del__ — that would silently tear down containers the user
    # asked to keep (--keep-container, debugging sessions). Cleanup is
    # explicit via the context manager or .cleanup().

    # -- exec ---------------------------------------------------------------

    def exec(
        self,
        cmd: list[str] | str,
        *,
        cwd: Optional[str] = None,
        env: Optional[dict[str, str]] = None,
        timeout: Optional[int] = None,
        capture: bool = True,
        tee_path: Optional[Path] = None,
        check: bool = False,
    ) -> tuple[int, str]:
        """
        Execute a command inside the container via ``docker exec``.

        Returns (exit_code, output). If ``tee_path`` is given, output is
        also streamed to that file.
        """
        if not self.container_id:
            raise RuntimeError("container not started")

        if isinstance(cmd, str):
            inner_cmd = ["bash", "-lc", cmd]
        else:
            inner_cmd = list(cmd)

        full = [self.executable, "exec", "-w", cwd or self.workdir]
        for k, v in (env or {}).items():
            full.extend(["-e", f"{k}={v}"])
        full.append(self.container_id)
        full.extend(inner_cmd)

        log.debug("docker exec: %s", shlex.join(full))

        if tee_path:
            code, output, timed_out = self._exec_streaming(full, tee_path, timeout, capture)
        else:
            code, output, timed_out = self._exec_blocking(full, timeout, capture)

        if timed_out:
            return 124, output
        if check and code != 0:
            raise RuntimeError(f"command failed (exit {code}): {output[:500]}")
        return code, output

    def _exec_streaming(
        self,
        full: list[str],
        tee_path: Path,
        timeout: Optional[int],
        capture: bool,
    ) -> tuple[int, str, bool]:
        """
        Run ``docker exec`` and stream stdout to ``tee_path`` AND optionally
        capture it. A threading.Timer watchdog kills the process after
        ``timeout`` seconds -- crucial because the read loop blocks on
        proc.stdout, so passing ``timeout`` to ``proc.wait`` (only reached
        after the loop exits) would never fire for a hung process.
        """
        tee_path.parent.mkdir(parents=True, exist_ok=True)
        with open(tee_path, "w", encoding="utf-8") as f:
            proc = subprocess.Popen(
                full,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )

            timed_out = threading.Event()
            timer = threading.Timer(timeout, self._timeout_kill,
                                    args=(proc, timed_out)) if timeout else None
            if timer:
                timer.daemon = True
                timer.start()

            captured: list[str] = []
            try:
                if proc.stdout is None:
                    raise RuntimeError("subprocess stdout pipe was not opened")
                for line in proc.stdout:
                    f.write(line)
                    f.flush()
                    if capture:
                        captured.append(line)
                proc.wait()
            finally:
                if timer:
                    timer.cancel()

            return proc.returncode, "".join(captured), timed_out.is_set()

    def _exec_blocking(
        self,
        full: list[str],
        timeout: Optional[int],
        capture: bool,
    ) -> tuple[int, str, bool]:
        """Run ``docker exec`` and capture stdout/stderr at the end."""
        try:
            result = subprocess.run(
                full,
                capture_output=capture,
                text=True,
                timeout=timeout,
                check=False,
            )
            return (
                result.returncode,
                (result.stdout or "") + (result.stderr or ""),
                False,
            )
        except subprocess.TimeoutExpired as e:
            partial = e.stdout if isinstance(e.stdout, str) else ""
            return -1, partial or "", True

    def _timeout_kill(self, proc: subprocess.Popen, timed_out: threading.Event) -> None:
        """
        Watchdog callback. Kills the host-side ``docker exec`` proc and
        also sends SIGKILL to anything still running inside the container
        -- docker exec's signal propagation isn't 100% reliable for
        forked children of the in-container process.
        """
        timed_out.set()
        log.warning("docker exec timed out; killing process")
        try:
            proc.kill()
        except ProcessLookupError:
            pass  # Process already exited
        except Exception as e:
            log.error("Failed to kill docker exec process: %s", e)
        if self.container_id:
            try:
                # Best-effort: kill anything in the container the agent's
                # session might have spawned. ``true`` ensures nonzero exit
                # from pkill (no matching processes) doesn't propagate.
                subprocess.run(
                    [self.executable, "exec", self.container_id,
                     "bash", "-c", "pkill -9 -f gemini || true; pkill -9 -f node || true"],
                    timeout=15, capture_output=True,
                )
            except subprocess.TimeoutExpired:
                log.warning(
                    "In-container pkill timed out after 15s for container %s; "
                    "processes may still be running",
                    self.container_id[:12],
                )
            except Exception as e:
                log.error(
                    "Failed to kill in-container processes for %s: %s",
                    self.container_id[:12], e,
                )

    # -- file transfer ------------------------------------------------------

    def cp_in(self, host_path: Path, container_path: str) -> None:
        """Copy a file or directory from host into the container."""
        if not self.container_id:
            raise RuntimeError("container not started")
        cmd = [self.executable, "cp", str(host_path), f"{self.container_id}:{container_path}"]
        subprocess.run(cmd, check=True, capture_output=True, text=True)

    def write_text(self, container_path: str, content: str, mode: int = 0o644) -> None:
        """Write a text file into the container at the given path."""
        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".tmp") as f:
            f.write(content)
            tmp = Path(f.name)
        try:
            os.chmod(tmp, mode)
            # Ensure parent dir exists in container
            parent = os.path.dirname(container_path) or "/"
            self.exec(["mkdir", "-p", parent])
            self.cp_in(tmp, container_path)
        finally:
            tmp.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Image presence helpers
# ---------------------------------------------------------------------------

def image_exists(image: str, executable: str = "docker") -> bool:
    """True if the image is available locally."""
    result = subprocess.run(
        [executable, "image", "inspect", image],
        capture_output=True, check=False,
    )
    return result.returncode == 0


def pull_image(image: str, executable: str = "docker") -> None:
    """Pull an image if not present locally."""
    if image_exists(image, executable):
        log.info("image present: %s", image)
        return
    log.info("pulling image: %s", image)
    subprocess.run([executable, "pull", image], check=True)


def image_digest(image: str, executable: str = "docker") -> Optional[str]:
    """Return the RepoDigest for an image, if available."""
    result = subprocess.run(
        [executable, "image", "inspect", "--format", "{{index .RepoDigests 0}}", image],
        capture_output=True, text=True, check=False,
    )
    if result.returncode == 0 and result.stdout.strip():
        return result.stdout.strip()
    return None
