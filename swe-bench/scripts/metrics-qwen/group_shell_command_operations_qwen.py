#!/usr/bin/env python3
"""
Aggregate run_shell_command invocations by their base executable (ignoring arguments).

The script reads Qwen's detailed tool usage (`tools_count_qwen.csv`) and writes a
companion aggregate (`tools_count_all_specific_qwen.csv`). Existing columns from
the legacy aggregate are preserved, and only the most frequent shell commands
receive dedicated columns; the remainder are rolled into `run_shell_command_other`.
"""

from __future__ import annotations

import csv
import re
import shlex
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]

sys.path.insert(0, str(REPO_ROOT))
from agent_command_categorization import categorize_command
DETAILED_PATH = (
    REPO_ROOT
    / "results"
    / "qwen_code_results"
    / "qwen_results"
    / "tools_count_qwen.csv"
)
AGGREGATED_PATH = (
    REPO_ROOT
    / "results"
    / "qwen_code_results"
    / "qwen_results"
    / "tools_count_all_specific_qwen.csv"
)
TEMPLATE_AGGREGATED_PATH = AGGREGATED_PATH.with_name("tools_count_all_qwen.csv")

UNKNOWN_KEY = "__unknown__"
MAX_COMMAND_COLUMNS = 30
MIN_TOTAL_COUNT = 10
MIN_FALLBACK_COLUMNS = 12
CATEGORY_COLUMNS = [
    "run_shell_command_test",
    "run_shell_command_python_exec",
    "run_shell_command_git_all",
    "run_shell_command_package_install",
    "run_shell_command_file_operations",
    "run_shell_command_text_search",
    "run_shell_command_other",
]


def _first_command_segment(raw_command: str) -> str:
    """Return the part of the command before connectors like && or ;.

    Also handles heredocs by removing content between << 'EOF' and closing EOF.
    """
    segment = raw_command.strip()
    if not segment:
        return ""

    # Handle heredocs: if we see << followed by a delimiter,
    # extract the content before the heredoc
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
        return ""

    while idx < len(tokens):
        candidate = _clean_token(tokens[idx])

        # Filter out tokens that don't look like valid commands
        # e.g., "/tmp/cp.txt)" or other file paths
        if candidate.startswith('/') or candidate.endswith(')'):
            idx += 1
            continue

        sanitized = _sanitize_base(candidate)
        if sanitized:
            return sanitized
        idx += 1

    return ""


def _looks_like_env_assignment(token: str) -> bool:
    """Detect KEY=value patterns that precede a command."""
    if "=" not in token:
        return False

    if token.startswith((">", "<", "|")):
        return False

    if token.count("=") != 1:
        return False

    key, value = token.split("=", 1)
    return bool(key) and bool(value)


def _clean_token(token: str) -> str:
    """Strip common punctuation surrounding a token."""
    stripped = token.strip().strip("'\"")
    stripped = stripped.strip("()[]{}:,")
    return stripped


def _is_probable_command(token: str) -> bool:
    """Heuristic to decide whether a token represents an executable."""
    if not token:
        return False

    if token.startswith(("-", "--", "#")):
        return False

    if not any(ch.isalnum() for ch in token):
        return False

    if not any(ch.isalpha() for ch in token) and not token.startswith(("./", "../", "/", "~")):
        return False

    if token.startswith(("./", "../", "/", "~")):
        return True

    if token.startswith(".") and len(token) > 1 and token[1].isalpha():
        return True

    first = token[0]
    return first.isalpha() or first.isdigit()


def _sanitize_base(candidate: str) -> str:
    """Return a normalized command name or empty string if unsuitable."""
    if not candidate:
        return ""

    candidate = candidate.strip()
    if not _is_probable_command(candidate):
        return ""

    lowered = candidate.lower()

    if lowered.startswith("./"):
        lowered = lowered[2:]

    if "/" in lowered:
        lowered = lowered.rsplit("/", 1)[-1]

    if lowered.startswith("./"):
        lowered = lowered[2:]

    if not lowered or lowered[0].isdigit():
        return ""

    if lowered.endswith((".sh", ".py")):
        base = lowered
    elif "." in lowered:
        return ""
    else:
        base = lowered

    if not re.fullmatch(r"[a-z][a-z0-9_\-]*([.](sh|py))?", base):
        return ""

    return base


