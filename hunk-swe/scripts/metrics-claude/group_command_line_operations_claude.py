#!/usr/bin/env python3
"""
Aggregate Bash commands by their base executable (ignoring arguments).

This script reads the detailed Claude tool usage CSV and writes an augmented
aggregate CSV so that common shell commands (e.g., `ls -la` vs `ls -l`) are
counted under the same column (`Bash_ls`). If the target CSV does not exist yet,
it will be created.
"""

from __future__ import annotations

import csv
import shlex
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]

# Delegate categorization to the shared SWE-bench module.
sys.path.insert(0, str(REPO_ROOT))
from agent_command_categorization import categorize_command  # noqa: E402
DETAILED_PATH = (
    REPO_ROOT
    / "results"
    / "claude_code_results"
    / "claude_results"
    / "tools_count_claude.csv"
)
AGGREGATED_PATH = (
    REPO_ROOT
    / "results"
    / "claude_code_results"
    / "claude_results"
    / "tools_count_all_specific_claude.csv"
)
TEMPLATE_AGGREGATED_PATH = AGGREGATED_PATH.with_name("tools_count_all_claude.csv")

UNKNOWN_KEY = "__unknown__"
CATEGORY_COLUMNS = [
    "Bash_test",
    "Bash_python_exec",
    "Bash_git_all",
    "Bash_package_install",
    "Bash_file_operations",
    "Bash_text_search",
    "Bash_other",
]

def _first_command_segment(raw_command: str) -> str:
    """Return the part of the command before any connectors like && or ;.

    Also handles heredocs by removing content between << 'EOF' and closing EOF.
    """
    segment = raw_command.strip()
    if not segment:
        return ""

    # Handle heredocs: if we see << followed by a delimiter,
    # extract the content before the heredoc
    import re
    heredoc_match = re.search(r'<<\s*(["\']?)(\w+)\1', segment)
    if heredoc_match:
        delimiter = heredoc_match.group(2)  # e.g., "EOF"
        # Find the closing delimiter on its own line
        lines = segment.split('\n')
        for i, line in enumerate(lines):
            if line.strip() == delimiter:
                # Found closing delimiter, keep only content before heredoc starts
                segment = '\n'.join(lines[:1])  # Keep only the first line
                break

    for delimiter in ("&&", "||", ";", "\n"):
        if delimiter in segment:
            segment = segment.split(delimiter, 1)[0].strip()

    return segment


def _extract_base_command(raw_command: str) -> str:
    """Extract the base command, ignoring arguments and env assignments."""
    segment = _first_command_segment(raw_command)
    if not segment:
        return ""

    # Check if the entire segment is just an env assignment with command substitution
    # e.g., "CP=$(cat /tmp/cp.txt)" should be skipped entirely
    import re
    if re.match(r'^\s*\w+=', segment):
        # This looks like an env assignment, skip it
        return ""

    try:
        tokens = shlex.split(segment)
    except ValueError:
        tokens = segment.split()

    if not tokens:
        return ""

    idx = 0
    # Skip environment variable assignments
    while idx < len(tokens) and _looks_like_env_assignment(tokens[idx]):
        idx += 1

    # Skip tokens that are part of broken command substitutions
    # e.g., "CP=$(cat" followed by "/tmp/cp.txt)"
    while idx < len(tokens) and (
        tokens[idx].endswith('(') or
        (idx > 0 and '=$(' in tokens[idx-1] and tokens[idx].endswith(')'))
    ):
        idx += 1

    if idx >= len(tokens):
        # Entire command was a sequence of assignments; treat as unknown.
        return ""

    base = tokens[idx].strip()

    # Filter out tokens that don't look like valid commands
    # e.g., "/tmp/cp.txt)" or other file paths
    if base.startswith('/') or base.endswith(')'):
        return ""

    return base.lower()


def _looks_like_env_assignment(token: str) -> bool:
    """Detect KEY=value patterns that precede a command."""
    if "=" not in token:
        return False

    if token.startswith((">", "<", "|")):
        return False

    # Avoid treating operators like == or =~ as assignments.
    if token.count("=") != 1:
        return False

    key, value = token.split("=", 1)
    return bool(key) and bool(value)


def _load_bash_command_counts() -> Tuple[
    Dict[str, Counter], Counter, Dict[str, Counter], Dict[str, Counter]
]:
    """Build bug -> base command counts, totals, and overall tool usage."""
    bug_counts: Dict[str, Counter] = defaultdict(Counter)
    totals: Counter = Counter()
    bug_tool_totals: Dict[str, Counter] = defaultdict(Counter)
    bug_category_totals: Dict[str, Counter] = defaultdict(Counter)

    with DETAILED_PATH.open(newline="") as detailed_file:
        reader = csv.DictReader(detailed_file)
        for row in reader:
            bug_id = row["bug"]
            count = int(row.get("count", "0") or 0)
            tool_name = row.get("tool_name", "").strip()

            if tool_name:
                bug_tool_totals[bug_id][tool_name] += count

            if tool_name != "Bash":
                continue

            command = row.get("command", "").strip()

            category = categorize_command(command)
            category_column = f"Bash_{category}"
            bug_category_totals[bug_id][category_column] += count

            base = _extract_base_command(command)
            if not base:
                bug_counts[bug_id][UNKNOWN_KEY] += count
                continue

            bug_counts[bug_id][base] += count
            totals[base] += count

    return bug_counts, totals, bug_tool_totals, bug_category_totals


