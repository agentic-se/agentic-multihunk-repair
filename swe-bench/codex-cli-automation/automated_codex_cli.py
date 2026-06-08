#!/usr/bin/env python3
"""
OpenAI Codex CLI runner on SWE-bench Verified multi-hunk bugs.
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
    DEFAULT_CODEX_BINARY,
    DEFAULT_CODEX_MODEL,
    DEFAULT_CODEX_NPM_PACKAGE,
    DEFAULT_CODEX_VERSION,
    DEFAULT_NODE_MAJOR,
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

def _build_codex_cmd(
    model: str,
    trajectory_path: str,
    last_message_path: str,
) -> str:
    parts = [
        "codex",
        "exec",
        "--model", shlex.quote(model),
        "--dangerously-bypass-approvals-and-sandbox",
        "--json",
        "--output-last-message", shlex.quote(last_message_path),
        "'Read and execute the instructions listed in AGENTS.md.'",
        ">", shlex.quote(trajectory_path),
    ]
    return " ".join(parts)


def _mirror_codex_session(agent_logs_mount: Path, logs_dir: Path) -> None:
    """Copy codex session JSONL files from the bind mount into logs_dir.

    With CODEX_HOME=/agent_logs/codex_home, codex writes its session log to
    <CODEX_HOME>/sessions/<date>/<id>.jsonl inside the container, which
    appears on the host at <agent_logs_mount>/codex_home/sessions/.../<id>.jsonl
    via the bind mount. Mirror those into logs_dir/ for easy access alongside
    the trajectory and last-message files.
    """
    sessions_root = agent_logs_mount / "codex_home" / "sessions"
    if not sessions_root.exists():
        log.warning("  no codex session dir found at %s", sessions_root)
        return
    for src in sessions_root.rglob("*.jsonl"):
        dst = logs_dir / f"codex-session-{src.name}"
        if dst.exists():
            continue
        dst.write_bytes(src.read_bytes())
        log.info("  copied codex session log -> %s", dst.name)


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
            cli_npm_package=DEFAULT_CODEX_NPM_PACKAGE,
            cli_version=args.codex_version,
            cli_binary=DEFAULT_CODEX_BINARY,
        )
    manifest_dict[instance_id] = collect_manifest_entry(
        instance_id, base, overlay,
        node_major=args.node_major,
        cli_npm_package=DEFAULT_CODEX_NPM_PACKAGE,
        cli_version=args.codex_version,
    )
    # Codex's underlying LLM choice is part of the reproducibility receipt
    # too; the generic manifest schema doesn't carry it, so stash it inline.
    manifest_dict[instance_id]["model"] = args.model

    # 2. Per-bug host paths.
    workspace = Path(args.workspace).resolve()
    bug_dir = ensure_dir(workspace / instance_id)
    logs_dir = ensure_dir(bug_dir / "logs")
    agent_logs_mount = ensure_dir(bug_dir / "agent_logs")
    trajectory = logs_dir / f"codex-trajectory-{ts()}.jsonl"
    last_message = logs_dir / f"codex-last-message-{ts()}.txt"
    console_log = logs_dir / f"run-{ts()}.log"

    # 3. Container.
    container = DockerContainer(
        overlay,
        workdir="/testbed",
        name=f"swebench-codex-{instance_id.replace('__', '-')[:34]}-{os.getpid()}",
        bind_mounts={str(agent_logs_mount): "/agent_logs"},
        keepalive_seconds=args.duration_min * 60 + 1800,
    )

    start = time.monotonic()
    try:
        container.start()

        # 4. Seed test_patch + AGENTS.md + scripts. Codex auto-loads
        # AGENTS.md (plural) from the working directory.
        prompt_template = (Path(args.base_prompt).resolve()
                           if args.base_prompt else DEFAULT_PROMPT)
        setup_container(
            container, record,
            agent_md=render_prompt(prompt_template, record),
            agent_md_path="/testbed/AGENTS.md",
        )

        # 5. Run agent inside the container. Codex reads OPENAI_API_KEY
        # for API-key auth; CODEX_HOME redirects ~/.codex into the bind
        # mount so we can capture the session JSONL after the run.
        env = {
            "NO_COLOR": "1",
            "CODEX_HOME": "/agent_logs/codex_home",
        }
        if api_key:
            env["OPENAI_API_KEY"] = api_key

        codex_cmd = _build_codex_cmd(
            args.model,
            f"/agent_logs/{trajectory.name}",
            f"/agent_logs/{last_message.name}",
        )
        log.info("[%s] launching Codex (timeout %d min)", instance_id, args.duration_min)
        container.exec(["mkdir", "-p", "/agent_logs/codex_home"])
        code, _ = container.exec(
            codex_cmd, cwd="/testbed", env=env,
            timeout=args.duration_min * 60, tee_path=console_log,
        )
        log.info("[%s] codex exit code %d", instance_id, code)

        # Mirror trajectory + last-message + session logs from the bind mount.
        for f in (trajectory, last_message):
            src = agent_logs_mount / f.name
            if src.exists() and not f.exists():
                f.write_bytes(src.read_bytes())
        _mirror_codex_session(agent_logs_mount, logs_dir)

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
            run_id=f"codex-{args.run_id_suffix}",
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
    """OPENAI_API_KEY from env, else the .env file."""
    if (key := os.environ.get("OPENAI_API_KEY")):
        return key
    if env_file and env_file.is_file():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped.startswith("OPENAI_API_KEY="):
                return stripped[len("OPENAI_API_KEY="):].strip().strip('"').strip("'")
    return None


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description="Codex CLI runner on SWE-bench Verified multi-hunk bugs "
                    "(per-instance Docker isolation).",
    )
    ap.add_argument("--model", default=DEFAULT_CODEX_MODEL,
                    help=f"Underlying LLM passed to `codex -m`. Default "
                         f"({DEFAULT_CODEX_MODEL}) matches codex "
                         f"{DEFAULT_CODEX_VERSION}'s built-in default; we "
                         f"pass it explicitly so the manifest records it.")
    ap.add_argument("--workspace", default="./workspace_docker",
                    help="Host directory for per-bug logs / patches")
    ap.add_argument("--base-prompt", default="../swe_bench_utils/prompt.md")
    ap.add_argument("--env-file", default="./.env")
    ap.add_argument("--image-base", default=DEFAULT_IMAGE_BASE,
                    help="SWE-bench instance image registry "
                         "(default: official DockerHub)")
    ap.add_argument("--image-tag", default=DEFAULT_IMAGE_TAG,
                    help=f"Tag on the instance image registry "
                         f"(default {DEFAULT_IMAGE_TAG} -- immutable on DockerHub)")
    ap.add_argument("--overlay-prefix", default="codex-eval")
    ap.add_argument("--node-major", default=DEFAULT_NODE_MAJOR)
    ap.add_argument("--codex-version", default=DEFAULT_CODEX_VERSION,
                    help=f"npm spec for {DEFAULT_CODEX_NPM_PACKAGE} "
                         f"(default {DEFAULT_CODEX_VERSION})")
    ap.add_argument("--no-build", action="store_true",
                    help="Skip overlay build; require pre-built images")
    ap.add_argument("--keep-container", action="store_true")
    ap.add_argument("--duration-min", type=int, default=30)
    ap.add_argument("--results-base", default="./results")
    ap.add_argument("--results-tag", default="codex",
                    help="Tag for results CSV filename (test_results_model_<tag>.csv)")
    ap.add_argument("--only", nargs="*", default=None)
    ap.add_argument("--start-from", default=None)
    ap.add_argument("--processed-json", default="./config/processed_codex.json")
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
            "OPENAI_API_KEY not found in environment or .env file -- "
            "codex cannot authenticate. Set it before running."
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
