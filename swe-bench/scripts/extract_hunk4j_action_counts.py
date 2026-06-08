#!/usr/bin/env python3
"""
Extract per-bug action-category counts for the Hunk4J side, in the same
17-bucket PAPER_CATEGORIES schema produced by `categorize_action`. This
is the Defects4J counterpart to extract_hunkswe_action_counts.py — same
categorizer, same output schema — and it covers all 372 bugs per agent
(unlike the upstream tools_count_all_abstracted_<agent>.csv files which
were missing 97 Gemini and 33 Qwen rows because of an interrupted
abstraction pipeline).

Each agent's d4j JSON logs live in a different host directory; the
trajectory FORMAT is identical to the corresponding agent's HunkSWE
trajectory (this is by design — both runs use the same CLIs). We re-use
the per-format parsers from `extract_hunkswe_action_counts.iter_tool_calls`.

Output: one CSV per agent at <repo>/agent_action_counts/<agent>_hunk4j_action_counts.csv
with the same header as the HunkSWE counterparts:
  instance_id, <17 PAPER_CATEGORIES...>
"""
from __future__ import annotations
import csv
from collections import Counter
from pathlib import Path

# Reuse the categorizer + per-format parsers from the HunkSWE extractor
from agent_command_categorization.categorizer import PAPER_CATEGORIES, categorize_action
from extract_hunkswe_action_counts import iter_tool_calls, _split_atomic

HOME = Path.home()
REPO = Path(__file__).resolve().parents[2]
OUT_DIR = REPO / "agent_action_counts"
OUT_DIR.mkdir(exist_ok=True)


# (agent, log_root, layout)
# layout is either:
#   "flat" — root contains one file per bug, named <BugId>_logs.json
#   "per_bug_subdir(<glob>)" — root has one subdir per bug, file matching glob inside
LOG_ROOTS = {
    "claude": (HOME / "Desktop/research/claude_logs/collected-claude-logs", "per_bug_subdir", "*.jsonl"),
    "codex":  (HOME / "Desktop/research/codex_logs/collected-codex-cli-logs", "per_bug_subdir", "codex-session-rollout-*.jsonl"),
    "gemini": (HOME / "Desktop/research/logs/372_bugs",                      "flat", "{bug}_logs.json"),
    "qwen":   (HOME / "Desktop/research/qwen_logs/collected-qwen-code-logs", "per_bug_subdir", "qwen-*.json"),
}


def normalize_bug_id(raw: str) -> str:
    """Match build_hunkds.py's `.capitalize()` rule used in hunkDS.csv."""
    parts = raw.replace("-", "_").split("_", 1)
    return parts[0].capitalize() + "_" + parts[1] if len(parts) > 1 else raw


def find_log_for_bug(agent: str, root: Path, layout: str, pat: str, bug_id: str) -> Path | None:
    """Find this agent's trajectory log for a given bug id (Chart_14 style)."""
    if layout == "flat":
        # Gemini: files named like 'Chart-14_logs.json' OR 'Chart_14_logs.json'.
        # Try both dash and underscore variants.
        dash = bug_id.replace("_", "-")
        for cand in (root / pat.format(bug=bug_id),
                     root / pat.format(bug=dash),
                     root / pat.format(bug=bug_id.lower()),
                     root / pat.format(bug=dash.lower())):
            if cand.exists():
                return cand
        return None
    # per_bug_subdir layout: root/<BugId>/<glob>. Bug folders may be
    # PascalCase ('Chart_14') OR lowercase ('chart_14') across agents.
    candidates = [bug_id, bug_id.lower(), bug_id.replace("_", "-"),
                  bug_id.lower().replace("_", "-")]
    for cand in candidates:
        d = root / cand
        if d.is_dir():
            files = sorted(d.glob(pat))
            if files:
                # If there are multiple session files (e.g. crash + retry),
                # take the LARGEST — that's the real session, not a stub.
                # This matches the convention used elsewhere; we are reading
                # raw call data so noise from retries is harmless.
                return max(files, key=lambda p: p.stat().st_size)
    return None


def main() -> None:
    # bug list = whatever the repair CSV ships per agent (always 372)
    repair_csvs = {
        "claude": HOME/"Desktop/birch/oak/results/claude_code_results/claude_results/claude_repair_ability.csv",
        "codex":  HOME/"Desktop/birch/oak/results/openai_codex_results/results-codex/codex_repair_ability.csv",
        "gemini": HOME/"Desktop/birch/oak/results/gemini_cli_results/gemini_repair_ability.csv",
        "qwen":   HOME/"Desktop/birch/oak/results/qwen_code_results/qwen_results/qwen_repair_ability.csv",
    }

    for agent, (root, layout, pat) in LOG_ROOTS.items():
        if not root.exists():
            print(f"  MISSING log root: {root}")
            continue

        bugs = []
        with open(repair_csvs[agent]) as f:
            for r in csv.DictReader(f):
                bugs.append(normalize_bug_id(r["bug_id"]))

        per_bug: dict[str, Counter] = {}
        missing = 0
        total_calls = 0
        for bug in bugs:
            log = find_log_for_bug(agent, root, layout, pat, bug)
            if log is None:
                per_bug[bug] = Counter()
                missing += 1
                continue
            counts: Counter = Counter()
            for tool_name, cmd in iter_tool_calls(agent, log):
                if tool_name in ("Bash", "run_shell_command") and cmd:
                    for atom in _split_atomic(cmd):
                        counts[categorize_action("Bash", atom)] += 1
                        total_calls += 1
                else:
                    counts[categorize_action(tool_name, cmd)] += 1
                    total_calls += 1
            per_bug[bug] = counts

        out_csv = OUT_DIR / f"{agent}_hunk4j_action_counts.csv"
        with out_csv.open("w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["instance_id"] + list(PAPER_CATEGORIES))
            for bug in sorted(per_bug):
                w.writerow([bug] + [per_bug[bug].get(c, 0) for c in PAPER_CATEGORIES])
        print(f"  {agent}: {len(per_bug)} bugs, {missing} no-log, {total_calls} tool calls -> {out_csv.name}")


if __name__ == "__main__":
    main()
