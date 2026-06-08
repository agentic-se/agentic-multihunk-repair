#!/usr/bin/env python3
from __future__ import annotations
import argparse
import json
from pathlib import Path
from typing import Dict, List, Tuple
from collections import Counter, defaultdict
import csv
import sys

# Codex function call types we care about
CODEX_FUNCTION_CALL = "function_call"

# Map Codex tool names to normalized names
TOOL_NAME_MAP = {
    "shell": "run_shell_command",
    "read_file": "read_file",
    "write_file": "write_file",
    "edit_file": "edit_file",
}

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Count tool invocations from Codex JSONL files (one per bug)."
    )
    p.add_argument("--input-dir", required=True,
                   help="Directory containing bug folders with JSONL files.")
    p.add_argument("--pattern", default="codex-session-*.jsonl",
                   help="Glob for JSONL files inside each bug folder (default: codex-session-*.jsonl).")
    p.add_argument("--out-long", required=True,
                   help="Path to write long CSV: bug,function_name,count,command.")
    p.add_argument("--out-wide",
                   help="Optional path to write wide CSV: bug plus one column per function_name.")
    return p.parse_args()

def load_codex_jsonl(path: Path) -> List[dict]:
    """Load JSONL file where each line is a JSON object."""
    objects = []
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    if isinstance(obj, dict):
                        objects.append(obj)
                except json.JSONDecodeError:
                    continue
    except Exception as e:
        print(f"[WARN] Failed to read {path}: {e}", file=sys.stderr)
    return objects

def normalize_tool_name(name: str) -> str:
    """Normalize Codex tool names to match Gemini naming convention."""
    return TOOL_NAME_MAP.get(name, name)

def parse_function_arguments(args_obj) -> dict:
    """Parse function arguments from Codex format."""
    if isinstance(args_obj, str):
        try:
            return json.loads(args_obj)
        except:
            return {}
    elif isinstance(args_obj, dict):
        return args_obj
    return {}

def get_command_from_shell(args: dict) -> str | None:
    """Extract command from shell tool arguments."""
    # Codex shell format: {"command": ["bash", "-lc", "actual command"]}
    cmd = args.get("command")
    if isinstance(cmd, list) and len(cmd) >= 3:
        # Return the actual command (3rd element)
        return cmd[2] if len(cmd) > 2 else " ".join(cmd)
    elif isinstance(cmd, str):
        return cmd
    return None

def bug_from_dirname(path: Path) -> str:
    """Extract bug ID from directory name like 'Chart_14' or file path."""
    return path.name

def count_tools_and_args(objects: List[dict]) -> Tuple[Counter, Dict[str, Counter]]:
    """
    Returns:
      - tool_counts: Counter(function_name -> count)
      - args_by_tool: Dict[function_name -> Counter(argument -> count)]
    """
    tool_counts = Counter()
    args_by_tool: Dict[str, Counter] = defaultdict(Counter)

    for obj in objects:
        # Look for function_call records
        if obj.get("type") != CODEX_FUNCTION_CALL:
            continue

        fn = obj.get("name", "")
        if not fn:
            continue

        # Normalize tool name
        normalized_fn = normalize_tool_name(fn)
        tool_counts[normalized_fn] += 1

        # Extract arguments if it's a shell command
        if fn == "shell":
            args_str = obj.get("arguments", "{}")
            args = parse_function_arguments(args_str)
            cmd = get_command_from_shell(args)
            if cmd:
                args_by_tool[normalized_fn][cmd] += 1

    return tool_counts, args_by_tool

def write_long_csv(out_path: Path, rows: List[Tuple[str, str, int, str]]) -> None:
    """
    Rows: (bug, function_name, count, command)
    'command' column stores command/query/prompt depending on tool (empty for others).
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["bug", "function_name", "count", "command"])
        for bug, fn, cnt, cmd in rows:
            w.writerow([bug, fn, cnt, cmd])

def write_wide_csv(out_path: Path, table: Dict[str, Counter]) -> None:
    tools = sorted({fn for counts in table.values() for fn in counts})
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["bug"] + tools)
        for bug in sorted(table):
            w.writerow([bug] + [table[bug].get(fn, 0) for fn in tools])

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
        print(f"[WARN] No bug directories found under {inp}")
    else:
        print(f"Found {len(bug_dirs)} bug directories under {inp}")

    for bug_dir in bug_dirs:
        bug = bug_from_dirname(bug_dir)

        # Find JSONL files in this bug directory
        jsonl_files = list(bug_dir.glob(args.pattern))

        if not jsonl_files:
            continue

        try:
            # Aggregate across all JSONL files for this bug
            all_objects = []
            for jf in jsonl_files:
                all_objects.extend(load_codex_jsonl(jf))

            tool_counts, args_by_tool = count_tools_and_args(all_objects)
            per_bug_tools[bug] = tool_counts
            per_bug_args[bug] = args_by_tool

            # Terminal summary
            if tool_counts:
                tool_summary = ", ".join(f"{fn}:{tool_counts[fn]}" for fn in sorted(tool_counts))
            else:
                tool_summary = "(no tool calls found)"

            suffixes = []
            if args_by_tool.get("run_shell_command"):
                top = sorted(args_by_tool["run_shell_command"],
                           key=args_by_tool["run_shell_command"].get, reverse=True)[:3]
                top_s = ", ".join(f"{arg[:50]}...:{args_by_tool['run_shell_command'][arg]}"
                                if len(arg) > 50 else f"{arg}:{args_by_tool['run_shell_command'][arg]}"
                                for arg in top)
                suffixes.append(f"run_shell_command → {top_s}")

            if suffixes:
                print(f"- {bug}: {tool_summary} | " + " | ".join(suffixes))
            else:
                print(f"- {bug}: {tool_summary}")

        except Exception as e:
            parse_error = True
            per_bug_tools[bug] = Counter()
            per_bug_args[bug] = {}
            print(f"[WARN] Failed to parse {bug}: {e}", file=sys.stderr)

    # Build LONG rows
    long_rows: List[Tuple[str, str, int, str]] = []
    for bug, tool_counter in per_bug_tools.items():
        args_by_tool = per_bug_args.get(bug, {})
        for fn, total_cnt in sorted(tool_counter.items()):
            arg_counter = args_by_tool.get(fn)
            if arg_counter:
                for arg, cnt in sorted(arg_counter.items()):
                    long_rows.append((bug, fn, cnt, arg))
            else:
                long_rows.append((bug, fn, total_cnt, ""))

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