def _load_shell_command_counts() -> Tuple[
    Dict[str, Counter], Counter, Dict[str, Counter], Dict[str, Counter]
]:
    """Build bug -> base command counts, totals, and overall function usage."""
    bug_counts: Dict[str, Counter] = defaultdict(Counter)
    totals: Counter = Counter()
    bug_function_totals: Dict[str, Counter] = defaultdict(Counter)
    bug_category_totals: Dict[str, Counter] = defaultdict(Counter)

    with DETAILED_PATH.open(newline="") as detailed_file:
        reader = csv.DictReader(detailed_file)
        for row in reader:
            bug_id = row["bug"]
            count = int(row.get("count", "0") or 0)
            function_name = row.get("function_name", "").strip()

            if function_name:
                bug_function_totals[bug_id][function_name] += count

            if function_name != "run_shell_command":
                continue

            command = row.get("command", "").strip()

            category = categorize_command(command)
            category_column = f"run_shell_command_{category}"
            bug_category_totals[bug_id][category_column] += count

            base = _extract_base_command(command)
            if not base:
                bug_counts[bug_id][UNKNOWN_KEY] += count
                continue

            bug_counts[bug_id][base] += count
            totals[base] += count

    return bug_counts, totals, bug_function_totals, bug_category_totals


def _prepare_new_columns(bases: Iterable[str]) -> Tuple[List[str], Dict[str, str]]:
    """Return ordered column list and a mapping column -> base command."""
    columns: List[str] = []
    mapping: Dict[str, str] = {}

    for base in bases:
        column = f"run_shell_command_{base}"
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
    """Rewrite/produce the aggregated CSV with per-command shell counts."""
    (
        bug_counts,
        totals,
        bug_function_totals,
        bug_category_totals,
    ) = _load_shell_command_counts()

    sorted_base_items = sorted(
        totals.items(), key=lambda item: (-item[1], item[0])
    )

    selected_bases: List[str] = []
    for base, count in sorted_base_items:
        if len(selected_bases) >= MAX_COMMAND_COLUMNS:
            break
        if count < MIN_TOTAL_COUNT and len(selected_bases) >= MIN_FALLBACK_COLUMNS:
            break
        selected_bases.append(base)

    if not selected_bases:
        selected_bases = [base for base, _ in sorted_base_items[:MIN_FALLBACK_COLUMNS]]

    new_columns, column_to_base = _prepare_new_columns(selected_bases)
    base_category_map = {base: categorize_command(base) for base in selected_bases}

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

    function_names = sorted(
        {fn for counts in bug_function_totals.values() for fn in counts} - {"bug"}
    )

    allowed_columns = {"bug"} | set(function_names) | set(CATEGORY_COLUMNS) | set(new_columns)

    if fieldnames:
        fieldnames = [name for name in fieldnames if name in allowed_columns]

    if not fieldnames:
        fieldnames = ["bug"]
        if "run_shell_command" in function_names:
            fieldnames.append("run_shell_command")
        for fn in function_names:
            if fn != "run_shell_command":
                fieldnames.append(fn)

    if "bug" not in fieldnames:
        fieldnames.insert(0, "bug")

    if "run_shell_command" in function_names and "run_shell_command" not in fieldnames:
        fieldnames.insert(
            1 if len(fieldnames) > 1 else len(fieldnames), "run_shell_command"
        )

    for fn in function_names:
        if fn not in fieldnames:
            fieldnames.append(fn)

    if "run_shell_command_other" not in fieldnames:
        if "run_shell_command" in fieldnames:
            fieldnames.insert(
                fieldnames.index("run_shell_command") + 1, "run_shell_command_other"
            )
        else:
            fieldnames.append("run_shell_command_other")

    for column in CATEGORY_COLUMNS:
        if column not in fieldnames:
            if column == "run_shell_command_other":
                continue
            fieldnames.append(column)

    fieldnames = _insert_columns(fieldnames, new_columns)

    all_bugs = sorted(
        set(bug_function_totals.keys())
        | {row["bug"] for row in rows if row.get("bug")}
    )

    result_rows: List[Dict[str, int]] = []
    for bug in all_bugs:
        row: Dict[str, int] = {key: 0 for key in fieldnames}
        row["bug"] = bug

        function_counts = bug_function_totals.get(bug, Counter())
        for fn, total in function_counts.items():
            row[fn] = total

        category_counts = bug_category_totals.get(bug, Counter())
        for column in CATEGORY_COLUMNS:
            if column == "run_shell_command_other":
                continue
            if column in fieldnames:
                row[column] = category_counts.get(column, 0)

        base_counts = bug_counts.get(bug, Counter())
        other_value = category_counts.get("run_shell_command_other", 0)

        for column, base in column_to_base.items():
            count = base_counts.get(base, 0)
            row[column] = count
            if base_category_map.get(base) == "other":
                other_value -= count

        other_value = max(0, other_value)
        other_value += base_counts.get(UNKNOWN_KEY, 0)
        row["run_shell_command_other"] = other_value

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
        print("No run_shell_command usage found.")
        return

    top_n = 10
    print("=" * 80)
    print("Top run_shell_command invocations (ignoring arguments)")
    print("=" * 80)
    for rank, (base, count) in enumerate(
        sorted(totals.items(), key=lambda item: (-item[1], item[0]))[:top_n], start=1
    ):
        print(f"{rank:>2}. {base:<20} {count}")


if __name__ == "__main__":
    update_aggregated_csv()
