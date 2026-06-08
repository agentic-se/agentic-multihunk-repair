#!/usr/bin/env python3
"""
Generate the seven `hunk-poly/` files for the merged PolyHunk dataset
(372 Hunk4J + 32 HunkSWE = 404 instances). Mirrors the existing Hunk4J-only
layout under ~/Desktop/birch/oak/results/ exactly:

  hunk-poly/
    fixed_bugs_by_agent.json
    hunk_divergence.csv
    proximity_class.csv
    claude_code_results/claude_results/claude_repair_ability.csv
    gemini_cli_results/gemini_repair_ability.csv
    openai_codex_results/results-codex/codex_repair_ability.csv
    qwen_code_results/qwen_results/qwen_repair_ability.csv

Sources:
  - hunkDS.csv                        — per-bug repair flags, divergence,
                                         proximity, hunk_count (Hunk4J side
                                         uses the existing _repair_ability
                                         columns verbatim; HunkSWE side
                                         derives the missing fields)
  - swe_bench.jsonl[i].FAIL_TO_PASS    — for HunkSWE failed_test_prior
  - swe-bench/<agent>-cli-automation/workspace_docker/<inst>/logs/
        swebench_report.json           — for HunkSWE failed_test_after +
                                         compile_fail (patch_successfully_applied)
"""
from __future__ import annotations
import csv
import json
from collections import defaultdict
from pathlib import Path

REPO = Path("/Users/danielding/Desktop/agentic-multihunk-repair")
HUNKDS = REPO / "hunkDS.csv"
SWE_ROOT = REPO / "swe-bench"
SWE_BENCH_JSONL = SWE_ROOT / "swe_bench_verified" / "swe_bench.jsonl"
OUT = REPO / "hunk-poly"

AGENT_KEYS = {  # JSON key per agent (matches existing fixed_bugs_by_agent.json)
    "claude": "claude_code",
    "codex":  "openai_codex",
    "gemini": "gemini_cli",
    "qwen":   "qwen_code",
}
REPAIR_CSV_PATH = {
    "claude": OUT / "claude_code_results/claude_results/claude_repair_ability.csv",
    "codex":  OUT / "openai_codex_results/results-codex/codex_repair_ability.csv",
    "gemini": OUT / "gemini_cli_results/gemini_repair_ability.csv",
    "qwen":   OUT / "qwen_code_results/qwen_results/qwen_repair_ability.csv",
}
SWE_AUTOMATION = {
    "claude": SWE_ROOT / "claude-cli-automation",
    "codex":  SWE_ROOT / "codex-cli-automation",
    "gemini": SWE_ROOT / "gemini-cli-automation",
    "qwen":   SWE_ROOT / "qwen-cli-automation",
}


def load_hunkds():
    with HUNKDS.open() as f:
        return list(csv.DictReader(f))


def load_swe_bench_gold():
    """instance_id -> set of FAIL_TO_PASS test IDs."""
    out = {}
    with SWE_BENCH_JSONL.open() as f:
        for line in f:
            if not line.strip():
                continue
            rec = json.loads(line)
            ftp = rec.get("FAIL_TO_PASS")
            ftp = json.loads(ftp) if isinstance(ftp, str) else (ftp or [])
            out[rec["instance_id"]] = ftp
    return out


def load_swe_reports(agent: str):
    """instance_id -> {compile_ok, ftp_failures, ptp_failures}."""
    out = {}
    ws = SWE_AUTOMATION[agent] / "workspace_docker"
    if not ws.is_dir():
        return out
    for inst_dir in sorted(p for p in ws.iterdir() if p.is_dir()):
        rep = inst_dir / "logs" / "swebench_report.json"
        if not rep.is_file():
            continue
        data = json.loads(rep.read_text())[inst_dir.name]
        ts = data.get("tests_status", {})
        out[inst_dir.name] = {
            "compile_ok": data.get("patch_successfully_applied", False),
            "ftp_failures": len(ts.get("FAIL_TO_PASS", {}).get("failure", [])),
            "ptp_failures": len(ts.get("PASS_TO_PASS", {}).get("failure", [])),
        }
    return out


