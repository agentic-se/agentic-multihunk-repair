#!/usr/bin/env python3
from __future__ import annotations
import argparse
import json
from pathlib import Path
from typing import Dict, List, Tuple
from collections import Counter, defaultdict
import csv
import sys

# Claude Code tool names we care about
CLAUDE_TOOLS = {
    "Bash",
    "Read",
    "Write",
    "Edit",
    "Glob",
    "Grep",
    "Task",
    "TodoWrite",
    "WebFetch",
    "WebSearch",
    "NotebookEdit",
    "ExitPlanMode",
    "AskUserQuestion",
    "BashOutput",
    "KillShell",
    "SlashCommand",
    "Skill",
}

# Tool name -> key to extract from input
ARG_KEY_BY_TOOL = {
    "Bash": "command",
    "WebSearch": "query",
    "WebFetch": "prompt",  # fallback to 'url' if prompt missing
}

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Count tool invocations from Claude Code JSONL log files."
    )
    p.add_argument("--input-dir", required=True,
                   help="Directory containing bug folders with *.jsonl files.")
    p.add_argument("--pattern", default="*.jsonl",
                   help="Glob for log files inside bug folders (default: *.jsonl).")
    p.add_argument("--out-long", required=True,
                   help="Path to write long CSV: bug,tool_name,count,command.")
    p.add_argument("--out-wide",
                   help="Optional path to write wide CSV: bug plus one column per tool_name.")
    return p.parse_args()

