#!/usr/bin/env python3
"""
Builds hunkDS.csv: a long-format unified dataset of Hunk4J (Defects4J) +
HunkSWE (SWE-bench Verified) bug-instances across agents and modes.

One row per (bug_id, agent, mode). Sources are existing CSVs/JSONs — no new
analysis is performed except deriving hunkswe `localization` from the
overlap of the agent's emitted patch files vs. the SWE-bench gold patch
files (per user direction).
"""
import csv
import json
import re
from collections import defaultdict
from pathlib import Path

HOME = Path.home()
D4J_ROOT = HOME / "Desktop" / "birch" / "oak" / "results"
SWE_ROOT = Path("/Users/danielding/Desktop/agentic-multihunk-repair/swe-bench")
OUT_PATH = Path("/Users/danielding/Desktop/agentic-multihunk-repair/hunkDS.csv")

HEADERS = [
    "bug_id", "benchmark", "project", "agent", "mode",
    "hunk_count", "hunk_divergence", "proximity_class",
    "localization", "repair", "compile_fail",
    "failed_test_prior", "failed_test_after", "regression_reduction",
    "fail_to_pass_resolved", "no_regressions", "failed_tests",
    "num_expected_edits", "correct_edits", "ote", "missed_edits",
    "total_input_tokens", "total_output_tokens",
    "cache_creation_tokens", "cache_read_tokens", "time_duration_s",
]


# ---------- helpers ----------

def norm_d4j(bug_id: str) -> str:
    """Normalize Defects4J bug ids to canonical project-camelCase + underscore + number.

    Defects4J project names use mixed casing: most are single-word
    (``Chart``, ``Cli``, ``Closure``, ``Math``, ...) but a handful are
    camelCase (``JacksonCore``, ``JacksonDatabind``, ``JacksonXml``,
    ``JxPath``). Upstream sources disagree on casing (some lowercase
    everything, some uppercase only the first letter, some preserve
    camelCase), so we normalize via an explicit canonical table for the
    multi-word projects and ``.capitalize()`` for the rest.
    """
    # Canonical camelCase for the multi-word Defects4J projects. Anything
    # not in this map falls back to single-letter title-casing.
    CANONICAL = {
        "jacksoncore":     "JacksonCore",
        "jacksondatabind": "JacksonDatabind",
        "jacksonxml":      "JacksonXml",
        "jxpath":          "JxPath",
    }
    s = bug_id.strip().replace("-", "_")
    if "_" in s:
        proj, num = s.split("_", 1)
        proj = CANONICAL.get(proj.lower(), proj.capitalize())
        s = proj + "_" + num
    return s


def d4j_project(bug_id: str) -> str:
    return bug_id.split("_", 1)[0]


def swe_project(instance_id: str) -> str:
    return instance_id.split("__", 1)[0]


def read_csv(path: Path) -> list[dict]:
    if not path.exists():
        print(f"  MISSING: {path}")
        return []
    with path.open() as f:
        return list(csv.DictReader(f))


def yes_no_to_int(v: str) -> int | str:
    v = (v or "").strip().lower()
    if v in ("yes", "true", "1", "pass", "passed"):
        return 1
    if v in ("no", "false", "0", "fail", "failed"):
        return 0
    return ""


# ---------- Hunk4J sources ----------

def load_d4j_hunk_meta() -> dict[str, dict]:
    """bug_id -> {hunk_count, hunk_divergence, proximity_class}"""
    meta: dict[str, dict] = defaultdict(dict)
    for row in read_csv(D4J_ROOT / "hunk_divergence.csv"):
        b = norm_d4j(row["bug_id"])
        meta[b]["hunk_count"] = row.get("hunk_count", "")
        meta[b]["hunk_divergence"] = row.get("divergence", "")
    for row in read_csv(D4J_ROOT / "proximity_class.csv"):
        b = norm_d4j(row["bug_id"])
        meta[b]["proximity_class"] = row.get("proximity_class", "")
    return meta


