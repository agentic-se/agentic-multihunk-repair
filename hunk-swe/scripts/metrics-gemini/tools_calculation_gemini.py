#!/usr/bin/env python3
from __future__ import annotations
import argparse
import json
from pathlib import Path
from typing import Dict, List, Tuple
from collections import Counter, defaultdict
import csv
import sys

# Accept common variants just in case
TOOL_EVENT_MATCHES = (
    "gemini_cli.tool_call",
    "gemini_cli.tool_call.start",
    "gemini_cli.tool_call.end",
)
EVENT_KEYS = ("event.name", "eventName", "event")
FUNC_KEYS  = ("function_name", "functionName")

# function_name -> key to extract from function_args JSON
ARG_KEY_BY_TOOL = {
    "run_shell_command": "command",
    "google_web_search": "query",
    "web_fetch":         "prompt",   # fallback to 'url' if prompt missing
}

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Count tool invocations from cleaned Gemini telemetry JSON files (one array of attributes per bug)."
    )
    p.add_argument("--input-dir", required=True,
                   help="Directory containing cleaned *_logs.json files (one per bug).")
    p.add_argument("--pattern", default="*_logs.json",
                   help="Glob for cleaned files inside input-dir (default: *_logs.json).")
    p.add_argument("--out-long", required=True,
                   help="Path to write long CSV: bug,function_name,count,command.")
    p.add_argument("--out-wide",
                   help="Optional path to write wide CSV: bug plus one column per function_name.")
    return p.parse_args()

def load_cleaned_attributes(path: Path) -> List[dict]:
    """Each cleaned file is a JSON array of 'attributes' dicts (we also tolerate a single dict)."""
    data = json.loads(path.read_text(encoding="utf-8", errors="ignore"))
    if isinstance(data, list):
        return [a for a in data if isinstance(a, dict)]
    elif isinstance(data, dict):
        return [data]
    return []

def get_event_name(attrs: dict) -> str | None:
    for k in EVENT_KEYS:
        v = attrs.get(k)
        if isinstance(v, str):
            return v
    return None

def get_function_name(attrs: dict) -> str | None:
    for k in FUNC_KEYS:
        v = attrs.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return None

def parse_function_args(attrs: dict) -> dict | None:
    """Parse 'function_args' (stringified JSON) into a dict."""
    fa = attrs.get("function_args")
    if not isinstance(fa, str) or not fa.strip():
        return None
    try:
        return json.loads(fa)
    except Exception:
        return None

def get_argument_for_tool(fn: str, attrs: dict) -> str | None:
    """
    Normalized 'argument' for supported tools:
      - run_shell_command -> command
      - google_web_search -> query
      - web_fetch         -> prompt (fallback: url)
    """
    key = ARG_KEY_BY_TOOL.get(fn)
    if not key:
        return None
    parsed = parse_function_args(attrs)
    if not isinstance(parsed, dict):
        return None
    val = parsed.get(key)
    if not isinstance(val, str) or not val.strip():
        if fn == "web_fetch":
            alt = parsed.get("url")
            if isinstance(alt, str) and alt.strip():
                return alt.strip()
        return None
    return val.strip()

def bug_from_filename(path: Path) -> str:
    """Use 'Chart-14' from 'Chart-14_logs.json'. If no *_logs suffix, fallback to stem."""
    stem = path.stem  # e.g., Chart-14_logs
    return stem[:-5] if stem.endswith("_logs") else stem

def count_tools_and_args(attrs_list: List[dict]) -> Tuple[Counter, Dict[str, Counter]]:
    """
    Returns:
      - tool_counts: Counter(function_name -> count)
      - args_by_tool: Dict[function_name -> Counter(argument -> count)]
        (only for tools we know how to extract arguments for)
    """
    tool_counts = Counter()
    args_by_tool: Dict[str, Counter] = defaultdict(Counter)

    for a in attrs_list:
        ev = get_event_name(a) or ""
        if any(ev == m for m in TOOL_EVENT_MATCHES):
            fn = get_function_name(a)
            if not fn:
                continue
            tool_counts[fn] += 1

            arg = get_argument_for_tool(fn, a)
            if arg:
                args_by_tool[fn][arg] += 1

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

    files = sorted(inp.glob(args.pattern))
    if not files:
        print(f"[WARN] No files matched {args.pattern} under {inp}")
    else:
        print(f"Found {len(files)} cleaned logs under {inp}")

    for jf in files:
        bug = bug_from_filename(jf)
        try:
            attrs_list = load_cleaned_attributes(jf)
            tool_counts, args_by_tool = count_tools_and_args(attrs_list)
            per_bug_tools[bug] = tool_counts
            per_bug_args[bug] = args_by_tool

            # Terminal summary
            if tool_counts:
                tool_summary = ", ".join(f"{fn}:{tool_counts[fn]}" for fn in sorted(tool_counts))
            else:
                tool_summary = "(no tool calls found)"

            suffixes = []
            for fn in ("run_shell_command", "google_web_search", "web_fetch"):
                if args_by_tool.get(fn):
                    top = sorted(args_by_tool[fn], key=args_by_tool[fn].get, reverse=True)[:3]
                    top_s = ", ".join(f"{arg}:{args_by_tool[fn][arg]}" for arg in top)
                    suffixes.append(f"{fn} → {top_s}")
            if suffixes:
                print(f"- {bug}: {tool_summary} | " + " | ".join(suffixes))
            else:
                print(f"- {bug}: {tool_summary}")

        except Exception as e:
            parse_error = True
            per_bug_tools[bug] = Counter()
            per_bug_args[bug] = {}
            print(f"[WARN] Failed to parse {jf.name}: {e}", file=sys.stderr)

    # Build LONG rows:
    # For tools with argument extraction, emit one row per argument (in 'command' column).
    # For other tools, emit a single row with empty 'command'.
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