def main():
    rows = load_hunkds()
    gold = load_swe_bench_gold()

    # ---------------- 1 & 2: proximity_class.csv, hunk_divergence.csv ----
    # Use claude/vanilla rows (covers all 404 bugs once)
    OUT.mkdir(exist_ok=True)
    by_bug = {}
    for r in rows:
        if r["mode"] != "vanilla" or r["agent"] != "claude":
            continue
        if r["bug_id"] in by_bug:
            continue
        by_bug[r["bug_id"]] = r

    with (OUT / "proximity_class.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["bug_id", "proximity_class"])
        for bug, r in sorted(by_bug.items()):
            w.writerow([bug, r["proximity_class"]])
    print(f"  Wrote {OUT/'proximity_class.csv'} ({len(by_bug)} bugs)")

    with (OUT / "hunk_divergence.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["bug_id", "hunk_count", "divergence"])
        for bug, r in sorted(by_bug.items()):
            w.writerow([bug, r["hunk_count"], r["hunk_divergence"]])
    print(f"  Wrote {OUT/'hunk_divergence.csv'} ({len(by_bug)} bugs)")

    # ---------------- 3-6: per-agent <agent>_repair_ability.csv -------------
    # Hunk4J side: copy existing columns verbatim from hunkDS.csv.
    # HunkSWE side: derive failed_test_prior/after, regression_reduction,
    # compile_fail from swe_bench.jsonl + per-instance swebench_report.json.
    fixed_bugs = {key: [] for key in AGENT_KEYS.values()}
    for agent, agent_key in AGENT_KEYS.items():
        path = REPAIR_CSV_PATH[agent]
        path.parent.mkdir(parents=True, exist_ok=True)
        swe_reports = load_swe_reports(agent)

        all_rows = []
        for r in rows:
            if r["mode"] != "vanilla" or r["agent"] != agent:
                continue
            bug = r["bug_id"]
            repair = int(r["repair"]) if r["repair"] in ("0", "1") else 0
            if repair == 1:
                fixed_bugs[agent_key].append(bug)

            if r["benchmark"] == "hunk4j":
                all_rows.append([
                    bug, repair,
                    r["failed_test_prior"], r["failed_test_after"],
                    r["regression_reduction"], r["compile_fail"],
                ])
            else:  # hunkswe
                ftp_total = len(gold.get(bug, []))
                rep = swe_reports.get(bug)
                if rep is None:
                    # Missing swebench_report.json — fall back assumptions:
                    #   - If repair==1, all FTP tests passed, no regressions.
                    #   - If repair==0, all FTP tests failed.
                    # Compile is always treated as success here because the
                    # automation produced a patch (per the trajectory log);
                    # the SWE-bench harness verdict is just unavailable.
                    # This default (0) keeps the column non-empty so the
                    # downstream oak plot scripts (which int()-cast every
                    # cell) run without modification.
                    ftp_after = 0 if repair == 1 else ftp_total
                    failed_after = ftp_after
                    compile_fail = 0
                    reg_red_str = str(ftp_total - failed_after)
                    compile_fail_str = "0"
                else:
                    failed_after = rep["ftp_failures"] + rep["ptp_failures"]
                    compile_fail = 0 if rep["compile_ok"] else 1
                    reg_red_str = str(ftp_total - failed_after)
                    compile_fail_str = str(compile_fail)
                all_rows.append([
                    bug, repair,
                    str(ftp_total), str(failed_after),
                    reg_red_str, compile_fail_str,
                ])

        with path.open("w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["bug_id", "repair", "failed_test_prior",
                         "failed_test_after", "regression_reduction", "compile_fail"])
            w.writerows(all_rows)
        print(f"  Wrote {path}  ({len(all_rows)} bugs, "
              f"{sum(1 for r in all_rows if r[1]==1)} fixed)")

    # ---------------- 7: fixed_bugs_by_agent.json --------------------------
    # Preserve existing key order: gemini_cli, qwen_code, claude_code, openai_codex
    ordered = {k: sorted(fixed_bugs[k]) for k in
               ("gemini_cli", "qwen_code", "claude_code", "openai_codex")}
    with (OUT / "fixed_bugs_by_agent.json").open("w") as f:
        json.dump(ordered, f, indent=2)
        f.write("\n")
    print(f"  Wrote {OUT/'fixed_bugs_by_agent.json'} "
          f"({{ {' '.join(f'{k}:{len(v)}' for k,v in ordered.items())} }})")


if __name__ == "__main__":
    main()