D4J_AGENT_FILES = {
    "claude": {
        "loc": D4J_ROOT / "claude_code_results/claude_results/claude_localization_ability.csv",
        "repair": D4J_ROOT / "claude_code_results/claude_results/claude_repair_ability.csv",
        "edit": D4J_ROOT / "claude_code_results/claude_results/edit_accuracy_summary_claude.csv",
        "token": D4J_ROOT / "claude_code_results/claude_results/token_and_duration_claude.csv",
    },
    "codex": {
        "loc": D4J_ROOT / "openai_codex_results/results-codex/codex_localization_ability.csv",
        "repair": D4J_ROOT / "openai_codex_results/results-codex/codex_repair_ability.csv",
        "edit": D4J_ROOT / "openai_codex_results/results-codex/edit_accuracy_summary_codex.csv",
        "token": D4J_ROOT / "openai_codex_results/results-codex/token_and_duration_codex.csv",
    },
    "gemini": {
        "loc": D4J_ROOT / "gemini_cli_results/gemini_localization_ability.csv",
        "repair": D4J_ROOT / "gemini_cli_results/gemini_repair_ability.csv",
        "edit": D4J_ROOT / "gemini_cli_results/ote-summary.csv",
        "token": D4J_ROOT / "gemini_cli_results/token_and_duration_gemini.csv",
    },
    "qwen": {
        "loc": D4J_ROOT / "qwen_code_results/qwen_results/qwen_localization_ability.csv",
        "repair": D4J_ROOT / "qwen_code_results/qwen_results/qwen_repair_ability.csv",
        "edit": D4J_ROOT / "qwen_code_results/qwen_results/qwen_edit_accuracy_summary.csv",
        "token": D4J_ROOT / "qwen_code_results/qwen_results/token_and_duration_qwen.csv",
    },
}

D4J_MCP_AGENT_FILES = {
    "gemini": {
        "loc": D4J_ROOT / "gemini_cli_results/mcp-gemini/gemini_localization_ability_mcp.csv",
        "repair": D4J_ROOT / "gemini_cli_results/mcp-gemini/gemini_repair_ability_mcp.csv",
        "edit": D4J_ROOT / "gemini_cli_results/mcp-gemini/ote-summary_mcp.csv",
        "token": D4J_ROOT / "gemini_cli_results/mcp-gemini/token_and_duration_gemini_mcp.csv",
    },
    "qwen": {
        "loc": D4J_ROOT / "qwen_code_results/qwen_results/mcp-qwen-code/qwen_localization_ability.csv",
        "repair": D4J_ROOT / "qwen_code_results/qwen_results/mcp-qwen-code/qwen_repair_ability.csv",
        "edit": None,
        "token": None,
    },
}


def build_d4j_rows(mode: str, agent_files: dict) -> list[dict]:
    hunk_meta = load_d4j_hunk_meta()
    rows: list[dict] = []
    for agent, files in agent_files.items():
        loc_map: dict[str, str] = {}
        for r in read_csv(files["loc"]):
            loc_map[norm_d4j(r["bug_id"])] = r.get("localization", "")

        edit_map: dict[str, dict] = {}
        if files.get("edit"):
            for r in read_csv(files["edit"]):
                edit_map[norm_d4j(r["bug"])] = r

        token_map: dict[str, dict] = {}
        if files.get("token"):
            for r in read_csv(files["token"]):
                key_col = "bug_id" if "bug_id" in r else "bug"
                token_map[norm_d4j(r[key_col])] = r

        repair_rows = read_csv(files["repair"])
        for r in repair_rows:
            bug = norm_d4j(r["bug_id"])
            meta = hunk_meta.get(bug, {})
            edit = edit_map.get(bug, {})
            tok = token_map.get(bug, {})

            # tokens: claude has cache_*; codex uses "input_token"/"output_token"
            tin = tok.get("total_input_token") or tok.get("input_token") or ""
            tout = tok.get("total_output_token") or tok.get("output_token") or ""
            row = {
                "bug_id": bug,
                "benchmark": "hunk4j",
                "project": d4j_project(bug),
                "agent": agent,
                "mode": mode,
                "hunk_count": meta.get("hunk_count", ""),
                "hunk_divergence": meta.get("hunk_divergence", ""),
                "proximity_class": meta.get("proximity_class", ""),
                "localization": loc_map.get(bug, ""),
                "repair": r.get("repair", ""),
                "compile_fail": r.get("compile_fail", ""),
                "failed_test_prior": r.get("failed_test_prior", ""),
                "failed_test_after": r.get("failed_test_after", ""),
                "regression_reduction": r.get("regression_reduction", ""),
                "fail_to_pass_resolved": "",
                "no_regressions": "",
                "failed_tests": "",
                "num_expected_edits": edit.get("num_expected", ""),
                "correct_edits": edit.get("correct_edits", ""),
                "ote": edit.get("ote", ""),
                "missed_edits": edit.get("missed_edits", ""),
                "total_input_tokens": tin,
                "total_output_tokens": tout,
                "cache_creation_tokens": tok.get("cache_creation_tokens", ""),
                "cache_read_tokens": tok.get("cache_read_tokens", ""),
                "time_duration_s": tok.get("time_duration", ""),
            }
            rows.append(row)
    return rows


