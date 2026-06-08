#!/usr/bin/env python3
"""
Qwen Code CLI runner on SWE-bench Verified multi-hunk bugs.
Runs the agent inside a per-instance Docker container.
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import os
import shlex
import sys
import time
from pathlib import Path
from typing import Optional

# Make swe_bench_utils importable.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from swe_bench_utils.build_overlay import (
    DEFAULT_NODE_MAJOR,
    DEFAULT_QWEN_BINARY,
    DEFAULT_QWEN_NPM_PACKAGE,
    DEFAULT_QWEN_VERSION,
    build_overlay,
    collect_manifest_entry,
    write_image_manifest,
)
from swe_bench_utils.config import (
    DEFAULT_PROMPT,
    load_multihunk_bugs,
    load_swebench_records,
    render_prompt,
)
from swe_bench_utils.container_setup import setup_container
from swe_bench_utils.docker_env import (
    DEFAULT_IMAGE_BASE,
    DEFAULT_IMAGE_TAG,
    DockerContainer,
    instance_image_name,
    overlay_image_name,
)
from swe_bench_utils.grader import grade_instance
from swe_bench_utils.utils import ensure_dir, ts

log = logging.getLogger(__name__)

DEFAULT_OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# ---------------------------------------------------------------------------
# MCP plumbing constants — see _setup_mcp_in_container() below.
# Mirrors the proven-out setup from progctx-mcp-swe-bench/test_mcp_e2e.py.
# ---------------------------------------------------------------------------

# Host path to the MCP server code we cp_in into every container.
REPO_ROOT = Path(__file__).resolve().parents[2]
PROGCTX_DIR = REPO_ROOT / "progctx-mcp-swe-bench"

# In-container locations.
CONTAINER_PKG_ROOT = "/opt/progctx-mcp-swe-bench"
QWEN_SETTINGS_PATH = "/root/.qwen/settings.json"

# A dedicated conda env inside the container, independent of the bug's
# testbed env (whose Python may be 3.7-3.9 and would fail PythonSearchManager's
# PEP 604 type hints).
MCP_ENV_NAME = "mcp-e2e"
MCP_ENV_PYTHON = "3.11"
MCP_ENV_PYTHON_PATH = f"/opt/miniconda3/envs/{MCP_ENV_NAME}/bin/python"

# Per-step timeouts inside the container (seconds).
TIMEOUT_CONDA_CREATE = 300
TIMEOUT_PIP_INSTALL = 300
TIMEOUT_SMALL = 30


# ---------------------------------------------------------------------------
# Results CSV
# ---------------------------------------------------------------------------

def write_result_csv(
    results_file: Path,
    instance_id: str,
    resolved: bool,
    fail_ok: bool,
    no_reg: bool,
    failed: list[str],
    duration_s: float,
    error: Optional[str] = None,
) -> None:
    """Append one row using the canonical SWE-bench verdict shape."""
    new = not results_file.exists()
    with open(results_file, "a", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["instance_id", "resolved", "fail_to_pass_resolved",
                        "no_regressions", "failed_tests", "duration_s", "error"])
        w.writerow([
            instance_id,
            "Yes" if resolved else "No",
            "Yes" if fail_ok else "No",
            "Yes" if no_reg else "No",
            "; ".join(failed),
            f"{duration_s:.2f}",
            error or "",
        ])
    log.info("results: %s resolved=%s ftp=%s noreg=%s%s",
             instance_id, resolved, fail_ok, no_reg,
             f" ERROR={error}" if error else "")


# ---------------------------------------------------------------------------
# Per-bug processing
# ---------------------------------------------------------------------------

def _setup_mcp_in_container(container: DockerContainer, instance_id: str) -> None:
    """Plumb the MCP server inside the container so qwen can call maple_* tools.

    Mirrors the proven-out pattern from progctx-mcp-swe-bench/test_mcp_e2e.py:

      1. mkdir -p the container-side package root (docker cp doesn't create it).
      2. cp_in progctx-mcp-swe-bench/{context, mcp_server} -> CONTAINER_PKG_ROOT.
      3. conda create -y -n <MCP_ENV_NAME> python=<MCP_ENV_PYTHON>.
         A fresh env makes the test independent of the bug's testbed Python
         (which can be 3.7-3.9 for older bugs and would fail PEP 604 hints).
      4. pip install 'mcp[fastmcp]' + standalone fastmcp into that env.
      5. Write QWEN_SETTINGS_PATH (/root/.qwen/settings.json) pointing at the
         STDIO `python_analysis_server.py`. Qwen spawns the server itself; no
         port forwarding, no collision with d4j's SSE on 9900.

    Each step asserts its own rc and raises RuntimeError with a tail-of-output
    on failure -- the per-bug try/finally still cleans the container up.
    """
    log.info("[%s] MCP setup: cp_in server code", instance_id)
    rc, out = container.exec(f"mkdir -p {CONTAINER_PKG_ROOT}", timeout=TIMEOUT_SMALL)
    if rc != 0:
        raise RuntimeError(f"[{instance_id}] mkdir {CONTAINER_PKG_ROOT} failed: {out}")
    container.cp_in(PROGCTX_DIR / "context", f"{CONTAINER_PKG_ROOT}/context")
    container.cp_in(PROGCTX_DIR / "mcp_server", f"{CONTAINER_PKG_ROOT}/mcp_server")

    log.info("[%s] MCP setup: conda create -n %s python=%s",
             instance_id, MCP_ENV_NAME, MCP_ENV_PYTHON)
    rc, out = container.exec(
        f"conda create -y -n {MCP_ENV_NAME} python={MCP_ENV_PYTHON} 2>&1",
        timeout=TIMEOUT_CONDA_CREATE,
    )
    if rc != 0:
        raise RuntimeError(
            f"[{instance_id}] conda create failed (rc={rc}). Last 1000 chars:\n"
            f"{out[-1000:]}"
        )

    log.info("[%s] MCP setup: pip install 'mcp[fastmcp]' fastmcp", instance_id)
    rc, out = container.exec(
        f"conda run -n {MCP_ENV_NAME} pip install --quiet "
        f"'mcp[fastmcp]' fastmcp 2>&1",
        timeout=TIMEOUT_PIP_INSTALL,
    )
    if rc != 0:
        raise RuntimeError(
            f"[{instance_id}] pip install failed (rc={rc}). Last 1000 chars:\n"
            f"{out[-1000:]}"
        )

    log.info("[%s] MCP setup: write %s", instance_id, QWEN_SETTINGS_PATH)
    settings = {
        "mcpServers": {
            "python-analysis-server": {
                "command": MCP_ENV_PYTHON_PATH,
                "args": [f"{CONTAINER_PKG_ROOT}/mcp_server/python_analysis_server.py"],
                "env": {
                    "PYTHON_PROJECT_PATH": "/testbed",
                    "PYTHONPATH": CONTAINER_PKG_ROOT,
                },
                "timeout": 30000,
            }
        }
    }
    rc, out = container.exec(
        f"mkdir -p {os.path.dirname(QWEN_SETTINGS_PATH)}",
        timeout=TIMEOUT_SMALL,
    )
    if rc != 0:
        raise RuntimeError(
            f"[{instance_id}] mkdir {os.path.dirname(QWEN_SETTINGS_PATH)} "
            f"failed: {out}"
        )
    container.write_text(QWEN_SETTINGS_PATH, json.dumps(settings, indent=2))
    log.info("[%s] MCP setup: done", instance_id)


def _build_qwen_cmd(
    model: str,
    trajectory_path: str,
    telemetry_path: str,
    prompt: str,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
) -> str:
    """Construct the docker-exec'd qwen invocation as a shell string."""
    # qwen-code 0.15.6: The ordered tool-call trace comes from the --telemetry*
    # family (OTel local-file exporter); the agent's final chat output is
    # captured as raw stdout via shell redirection. --sandbox is dropped:
    # we already run inside a per-instance container, so there's no benefit
    # to nested sandboxing.
    #
    # IMPORTANT: Qwen CLI does NOT read OPENAI_API_KEY from environment
    # variables. Credentials MUST be passed via --openai-api-key and
    # --openai-base-url CLI flags.
    #
    # NOTE: We pass the prompt content directly via -p instead of asking the
    # agent to read AGENT.md, because early versions of Qwen CLI got stuck
    # in reasoning loops when asked to read files.
    parts = [
        "qwen",
        "--model", shlex.quote(model),
    ]

    # Add API credentials as CLI flags (required for Qwen 0.15.6)
    # Note: --auth-type is required in 0.15.6+ to specify authentication method
    if api_key:
        parts.extend([
            "--auth-type", "openai",
            "--openai-api-key", shlex.quote(api_key),
        ])
    if base_url:
        parts.extend(["--openai-base-url", shlex.quote(base_url)])

    parts.extend([
        "--yolo",
        "--telemetry",
        "--telemetry-target=local",
        "--telemetry-otlp-endpoint=",
        "--telemetry-log-prompts",
        f"--telemetry-outfile={shlex.quote(telemetry_path)}",
        "-p", shlex.quote(prompt),
        ">", shlex.quote(trajectory_path),
    ])
    return " ".join(parts)


def process_bug(
    instance_id: str,
    record: dict,
    args: argparse.Namespace,
    *,
    api_key: Optional[str],
    results_file: Path,
    manifest_dict: dict[str, dict],
) -> None:
    log.info("=== %s ===", instance_id)

    # 1. Ensure overlay image exists.
    base = instance_image_name(instance_id, image_base=args.image_base, tag=args.image_tag)
    overlay = overlay_image_name(instance_id, prefix=args.overlay_prefix,
                                 image_base=args.image_base)
    if not args.no_build:
        overlay = build_overlay(
            instance_id,
            image_base=args.image_base,
            image_tag=args.image_tag,
            overlay_prefix=args.overlay_prefix,
            node_major=args.node_major,
            cli_npm_package=DEFAULT_QWEN_NPM_PACKAGE,
            cli_version=args.qwen_version,
            cli_binary=DEFAULT_QWEN_BINARY,
        )
    manifest_dict[instance_id] = collect_manifest_entry(
        instance_id, base, overlay,
        node_major=args.node_major,
        cli_npm_package=DEFAULT_QWEN_NPM_PACKAGE,
        cli_version=args.qwen_version,
    )

    # 2. Per-bug host paths.
    workspace = Path(args.workspace).resolve()
    bug_dir = ensure_dir(workspace / instance_id)
    logs_dir = ensure_dir(bug_dir / "logs")
    agent_logs_mount = ensure_dir(bug_dir / "agent_logs")
    trajectory = logs_dir / f"qwen-trajectory-{ts()}.json"
    telemetry = logs_dir / f"qwen-telemetry-{ts()}.json"
    console_log = logs_dir / f"run-{ts()}.log"

    # 3. Container.
    container = DockerContainer(
        overlay,
        workdir="/testbed",
        name=f"swebench-qwen-{instance_id.replace('__', '-')[:35]}-{os.getpid()}",
        bind_mounts={str(agent_logs_mount): "/agent_logs"},
        keepalive_seconds=args.duration_min * 60 + 1800,
    )

    start = time.monotonic()
    try:
        container.start()

        # 4. Seed test_patch + AGENT.md + scripts.
        prompt_template = (Path(args.base_prompt).resolve()
                           if args.base_prompt else DEFAULT_PROMPT)
        agent_prompt = render_prompt(prompt_template, record)
        setup_container(container, record, agent_md=agent_prompt)

        # 4b. Plumb the MCP server into the container so qwen can resolve
        # the maple_* tools listed in prompt_mcp.md.
        _setup_mcp_in_container(container, instance_id)

        # 5. Run agent inside the container. Qwen CLI 0.0.11 requires API
        # credentials to be passed via --openai-api-key and --openai-base-url
        # flags (NOT environment variables). We also pass the prompt content
        # directly via -p instead of asking the agent to read AGENT.md, because
        # Qwen CLI gets stuck in reasoning loops when asked to read files.
        env = {"NO_COLOR": "1"}

        qwen_cmd = _build_qwen_cmd(
            args.model,
            f"/agent_logs/{trajectory.name}",
            f"/agent_logs/{telemetry.name}",
            prompt=agent_prompt,
            api_key=api_key,
            base_url=args.openai_base_url if api_key else None,
        )
        log.info("[%s] qwen command: %s", instance_id, qwen_cmd[:200] + "..." if len(qwen_cmd) > 200 else qwen_cmd)
        log.info("[%s] launching Qwen Code (timeout %d min)", instance_id, args.duration_min)
        code, _ = container.exec(
            qwen_cmd, cwd="/testbed", env=env,
            timeout=args.duration_min * 60, tee_path=console_log,
        )
        log.info("[%s] qwen exit code %d", instance_id, code)

        # Mirror trajectory + telemetry from the bind-mount (no-op if already there).
        for f in (trajectory, telemetry):
            src = agent_logs_mount / f.name
            if src.exists() and not f.exists():
                f.write_bytes(src.read_bytes())

        # 6. Capture patch (vs HEAD = test_patch commit; agent's bug fix only).
        _, diff = container.exec(
            ["git", "diff", "--no-ext-diff", "--binary", "HEAD"],
            cwd="/testbed", timeout=120,
        )
        patch_path = logs_dir / f"patch-{ts()}.diff"
        patch_path.write_text(diff or "# No tracked changes detected\n", encoding="utf-8")
        log.info("[%s] patch saved -> %s (%d bytes)",
                 instance_id, patch_path, patch_path.stat().st_size)

        # 7. Graded validation via the official SWE-bench evaluator.
        result = grade_instance(
            instance_id, diff,
            run_id=f"qwen-{args.run_id_suffix}",
            output_dir=ensure_dir(logs_dir / "swebench_grader"),
            instance_image_tag=args.image_tag,
        )
        write_result_csv(
            results_file, instance_id,
            resolved=result.resolved,
            fail_ok=result.fail_to_pass_resolved,
            no_reg=result.no_regressions,
            failed=result.failed_tests,
            duration_s=time.monotonic() - start,
            error=result.error,
        )

    except Exception as e:
        log.exception("[%s] error: %s", instance_id, e)
        write_result_csv(results_file, instance_id, False, False, False,
                         [f"ERROR: {e}"], time.monotonic() - start, error=str(e))
    finally:
        if args.keep_container:
            log.info("[%s] --keep-container set; %s left running",
                     instance_id, container.name)
        else:
            container.cleanup()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def _read_api_key(env_file: Optional[Path]) -> Optional[str]:
    """OPENROUTER_API_KEY (preferred) or OPENAI_API_KEY from env, else .env."""
    for var in ("OPENROUTER_API_KEY", "OPENAI_API_KEY"):
        if (key := os.environ.get(var)):
            return key
    if env_file and env_file.is_file():
        prefixes = ("OPENROUTER_API_KEY=", "OPENAI_API_KEY=")
        for line in env_file.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            for p in prefixes:
                if stripped.startswith(p):
                    return stripped[len(p):].strip().strip('"').strip("'")
    return None


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description="Qwen Code CLI runner on SWE-bench Verified multi-hunk bugs "
                    "(per-instance Docker isolation).",
    )
    ap.add_argument("--model", default="qwen/qwen3-coder-flash",
                    help="Model name as recognized by the OpenAI-compatible "
                         "endpoint (default: qwen3-coder-flash via OpenRouter)")
    ap.add_argument("--openai-base-url", default=DEFAULT_OPENROUTER_BASE_URL,
                    help=f"OpenAI-compatible API endpoint "
                         f"(default {DEFAULT_OPENROUTER_BASE_URL})")
    ap.add_argument("--workspace", default="./workspace_docker",
                    help="Host directory for per-bug logs / patches")
    ap.add_argument("--base-prompt", default="./prompt_mcp.md")
    ap.add_argument("--env-file", default="./.env")
    ap.add_argument("--image-base", default=DEFAULT_IMAGE_BASE,
                    help="SWE-bench instance image registry "
                         "(default: official DockerHub)")
    ap.add_argument("--image-tag", default=DEFAULT_IMAGE_TAG,
                    help=f"Tag on the instance image registry "
                         f"(default {DEFAULT_IMAGE_TAG} -- immutable on DockerHub)")
    ap.add_argument("--overlay-prefix", default="qwen-eval")
    ap.add_argument("--node-major", default=DEFAULT_NODE_MAJOR)
    ap.add_argument("--qwen-version", default=DEFAULT_QWEN_VERSION,
                    help=f"npm spec for {DEFAULT_QWEN_NPM_PACKAGE} "
                         f"(default {DEFAULT_QWEN_VERSION})")
    ap.add_argument("--no-build", action="store_true",
                    help="Skip overlay build; require pre-built images")
    ap.add_argument("--keep-container", action="store_true")
    ap.add_argument("--duration-min", type=int, default=30)
    ap.add_argument("--results-base", default="./results")
    ap.add_argument("--results-tag", default="qwen_mcp",
                    help="Tag for results CSV filename (test_results_model_<tag>.csv)")
    ap.add_argument("--only", nargs="*", default=None)
    ap.add_argument("--start-from", default=None)
    ap.add_argument("--processed-json", default="./config/processed_qwen_mcp.json")
    ap.add_argument("--manifest", default="./image_manifest.json")
    ap.add_argument("--run-id-suffix", default="run1",
                    help="Tag passed to swebench's run_evaluation as run_id "
                         "(used in its log/report file names)")
    return ap.parse_args()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = parse_args()

    results_file = ensure_dir(Path(args.results_base).resolve()) / f"test_results_model_{args.results_tag}.csv"
    api_key = _read_api_key(Path(args.env_file).resolve() if args.env_file else None)
    if not api_key:
        raise RuntimeError(
            "Neither OPENROUTER_API_KEY nor OPENAI_API_KEY found in "
            "environment or .env file -- qwen-code cannot authenticate. "
            "Set one before running."
        )

    processed_path = Path(args.processed_json).resolve()
    ensure_dir(processed_path.parent)
    processed = (set(json.loads(processed_path.read_text())) if processed_path.exists() else set())

    multihunk = load_multihunk_bugs()
    records = load_swebench_records(set(multihunk))
    if missing := set(multihunk) - set(records):
        log.error("Missing SWE-bench records for: %s", sorted(missing))
        sys.exit(1)

    ids = list(multihunk)
    if args.only:
        ids = [i for i in ids if i in set(args.only)]
    if args.start_from in ids:
        ids = ids[ids.index(args.start_from):]
    to_run = [i for i in ids if i not in processed]

    log.info("Total: %d  Processed: %d  Remaining: %d",
             len(ids), len(processed), len(to_run))

    manifest_path = Path(args.manifest).resolve()
    # Merge with existing manifest so reruns with --only/--start-from
    # don't drop entries from prior runs.
    if manifest_path.exists():
        existing = json.loads(manifest_path.read_text())
        manifest_dict: dict[str, dict] = {e["instance_id"]: e for e in existing}
    else:
        manifest_dict = {}
    for iid in to_run:
        try:
            process_bug(
                iid, records[iid], args,
                api_key=api_key,
                results_file=results_file,
                manifest_dict=manifest_dict,
            )
            processed.add(iid)
            processed_path.write_text(json.dumps(sorted(processed), indent=2))
            write_image_manifest(manifest_path, list(manifest_dict.values()))
        except KeyboardInterrupt:
            log.info("interrupted by user")
            break

    log.info("Manifest written: %s", manifest_path)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[!] Interrupted", file=sys.stderr)
        sys.exit(130)