def load_jsonl_file(path: Path) -> List[dict]:
    """Load JSONL file (one JSON object per line)."""
    lines = []
    with path.open('r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                if isinstance(obj, dict):
                    lines.append(obj)
            except json.JSONDecodeError:
                pass
    return lines

def extract_tool_calls(log_objects: List[dict]) -> List[Tuple[str, dict]]:
    """
    Extract tool calls from Claude log objects.
    Returns list of (tool_name, input_dict) tuples.
    """
    tool_calls = []
    for obj in log_objects:
        # Look for assistant messages with tool_use content
        if obj.get('type') != 'assistant':
            continue

        message = obj.get('message', {})
        if not isinstance(message, dict):
            continue

        content = message.get('content', [])
        if not isinstance(content, list):
            continue

        for item in content:
            if not isinstance(item, dict):
                continue
            if item.get('type') == 'tool_use':
                tool_name = item.get('name', '')
                tool_input = item.get('input', {})
                if tool_name:
                    tool_calls.append((tool_name, tool_input))

    return tool_calls

def get_argument_for_tool(tool_name: str, tool_input: dict) -> str | None:
    """
    Extract relevant argument for supported tools:
      - Bash -> command
      - WebSearch -> query
      - WebFetch -> prompt (fallback: url)
    """
    key = ARG_KEY_BY_TOOL.get(tool_name)
    if not key:
        return None

    val = tool_input.get(key)
    if not isinstance(val, str) or not val.strip():
        if tool_name == "WebFetch":
            alt = tool_input.get("url")
            if isinstance(alt, str) and alt.strip():
                return alt.strip()
        return None
    return val.strip()

def bug_from_dirname(path: Path) -> str:
    """
    Extract bug id from directory name.
    E.g., 'chart_14' -> 'chart_14'
    """
    return path.name

def count_tools_and_args(tool_calls: List[Tuple[str, dict]]) -> Tuple[Counter, Dict[str, Counter]]:
    """
    Returns:
      - tool_counts: Counter(tool_name -> count)
      - args_by_tool: Dict[tool_name -> Counter(argument -> count)]
    """
    tool_counts = Counter()
    args_by_tool: Dict[str, Counter] = defaultdict(Counter)

    for tool_name, tool_input in tool_calls:
        tool_counts[tool_name] += 1

        arg = get_argument_for_tool(tool_name, tool_input)
        if arg:
            args_by_tool[tool_name][arg] += 1

    return tool_counts, args_by_tool

def write_long_csv(out_path: Path, rows: List[Tuple[str, str, int, str]]) -> None:
    """
    Rows: (bug, tool_name, count, command)
    'command' column stores command/query/prompt depending on tool (empty for others).
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["bug", "tool_name", "count", "command"])
        for bug, tool_name, cnt, cmd in rows:
            w.writerow([bug, tool_name, cnt, cmd])

def write_wide_csv(out_path: Path, table: Dict[str, Counter]) -> None:
    tools = sorted({tn for counts in table.values() for tn in counts})
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["bug"] + tools)
        for bug in sorted(table):
            w.writerow([bug] + [table[bug].get(tn, 0) for tn in tools])

def main():
    args = parse_args()
    inp = Path(args.input_dir).expanduser().resolve()
    if not inp.is_dir():
        print(f"ERROR: --input-dir is not a directory: {inp}", file=sys.stderr)
        sys.exit(2)

    per_bug_tools: Dict[str, Counter] = {}
    per_bug_args: Dict[str, Dict[str, Counter]] = {}
    parse_error = False

    # Find all bug directories
    bug_dirs = [d for d in sorted(inp.iterdir()) if d.is_dir()]
    if not bug_dirs:
        print(f"[WARN] No subdirectories found under {inp}")
    else:
        print(f"Found {len(bug_dirs)} bug directories under {inp}")

    for bug_dir in bug_dirs:
        bug = bug_from_dirname(bug_dir)

        # Find all matching log files in this bug directory
        log_files = list(bug_dir.glob(args.pattern))
        if not log_files:
            print(f"[WARN] No {args.pattern} files in {bug_dir.name}")
            continue

        all_tool_calls = []
        for log_file in log_files:
            try:
                log_objects = load_jsonl_file(log_file)
                tool_calls = extract_tool_calls(log_objects)
                all_tool_calls.extend(tool_calls)
            except Exception as e:
                print(f"[WARN] Failed to parse {log_file.name}: {e}", file=sys.stderr)
                parse_error = True

        if not all_tool_calls:
            print(f"[WARN] No tool calls found in {bug}")
            per_bug_tools[bug] = Counter()
            per_bug_args[bug] = {}
            continue

        tool_counts, args_by_tool = count_tools_and_args(all_tool_calls)
        per_bug_tools[bug] = tool_counts
        per_bug_args[bug] = args_by_tool

        # Terminal summary
        if tool_counts:
            tool_summary = ", ".join(f"{tn}:{tool_counts[tn]}" for tn in sorted(tool_counts))
        else:
            tool_summary = "(no tool calls found)"

        suffixes = []
        for tn in ("Bash", "WebSearch", "WebFetch"):
            if args_by_tool.get(tn):
                top = sorted(args_by_tool[tn], key=args_by_tool[tn].get, reverse=True)[:3]
                top_s = ", ".join(f"{arg}:{args_by_tool[tn][arg]}" for arg in top)
                suffixes.append(f"{tn} → {top_s}")
        if suffixes:
            print(f"- {bug}: {tool_summary} | " + " | ".join(suffixes))
        else:
            print(f"- {bug}: {tool_summary}")

    # Build LONG rows
    long_rows: List[Tuple[str, str, int, str]] = []
    for bug, tool_counter in per_bug_tools.items():
        args_by_tool = per_bug_args.get(bug, {})
        for tool_name, total_cnt in sorted(tool_counter.items()):
            arg_counter = args_by_tool.get(tool_name)
            if arg_counter:
                for arg, cnt in sorted(arg_counter.items()):
                    long_rows.append((bug, tool_name, cnt, arg))
            else:
                long_rows.append((bug, tool_name, total_cnt, ""))

    # Write CSVs
    out_long = Path(args.out_long).expanduser().resolve()
    write_long_csv(out_long, long_rows)
    print(f"[OK] wrote long CSV → {out_long}")

    if args.out_wide:
        write_wide_csv(Path(args.out_wide).expanduser().resolve(), per_bug_tools)
        print(f"[OK] wrote wide CSV → {Path(args.out_wide).resolve()}")

    if parse_error:
        sys.exit(1)

if __name__ == "__main__":
    main()