# ---------- HunkSWE sources ----------

SWE_AGENT_DIRS = {
    ("claude", "vanilla"): SWE_ROOT / "claude-cli-automation",
    ("codex",  "vanilla"): SWE_ROOT / "codex-cli-automation",
    ("gemini", "vanilla"): SWE_ROOT / "gemini-cli-automation",
    ("qwen",   "vanilla"): SWE_ROOT / "qwen-cli-automation",
    ("gemini", "mcp"):     SWE_ROOT / "gemini-cli-automation-mcp",
    ("qwen",   "mcp"):     SWE_ROOT / "qwen-cli-automation-mcp",
}


def load_swe_hunk_meta() -> dict[str, dict]:
    meta: dict[str, dict] = defaultdict(dict)
    for r in read_csv(SWE_ROOT / "swe_hunk_divergence/total_hunk_divergence_results.csv"):
        meta[r["bug_id"]]["hunk_count"] = r.get("hunk_count", "")
        meta[r["bug_id"]]["hunk_divergence"] = r.get("divergence", "")
    for r in read_csv(SWE_ROOT / "swe_proximity_class/proximity_class.csv"):
        meta[r["issue_id"]]["proximity_class"] = r.get("proximity_class", "")
    return meta


_GOLD_FILE_CACHE: dict[str, set] = {}

def load_gold_files() -> dict[str, set]:
    """instance_id -> set of file paths touched by the gold patch."""
    if _GOLD_FILE_CACHE:
        return _GOLD_FILE_CACHE
    diff_re = re.compile(r"^diff --git a/(\S+) b/\S+", re.MULTILINE)
    with (SWE_ROOT / "swe_bench_verified/swe_bench.jsonl").open() as f:
        for line in f:
            rec = json.loads(line)
            files = set(diff_re.findall(rec.get("patch", "")))
            _GOLD_FILE_CACHE[rec["instance_id"]] = files
    return _GOLD_FILE_CACHE


def patch_files_for(agent_dir: Path, instance_id: str) -> set:
    """Files touched by the agent's most-recent patch-*.diff for this instance."""
    logs_dir = agent_dir / "workspace_docker" / instance_id / "logs"
    if not logs_dir.exists():
        return set()
    diff_files = sorted(logs_dir.glob("patch-*.diff"))
    if not diff_files:
        return set()
    diff_re = re.compile(r"^diff --git a/(\S+) b/\S+", re.MULTILINE)
    text = diff_files[-1].read_text(errors="replace")
    return set(diff_re.findall(text))


def derive_swe_localization(agent_dir: Path, instance_id: str, gold_files: dict[str, set]) -> int:
    """Paper §4.4 definition: agent's modified files must be a *superset* of
    the gold-patch files (every fault location must be touched)."""
    touched = patch_files_for(agent_dir, instance_id)
    gold = gold_files.get(instance_id, set())
    if not gold:
        return ""
    return 1 if gold.issubset(touched) else 0


SWE_EDIT_ACCURACY_CSVS = {
    ("claude", "vanilla"): SWE_ROOT / "claude-cli-automation/results/claude_edit_accuracy_summary.csv",
    ("codex",  "vanilla"): SWE_ROOT / "codex-cli-automation/results/codex_edit_accuracy_summary.csv",
    ("gemini", "vanilla"): SWE_ROOT / "gemini-cli-automation/results/gemini_edit_accuracy_summary.csv",
    ("qwen",   "vanilla"): SWE_ROOT / "qwen-cli-automation/results/qwen_edit_accuracy_summary.csv",
    ("gemini", "mcp"):     SWE_ROOT / "gemini-cli-automation-mcp/results/gemini_mcp_edit_accuracy_summary.csv",
    ("qwen",   "mcp"):     SWE_ROOT / "qwen-cli-automation-mcp/results/qwen_mcp_edit_accuracy_summary.csv",
}


