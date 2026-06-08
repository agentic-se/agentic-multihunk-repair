"""
Grade an agent's predicted patch using the official SWE-bench harness.

Produces results bit-identical to the SWE-bench leaderboard. We hand the
predicted patch off to ``swebench.harness.run_evaluation``, which runs
its own grading container, applies the patch, executes the canonical
per-instance test command, and writes ``report.json``. We parse that
report into our CSV format.

For convenience, key swebench artifacts (report.json, eval.sh,
test_output.txt) are also copied up to the per-bug logs/ directory so
they're visible without spelunking through swebench's nested layout.
"""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)


@dataclass
class GradingResult:
    instance_id: str
    resolved: bool                  # SWE-bench's canonical "is this bug fixed?" verdict
    fail_to_pass_resolved: bool     # all FTP tests now pass
    no_regressions: bool            # all PTP tests still pass
    failed_tests: list[str]         # specific tests that failed (FTP not passing + PTP regressions)
    report_path: Optional[Path]     # canonical report.json on disk
    error: Optional[str] = None     # set if grading itself failed


def grade_instance(
    instance_id: str,
    patch_text: str,
    *,
    run_id: str,
    output_dir: Path,
    instance_image_tag: str = "v2",
    namespace: str = "swebench",
    timeout: int = 1800,
    dataset_name: str = "SWE-bench/SWE-bench_Verified",
    split: str = "test",
) -> GradingResult:
    """
    Grade one instance with the official SWE-bench evaluator.

    Writes a single-entry predictions JSONL and invokes
    ``python -m swebench.harness.run_evaluation`` as a subprocess so the
    swebench package's logging / docker handling stays cleanly isolated
    from ours. Then reads the resulting report.json.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    pred_path = output_dir / "predictions.jsonl"
    pred = {
        "instance_id": instance_id,
        "model_patch": patch_text or "",
        "model_name_or_path": run_id,
    }
    pred_path.write_text(json.dumps(pred) + "\n", encoding="utf-8")

    cmd = [
        sys.executable, "-m", "swebench.harness.run_evaluation",
        "--dataset_name", dataset_name,
        "--split", split,
        "--predictions_path", str(pred_path),
        "--instance_ids", instance_id,
        "--max_workers", "1",
        "--run_id", run_id,
        "--cache_level", "instance",
        "--namespace", namespace,
        "--instance_image_tag", instance_image_tag,
        "--timeout", str(timeout),
        "--report_dir", str(output_dir),
    ]
    log.info("[grader] %s", " ".join(cmd))
    proc = subprocess.run(cmd, capture_output=True, text=True, cwd=output_dir)
    if proc.returncode != 0:
        log.error("[grader] swebench failed (exit %d): %s",
                  proc.returncode, (proc.stderr or proc.stdout)[-500:])
        return GradingResult(instance_id, False, False, False, [],
                             None, error=f"swebench exit {proc.returncode}")

    # swebench produces TWO output files:
    #   1. <output_dir>/<run_id>.<model>.json  -- aggregate summary (counts only)
    #   2. <output_dir>/logs/run_evaluation/<run_id>/<model>/<instance>/report.json
    #      -- per-instance verdict with FAIL_TO_PASS / PASS_TO_PASS breakdown
    # We need #2 for the CSV row.
    model = pred["model_name_or_path"]
    report_path = (
        output_dir / "logs" / "run_evaluation" / run_id / model / instance_id / "report.json"
    )
    if not report_path.exists():
        # Fallback: glob in case swebench changes the layout in a future version.
        candidates = list(output_dir.rglob(f"**/{instance_id}/report.json"))
        if not candidates:
            log.error("[grader] no per-instance report under %s", output_dir)
            return GradingResult(instance_id, False, False, False, [],
                                 None, error="no per-instance report produced")
        report_path = candidates[0]

    report = json.loads(report_path.read_text(encoding="utf-8"))

    # Copy the key swebench artifacts up to the logs/ directory so they
    # are visible alongside our other per-bug logs. swebench's own copies
    # remain in place (deeply nested) for full traceability.
    _surface_swebench_artifacts(report_path, output_dir.parent)

    return _parse_report(instance_id, report, report_path)


def _surface_swebench_artifacts(report_path: Path, logs_dir: Path) -> None:
    """Copy swebench's per-instance artifacts up to <logs_dir>/ for visibility."""
    src_dir = report_path.parent
    for name, dest_name in [
        ("report.json", "swebench_report.json"),
        ("eval.sh", "swebench_eval.sh"),
        ("test_output.txt", "swebench_test_output.txt"),
    ]:
        src = src_dir / name
        if src.is_file():
            try:
                shutil.copy2(src, logs_dir / dest_name)
            except OSError as e:
                log.warning("[grader] could not copy %s: %s", src, e)


def _parse_report(instance_id: str, report: dict, report_path: Path) -> GradingResult:
    """
    Translate swebench's report.json into our GradingResult shape.

    swebench's report has the structure:
        {
          "<run_id>": {
            "instance_id_to_results": {
              "<instance>": {
                "resolved": True,
                "tests_status": {
                  "FAIL_TO_PASS": {"success": [...], "failure": [...]},
                  "PASS_TO_PASS": {"success": [...], "failure": [...]},
                }
              }
            },
            "resolved_ids": [...],
            ...
          }
        }
    """
    # Find the per-instance sub-dict regardless of outer keying.
    inst_block = None
    for v in report.values() if isinstance(report, dict) else []:
        if isinstance(v, dict) and "instance_id_to_results" in v:
            inst_block = v["instance_id_to_results"].get(instance_id)
            break
    if inst_block is None and isinstance(report, dict):
        # Some swebench versions key directly on instance_id at the top level.
        inst_block = report.get(instance_id)

    if inst_block is None:
        return GradingResult(instance_id, False, False, False, [],
                             report_path, error="instance not in report")

    resolved = bool(inst_block.get("resolved", False))
    statuses = inst_block.get("tests_status", {})
    ftp = statuses.get("FAIL_TO_PASS", {})
    ptp = statuses.get("PASS_TO_PASS", {})
    ftp_failures = list(ftp.get("failure", []))
    ptp_failures = list(ptp.get("failure", []))

    return GradingResult(
        instance_id=instance_id,
        resolved=resolved,
        fail_to_pass_resolved=(len(ftp_failures) == 0 and bool(ftp.get("success"))),
        no_regressions=(len(ptp_failures) == 0),
        failed_tests=ftp_failures + ptp_failures,
        report_path=report_path,
    )
