"""
Seed a SWE-bench container with what the agent needs:
test_patch (committed), AGENT.md, .swebench/ metadata, and run_*.sh scripts.

The agent's run_failing_tests.sh / run_all_tests.sh are shipped as real
files in swe_bench_utils/scripts/. They read instance-specific data from
/testbed/.swebench/ at runtime so a single static script works for every
project (django uses runtests.py, sympy uses bin/test, etc.).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

from swebench.harness.test_spec.python import (
    MAP_REPO_VERSION_TO_SPECS,
    get_test_directives,
)

from .config import get_fail_to_pass, get_pass_to_pass
from .docker_env import DockerContainer

log = logging.getLogger(__name__)

TESTBED = "/testbed"
META_DIR = "/testbed/.swebench"

SCRIPTS_DIR = Path(__file__).resolve().parent / "scripts"


# ---------------------------------------------------------------------------
# Test patch
# ---------------------------------------------------------------------------

def apply_test_patch_in_container(container: DockerContainer, test_patch: str) -> bool:
    """
    Apply the SWE-bench test_patch and commit it as HEAD.

    Why commit: a stray ``git restore`` / ``git reset`` from the agent
    would otherwise revert the failing-test additions back to base_commit.
    Committing makes the test_patch state the new HEAD so restore goes
    back TO it, and ``git diff HEAD`` captures only the agent's bug fix.
    """
    if not test_patch or not test_patch.strip():
        log.warning("  No test_patch to apply.")
        return False

    container.write_text("/testbed/.swebench_test_patch.diff", test_patch)
    code, out = container.exec(
        ["git", "apply", ".swebench_test_patch.diff"], cwd=TESTBED,
    )
    if code != 0:
        log.warning("  Test patch did not apply cleanly: %s", out.strip()[:200])
        code, out = container.exec(
            ["git", "apply", "--reject", ".swebench_test_patch.diff"], cwd=TESTBED,
        )
        if code != 0:
            log.error("  Test patch could not be applied at all.")
            return False
        log.warning("  Test patch applied with --reject.")
    else:
        log.info("  Test patch applied.")

    code, out = container.exec(
        "git add -A && git -c user.email=swebench@local -c user.name=swebench "
        "commit --no-verify -m 'swe-bench: apply test_patch'",
        cwd=TESTBED,
    )
    if code != 0:
        log.error("  Failed to commit test_patch: %s", out.strip()[:200])
        return False
    log.info("  Test patch committed (HEAD now contains failing tests).")
    return True


# ---------------------------------------------------------------------------
# Per-instance metadata
# ---------------------------------------------------------------------------

def _resolve_test_invocation(record: dict) -> tuple[str, str, str]:
    """
    Look up the canonical test invocation for this instance from swebench.

    Returns (cwd, test_cmd, test_directives_string).

    cwd is always /testbed: that's what swebench's own eval.sh does. The
    test_cmd values in swebench's MAP_REPO_VERSION_TO_SPECS already include
    any required relative-path prefix (e.g. django's ``./tests/runtests.py``
    or sympy's ``bin/test``), so they expect to be run from /testbed.
    """
    repo, version = record["repo"], record["version"]
    spec = MAP_REPO_VERSION_TO_SPECS.get(repo, {}).get(version)
    if not spec:
        raise RuntimeError(
            f"swebench has no test_cmd for {repo} v{version} "
            f"(instance {record['instance_id']})"
        )
    test_cmd = spec["test_cmd"]
    directives = get_test_directives(record)
    return "/testbed", test_cmd, " ".join(directives)


def write_metadata_in_container(container: DockerContainer, record: dict) -> None:
    """Write structured metadata + per-instance test invocation into /testbed/.swebench/."""
    container.exec(["mkdir", "-p", META_DIR])

    container.write_text(f"{META_DIR}/problem_statement.md",
                         record.get("problem_statement", ""))
    container.write_text(f"{META_DIR}/FAIL_TO_PASS.json",
                         json.dumps(get_fail_to_pass(record), indent=2))
    container.write_text(f"{META_DIR}/PASS_TO_PASS.json",
                         json.dumps(get_pass_to_pass(record), indent=2))
    container.write_text(
        f"{META_DIR}/instance_metadata.json",
        json.dumps({k: v for k, v in record.items() if k != "patch"},
                   indent=2, default=str),
    )

    hints = (record.get("hints_text") or "").strip()
    if hints:
        container.write_text(f"{META_DIR}/hints.md", hints)

    # Canonical test invocation (consumed by run_*.sh inside the container).
    cwd, test_cmd, directives = _resolve_test_invocation(record)
    container.write_text(f"{META_DIR}/test_cwd", cwd + "\n")
    container.write_text(f"{META_DIR}/test_cmd", test_cmd + "\n")
    container.write_text(f"{META_DIR}/test_directives", directives + "\n")
    log.info("  Metadata written to %s (cwd=%s, cmd=%r)",
             META_DIR, cwd, test_cmd)


# ---------------------------------------------------------------------------
# Test runner scripts
# ---------------------------------------------------------------------------

def install_test_scripts_in_container(container: DockerContainer) -> None:
    """
    Copy the static run_failing_tests.sh / run_all_tests.sh scripts into
    /testbed/. They read /testbed/.swebench/test_cmd + test_directives at
    runtime, so they're project-agnostic -- one file works for django,
    sympy, astropy, sklearn alike.
    """
    for name in ("run_failing_tests.sh", "run_all_tests.sh"):
        src = SCRIPTS_DIR / name
        if not src.is_file():
            raise RuntimeError(f"missing script: {src}")
        container.write_text(f"/testbed/{name}", src.read_text(encoding="utf-8"),
                             mode=0o755)
    log.info("  Test runner scripts installed at /testbed/run_*.sh")


# ---------------------------------------------------------------------------
# Top-level setup
# ---------------------------------------------------------------------------

def setup_container(
    container: DockerContainer,
    record: dict,
    *,
    agent_md: Optional[str] = None,
    agent_md_path: str = "/testbed/AGENT.md",
) -> None:
    """Apply test_patch, write metadata, copy test scripts, drop the prompt file.

    ``agent_md_path`` selects the in-container path for the prompt. Default
    is ``/testbed/AGENT.md`` (gemini-cli, qwen-code). Codex CLI auto-loads
    ``AGENTS.md`` (plural) from the working directory, so its runner passes
    ``/testbed/AGENTS.md`` instead.
    """
    apply_test_patch_in_container(container, record.get("test_patch", ""))
    write_metadata_in_container(container, record)
    install_test_scripts_in_container(container)
    if agent_md is not None:
        container.write_text(agent_md_path, agent_md)
