"""End-to-end test: run the MCP server inside the SWE-bench Docker container
for astropy__astropy-13033 and verify maple_* tools via the STDIO transport.

Designed to be debuggable when something goes wrong:

  - Every phase emits a clearly-labelled progress marker through `log`.
  - Each `docker exec` step asserts its own exit code and dumps the trailing
    chunk of output on failure (no truncated 'rc=1' surprises).
  - On failure, the test dumps the in-container conda env list + the relevant
    env's `pip list` so the user can see what was actually installed.
  - Set MCP_E2E_KEEP_CONTAINER=1 to leave the container alive after a failure
    for post-mortem inspection (`docker exec -it <name> bash`).
  - The in-container runner script writes per-step progress to stderr (NOT
    stdout, which is the MCP protocol channel) and exits with distinct codes
    per failure mode (2 = bad setup, 3 = list_tools, 4 = find_class,
    5 = repo_structure, 6 = extract_class_skeleton).

What this test exercises:

  1. Pull/use the SWE-bench instance image for astropy__astropy-13033.
  2. Start a container; verify miniconda is present.
  3. Create a fresh conda env `mcp-e2e` with Python 3.11 inside the container
     (the SWE-bench testbed env's Python may be 3.7-3.9 for older bugs and
     would fail to parse PythonSearchManager's PEP 604 type hints).
  4. Install BOTH `mcp[fastmcp]` AND the standalone `fastmcp` package into
     that env. Defensive against version skew with d4j's setup.
  5. Verify the mcp imports actually resolve.
  6. cp_in progctx-mcp-swe-bench/context/ and mcp_server/ into the container
     and verify the copy.
  7. Drop the in-container runner script and execute it via `conda run`.
  8. The runner spawns python_analysis_server.py (STDIO), connects with the
     MCP client, runs list_tools (asserts 9 maple_* present), and calls
     maple_find_class, maple_repo_structure, and maple_extract_class_skeleton.

The test is auto-skipped at module load when:

  - `docker ps` fails (Docker isn't running).
  - `swe_bench_utils` isn't importable (i.e. the swe-bench-eval env isn't
    active).

Run from progctx-mcp-swe-bench/:

    python -m pytest test_mcp_e2e.py -v -s

The `-s` flag is recommended so the progress log streams live to the
terminal during the ~2-10 min run.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SWE_BENCH_INSTANCE = "astropy__astropy-13033"

HERE = Path(__file__).resolve().parent              # progctx-mcp-swe-bench/
REPO_ROOT = HERE.parent

CONTAINER_PKG_ROOT = "/opt/progctx-mcp-swe-bench"
RUNNER_HOST_PATH = Path(__file__).resolve().parent / "mcp_e2e_runner.py"
RUNNER_CONTAINER_PATH = "/tmp/run_mcp_e2e.py"

# A fresh conda env inside the container — gives us Python 3.10+ regardless
# of what the bug's testbed env pins.
MCP_ENV_NAME = "mcp-e2e"
MCP_ENV_PYTHON = "3.11"

# Per-step timeouts (seconds). Generous on the heavy ones because the first
# run pulls a ~5 GB image and rebuilds astropy's index.
TIMEOUT_DOCKER_PULL = 1200
TIMEOUT_CONDA_CREATE = 300
TIMEOUT_PIP_INSTALL = 300
TIMEOUT_RUNNER = 600
TIMEOUT_SMALL = 30

# Debugging — leave the container alive after the test for `docker exec`.
KEEP_CONTAINER = bool(os.environ.get("MCP_E2E_KEEP_CONTAINER"))


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

log = logging.getLogger("mcp_e2e")
if not log.handlers:
    log.setLevel(logging.INFO)
    h = logging.StreamHandler(sys.stderr)
    h.setFormatter(logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    ))
    log.addHandler(h)
    log.propagate = False


def _step(label: str) -> None:
    log.info("=" * 72)
    log.info(label)
    log.info("=" * 72)


# ---------------------------------------------------------------------------
# Module-level skip guards
# ---------------------------------------------------------------------------

def _docker_available() -> bool:
    if shutil.which("docker") is None:
        return False
    try:
        subprocess.run(
            ["docker", "ps"], check=True, capture_output=True, timeout=10
        )
        return True
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired,
            FileNotFoundError):
        return False


if not _docker_available():
    pytest.skip(
        "Docker is not available or `docker ps` failed. "
        "Start Docker Desktop and try again.",
        allow_module_level=True,
    )

sys.path.insert(0, str(REPO_ROOT / "swe-bench"))
try:
    from swe_bench_utils.docker_env import DockerContainer, instance_image_name
except ImportError as e:                            # pragma: no cover
    pytest.skip(
        f"swe_bench_utils is not importable from {REPO_ROOT}/swe-bench: {e}. "
        f"Activate the swe-bench-eval conda env first.",
        allow_module_level=True,
    )


# The runner that actually exercises the MCP server lives in a sibling .py
# file so it gets normal syntax highlighting / IDE support. It's NOT meant
# to run on the host (the host's Python doesn't have `mcp[fastmcp]`); the
# test cp_in's it into the container and runs it there via `conda run`.
# See mcp_e2e_runner.py for the runner source.


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _exec_or_fail(
    container: DockerContainer,
    cmd: str,
    *,
    timeout: int,
    label: str,
) -> str:
    """Run `cmd` in the container; pytest.fail with diagnostics on non-zero rc."""
    rc, out = container.exec(cmd, timeout=timeout)
    if rc != 0:
        _dump_diagnostics(container, f"{label} failed (rc={rc})", out)
        pytest.fail(f"{label} failed inside container (rc={rc})")
    return out


def _dump_diagnostics(
    container: DockerContainer, headline: str, output: str
) -> None:
    """Best-effort diagnostic dump on failure — env list + pip list + tail of output."""
    log.error("=" * 72)
    log.error(f"DIAGNOSTICS: {headline}")
    log.error("=" * 72)
    log.error("--- command output (last 2000 chars) ---")
    log.error(output[-2000:] if output else "(no output)")
    try:
        _, env_list = container.exec("conda env list", timeout=TIMEOUT_SMALL)
        log.error("--- conda env list ---")
        log.error(env_list)
    except Exception:                                # pragma: no cover
        pass
    try:
        _, pip_list = container.exec(
            f"conda run -n {MCP_ENV_NAME} pip list 2>&1",
            timeout=TIMEOUT_SMALL,
        )
        log.error(f"--- pip list in {MCP_ENV_NAME} (tail) ---")
        log.error(pip_list[-1500:])
    except Exception:                                # pragma: no cover
        pass


# ---------------------------------------------------------------------------
# The test
# ---------------------------------------------------------------------------

def test_mcp_e2e_in_swebench_docker():
    """Boot the SWE-bench container, install MCP into a fresh Py 3.11 env,
    spawn the MCP server via STDIO, verify maple_* tools end to end."""
    image = instance_image_name(SWE_BENCH_INSTANCE)
    container_name = f"swebench-mcp-e2e-{os.getpid()}"

    _step(f"image: {image}")
    log.info(f"docker pull {image} (timeout {TIMEOUT_DOCKER_PULL}s)...")
    pull = subprocess.run(
        ["docker", "pull", image],
        check=False, timeout=TIMEOUT_DOCKER_PULL,
        capture_output=True, text=True,
    )
    if pull.returncode != 0:
        log.error(f"docker pull stderr:\n{pull.stderr[-1500:]}")
        pytest.fail(f"`docker pull {image}` failed (rc={pull.returncode})")
    log.info("  pulled")

    container = DockerContainer(
        image=image, workdir="/testbed", name=container_name,
    )

    _step(f"start container: {container_name}")
    container.start()
    log.info(f"  started: {container.container_id[:12]}")

    try:
        _step("verify conda is present")
        out = _exec_or_fail(
            container, "conda --version",
            timeout=TIMEOUT_SMALL, label="conda --version",
        )
        log.info(f"  {out.strip()}")

        _step(f"create env {MCP_ENV_NAME} (python={MCP_ENV_PYTHON})")
        _exec_or_fail(
            container,
            f"conda create -y -n {MCP_ENV_NAME} python={MCP_ENV_PYTHON} 2>&1",
            timeout=TIMEOUT_CONDA_CREATE,
            label=f"conda create {MCP_ENV_NAME}",
        )
        out = _exec_or_fail(
            container,
            f"conda run -n {MCP_ENV_NAME} python --version",
            timeout=TIMEOUT_SMALL,
            label=f"conda run -n {MCP_ENV_NAME} python --version",
        )
        assert f"Python {MCP_ENV_PYTHON}" in out, (
            f"unexpected python version: {out.strip()!r}"
        )
        log.info(f"  env python: {out.strip()}")

        _step("install mcp[fastmcp] + standalone fastmcp into env")
        _exec_or_fail(
            container,
            f"conda run -n {MCP_ENV_NAME} pip install --quiet "
            f"'mcp[fastmcp]' fastmcp 2>&1",
            timeout=TIMEOUT_PIP_INSTALL,
            label="pip install 'mcp[fastmcp]' fastmcp",
        )

        _step("verify mcp imports resolve")
        out = _exec_or_fail(
            container,
            f"conda run -n {MCP_ENV_NAME} python -c "
            f"\"import mcp, mcp.server.fastmcp, mcp.client.stdio; "
            f"print('mcp', getattr(mcp, '__version__', 'unknown'))\" 2>&1",
            timeout=TIMEOUT_SMALL,
            label="mcp import smoke test",
        )
        log.info(f"  {out.strip()}")

        _step("copy server code into container")
        # docker cp does not create intermediate directories, so create the
        # parent path first.
        _exec_or_fail(
            container, f"mkdir -p {CONTAINER_PKG_ROOT}",
            timeout=TIMEOUT_SMALL,
            label=f"mkdir -p {CONTAINER_PKG_ROOT}",
        )
        container.cp_in(HERE / "context", f"{CONTAINER_PKG_ROOT}/context")
        container.cp_in(HERE / "mcp_server", f"{CONTAINER_PKG_ROOT}/mcp_server")
        out = _exec_or_fail(
            container, f"ls {CONTAINER_PKG_ROOT}",
            timeout=TIMEOUT_SMALL,
            label="ls /opt/progctx-mcp-swe-bench",
        )
        for needed in ("context", "mcp_server"):
            assert needed in out, (
                f"cp_in verification failed: '{needed}' missing from {out!r}"
            )
        log.info(f"  {out.strip()}")

        _step(f"cp_in runner: {RUNNER_HOST_PATH.name} -> {RUNNER_CONTAINER_PATH}")
        container.cp_in(RUNNER_HOST_PATH, RUNNER_CONTAINER_PATH)

        _step(f"execute runner (timeout {TIMEOUT_RUNNER}s)")
        rc, out = container.exec(
            f"conda run -n {MCP_ENV_NAME} python {RUNNER_CONTAINER_PATH} 2>&1",
            timeout=TIMEOUT_RUNNER,
        )

        if rc != 0 or "ALL_PASSED" not in out:
            _dump_diagnostics(container, f"runner failed (rc={rc})", out)
            log.error("--- full runner output ---")
            log.error(out)
            pytest.fail(
                f"e2e runner failed (rc={rc}); see diagnostics above"
            )

        _step("ALL_PASSED")
        log.info("--- runner output ---")
        log.info(out)

    finally:
        if KEEP_CONTAINER:
            log.warning(
                f"MCP_E2E_KEEP_CONTAINER=1 — leaving container "
                f"'{container_name}' alive. Clean up manually:"
            )
            log.warning(f"  docker exec -it {container_name} bash")
            log.warning(f"  docker rm -f {container_name}")
        else:
            container.cleanup()
            log.info(f"removed container '{container_name}'")