def _prepare_new_columns(bases: Iterable[str]) -> Tuple[List[str], Dict[str, str]]:
    """Return ordered column list and a mapping column -> base command."""
    columns: List[str] = []
    mapping: Dict[str, str] = {}

    for base in bases:
        column = f"Bash_{base}"
        columns.append(column)
        mapping[column] = base

    return columns, mapping


def _insert_columns(fieldnames: List[str], new_columns: List[str]) -> List[str]:
    """Ensure all new columns are present, preserving original order."""
    updated = list(fieldnames)
    for column in new_columns:
        if column not in updated:
            updated.append(column)
    return updated


def update_aggregated_csv() -> None:
    """Rewrite the aggregated CSV with per-command Bash counts."""
    bug_counts, totals, bug_tool_totals, bug_category_totals = (
        _load_bash_command_counts()
    )

    # Sort base commands by total count (descending) then alphabetically.
    sorted_bases = [
        base
        for base, _ in sorted(
            totals.items(), key=lambda item: (-item[1], item[0])
        )
    ]

    new_columns, column_to_base = _prepare_new_columns(sorted_bases)

    if AGGREGATED_PATH.exists():
        source_path = AGGREGATED_PATH
    elif TEMPLATE_AGGREGATED_PATH.exists():
        source_path = TEMPLATE_AGGREGATED_PATH
    else:
        source_path = None

    rows: List[Dict[str, int]] = []
    fieldnames: List[str] = []

    if source_path:
        with source_path.open(newline="") as aggregated_file:
            reader = csv.DictReader(aggregated_file)
            rows = list(reader)
            fieldnames = reader.fieldnames or []

    tool_names = sorted(
        {tool for counts in bug_tool_totals.values() for tool in counts} - {"bug"}
    )

    if not fieldnames:
        fieldnames = ["bug"]
        if "Bash" in tool_names:
            fieldnames.append("Bash")
        for tool in tool_names:
            if tool != "Bash":
                fieldnames.append(tool)

    if "bug" not in fieldnames:
        fieldnames.insert(0, "bug")

    if "Bash" in tool_names and "Bash" not in fieldnames:
        fieldnames.insert(1 if len(fieldnames) > 1 else len(fieldnames), "Bash")

    for tool in tool_names:
        if tool not in fieldnames:
            fieldnames.append(tool)

    if "Bash_other" not in fieldnames:
        if "Bash" in fieldnames:
            fieldnames.insert(fieldnames.index("Bash") + 1, "Bash_other")
        else:
            fieldnames.append("Bash_other")

    for column in CATEGORY_COLUMNS:
        if column not in fieldnames:
            if column == "Bash_other":
                continue
            fieldnames.append(column)

    fieldnames = _insert_columns(fieldnames, new_columns)

    all_bugs = sorted(
        set(bug_tool_totals.keys())
        | {row["bug"] for row in rows if row.get("bug")}
    )

    result_rows: List[Dict[str, int]] = []
    for bug in all_bugs:
        row: Dict[str, int] = {key: 0 for key in fieldnames}
        row["bug"] = bug

        tool_counts = bug_tool_totals.get(bug, Counter())
        for tool, total in tool_counts.items():
            row[tool] = total

        category_counts = bug_category_totals.get(bug, Counter())
        for column in CATEGORY_COLUMNS:
            if column == "Bash_other":
                continue
            if column in fieldnames:
                row[column] = category_counts.get(column, 0)

        counts = bug_counts.get(bug, Counter())
        for column, base in column_to_base.items():
            row[column] = counts.get(base, 0)

        row["Bash_other"] = category_counts.get("Bash_other", 0) + counts.get(
            UNKNOWN_KEY, 0
        )
        result_rows.append(row)

    AGGREGATED_PATH.parent.mkdir(parents=True, exist_ok=True)

    with AGGREGATED_PATH.open("w", newline="") as aggregated_file:
        writer = csv.DictWriter(aggregated_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(result_rows)

    _print_summary(totals)


def _print_summary(totals: Counter) -> None:
    """Print simple diagnostics about the aggregation."""
    if not totals:
        print("No Bash command usage found.")
        return

    top_n = 10
    print("=" * 80)
    print("Top Bash commands (ignoring arguments)")
    print("=" * 80)
    for rank, (base, count) in enumerate(
        sorted(totals.items(), key=lambda item: (-item[1], item[0]))[:top_n], start=1
    ):
        print(f"{rank:>2}. {base:<20} {count}")


if __name__ == "__main__":
    update_aggregated_csv()