def load_swe_edit_accuracy() -> dict[tuple, dict]:
    """(instance_id, agent, mode) -> {num_expected, correct_edits, ote, missed_edits}
    sourced from swe-bench/<agent>-cli-automation[-mcp]/results/<tag>_edit_accuracy_summary.csv
    produced by swe-bench/scripts/metrics-<agent>/edit_accuracy_<agent>.py."""
    out: dict[tuple, dict] = {}
    for (agent, mode), path in SWE_EDIT_ACCURACY_CSVS.items():
        for r in read_csv(path):
            # Original Hunk4J scripts emit `bug`; SWE-bench-adapted version uses
            # the same column name for backward compatibility.
            iid = r.get("bug") or r.get("instance_id")
            out[(iid, agent, mode)] = r
    return out


def load_swe_tokens() -> dict[tuple, dict]:
    """(instance_id, agent, mode) -> token/duration dict extracted from
    agent_logs by extract_hunkswe_tokens.py. Returns empty dict if the file
    hasn't been generated yet."""
    p = Path("/Users/danielding/Desktop/agentic-multihunk-repair/hunkswe_token_duration.csv")
    out: dict[tuple, dict] = {}
    if not p.exists():
        return out
    for r in read_csv(p):
        out[(r["instance_id"], r["agent"], r["mode"])] = r
    return out


def build_swe_rows() -> list[dict]:
    hunk_meta = load_swe_hunk_meta()
    gold_files = load_gold_files()
    token_lookup = load_swe_tokens()
    edit_lookup = load_swe_edit_accuracy()
    rows: list[dict] = []

    for (agent, mode), agent_dir in SWE_AGENT_DIRS.items():
        tag = agent if mode == "vanilla" else f"{agent}_mcp"
        results_csv = agent_dir / "results" / f"test_results_model_{tag}.csv"
        for r in read_csv(results_csv):
            iid = r["instance_id"]
            meta = hunk_meta.get(iid, {})
            tok = token_lookup.get((iid, agent, mode), {})
            ea = edit_lookup.get((iid, agent, mode), {})
            row = {
                "bug_id": iid,
                "benchmark": "hunkswe",
                "project": swe_project(iid),
                "agent": agent,
                "mode": mode,
                "hunk_count": meta.get("hunk_count", ""),
                "hunk_divergence": meta.get("hunk_divergence", ""),
                "proximity_class": meta.get("proximity_class", ""),
                "localization": derive_swe_localization(agent_dir, iid, gold_files),
                "repair": yes_no_to_int(r.get("resolved", "")),
                "compile_fail": "",
                "failed_test_prior": "",
                "failed_test_after": "",
                "regression_reduction": "",
                "fail_to_pass_resolved": yes_no_to_int(r.get("fail_to_pass_resolved", "")),
                "no_regressions": yes_no_to_int(r.get("no_regressions", "")),
                "failed_tests": r.get("failed_tests", ""),
                "num_expected_edits": ea.get("num_expected", ""),
                "correct_edits": ea.get("correct_edits", ""),
                "ote": ea.get("ote", ""),
                "missed_edits": ea.get("missed_edits", ""),
                "total_input_tokens": tok.get("total_input_tokens", ""),
                "total_output_tokens": tok.get("total_output_tokens", ""),
                "cache_creation_tokens": tok.get("cache_creation_tokens", ""),
                "cache_read_tokens": tok.get("cache_read_tokens", ""),
                "time_duration_s": r.get("duration_s", ""),
            }
            rows.append(row)
    return rows


# ---------- main ----------

def main():
    print("Loading Hunk4J vanilla rows...")
    rows = build_d4j_rows("vanilla", D4J_AGENT_FILES)
    print(f"  -> {len(rows)} rows")

    print("Loading Hunk4J MCP rows...")
    mcp_rows = build_d4j_rows("mcp", D4J_MCP_AGENT_FILES)
    print(f"  -> {len(mcp_rows)} rows")

    print("Loading HunkSWE rows (deriving localization from patches)...")
    swe_rows = build_swe_rows()
    print(f"  -> {len(swe_rows)} rows")

    all_rows = rows + mcp_rows + swe_rows
    print(f"Total: {len(all_rows)} rows")

    with OUT_PATH.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=HEADERS)
        w.writeheader()
        for r in all_rows:
            w.writerow(r)
    print(f"Wrote {OUT_PATH}")

    # Quick breakdown
    by = defaultdict(int)
    for r in all_rows:
        by[(r["benchmark"], r["mode"], r["agent"])] += 1
    for k in sorted(by):
        print(f"  {k}: {by[k]}")


if __name__ == "__main__":
    main()
