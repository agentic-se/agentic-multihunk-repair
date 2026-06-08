#!/usr/bin/env python3
import json
import csv
import re
import sys
from pathlib import Path
from collections import Counter
from typing import List, Dict, Tuple, Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agent_command_categorization import categorize_command

# -------------------- Config --------------------
DETAILED_CSV = Path("../results/qwen_code_results/qwen_results/tools_count_detailed_qwen.csv").expanduser().resolve()
RESULTS_CSV = Path("../results/qwen_code_results/results-hunk4j-qwen-code.csv").expanduser().resolve()
OUT_DIR = Path("../results/qwen_code_results/qwen_results/tools_sequence_qwen").expanduser().resolve()

# -------------------- Helpers --------------------
def norm_bug_id(bug: str) -> str:
    """Normalize Chart_14 / Chart-14 / chart_14 to chart_14."""
    bug = bug.strip().lower()
    bug = bug.replace("-", "_")
    return bug

def categorize_shell_command(cmd: str) -> str:
    """Return ``run_shell_command_<bucket>`` using the shared SWE-bench categorizer."""
    return f"run_shell_command_{categorize_command(cmd)}"

def parse_log_file(log_path: Path) -> List[dict]:
    """Parse a qwen*.json file; extract tool call events sorted by timestamp."""
    with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()

    # Parse using NDJSON approach
    from json import JSONDecoder
    objects = []
    dec = JSONDecoder()
    i, n = 0, len(content)
    while i < n:
        while i < n and content[i].isspace():
            i += 1
        if i >= n:
            break
        try:
            obj, end = dec.raw_decode(content, i)
            if isinstance(obj, dict):
                objects.append(obj)
            i = end
        except:
            i += 1

    events = []
    for obj in objects:
        if isinstance(obj, dict) and 'attributes' in obj and isinstance(obj['attributes'], dict):
            attrs = obj['attributes']
            event_name = attrs.get('event.name', '')
            # For Qwen logs, the event name is "qwen-code.tool_call"
            if event_name in ('qwen-code.tool_call', 'gemini_cli.tool_call'):
                events.append(attrs)

    # Sort by timestamp string (ISO-8601 sorts lexicographically fine)
    events.sort(key=lambda e: e.get('event.timestamp', ''))
    return events

def extract_tool_sequence(events: List[dict]) -> List[str]:
    seq = []
    for e in events:
        fn = e.get('function_name', '')
        if not fn:
            continue
        if fn == 'run_shell_command':
            arg_str = e.get('function_args', '{}')
            try:
                args = json.loads(arg_str) if isinstance(arg_str, str) else (arg_str or {})
            except json.JSONDecodeError:
                args = {}
            cmd = args.get('command', '')
            fn = categorize_shell_command(cmd) if cmd else 'run_shell_command_other'
        seq.append(fn)
    return seq

def get_ngrams(sequence: List[str], n: int) -> List[Tuple[str, ...]]:
    if len(sequence) < n:
        return []
    return [tuple(sequence[i:i+n]) for i in range(len(sequence)-n+1)]

def read_success_map(csv_path: Path) -> Dict[str, bool]:
    """
    Reads CSV with columns: bug,pass,test_fail,compile_fail,failed_tests
    Returns { 'Chart_14': True/False }
    """
    mapping: Dict[str, bool] = {}
    with csv_path.open(newline='', encoding='utf-8') as f:
        r = csv.DictReader(f)
        for row in r:
            bug = row.get('bug') or row.get('bug_id') or row.get('id')
            if not bug:
                continue
            bug = norm_bug_id(bug)
            raw = (row.get('pass') or '').strip().lower()
            mapping[bug] = raw in ('yes', 'true', 'pass', 'passed', '1')
    return mapping

def load_tool_sequences_from_csv(csv_path: Path) -> Dict[str, List[str]]:
    """
    Load tool sequences from tools_count_detailed CSV.
    Returns { 'chart_14': ['READ', 'TEST', 'WRITE', ...] }
    """
    sequences: Dict[str, List[str]] = {}

    with csv_path.open('r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            bug = norm_bug_id(row['bug'])
            category = row['category']

            if bug not in sequences:
                sequences[bug] = []
            sequences[bug].append(category)

    return sequences

def count_by_bucket(seqs: Dict[str, List[str]],
                    success_map: Dict[str, bool],
                    window: int) -> Tuple[Counter, Counter, Counter]:
    """
    Returns (all_counter, success_counter, fail_counter) for n-grams of size `window`.
    """
    all_c = Counter()
    succ_c = Counter()
    fail_c = Counter()
    for bug, seq in seqs.items():
        grams = get_ngrams(seq, window)
        if not grams:
            continue
        all_c.update(grams)
        ok = success_map.get(bug)
        if ok is True:
            succ_c.update(grams)
        elif ok is False:
            fail_c.update(grams)
        # if ok is None (bug not in results CSV), it contributes only to "all"
    return all_c, succ_c, fail_c

def write_patterns_csv(counter: Counter, out_path: Path, window_size: int):
    rows = []
    for ngram, freq in counter.most_common():
        rows.append({
            'window_size': window_size,
            'tool_sequence': " -> ".join(ngram),
            'frequency': freq
        })
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open('w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=['window_size', 'tool_sequence', 'frequency'])
        w.writeheader()
        w.writerows(rows)

# -------------------- Main --------------------
def main():
    print(f"Loading tool sequences from {DETAILED_CSV}")
    if not DETAILED_CSV.exists():
        print(f"[ERROR] Detailed CSV not found: {DETAILED_CSV}")
        return

    all_sequences = load_tool_sequences_from_csv(DETAILED_CSV)
    print(f"Loaded sequences for {len(all_sequences)} bugs")

    if not RESULTS_CSV.exists():
        print(f"[ERROR] Results CSV not found: {RESULTS_CSV}")
        return

    success_map = read_success_map(RESULTS_CSV)
    print(f"Loaded {len(success_map)} bug results from {RESULTS_CSV}")

    # Count successful/unsuccessful bugs
    successful_bugs = [bug for bug, passed in success_map.items() if passed]
    unsuccessful_bugs = [bug for bug, passed in success_map.items() if not passed]
    print(f"  Successful: {len(successful_bugs)}, Unsuccessful: {len(unsuccessful_bugs)}")

    for window in (3, 4, 5):
        all_c, succ_c, fail_c = count_by_bucket(all_sequences, success_map, window)

        write_patterns_csv(all_c,   OUT_DIR / f"tool_sequence_patterns_window_{window}_all.csv",          window)
        write_patterns_csv(succ_c,  OUT_DIR / f"tool_sequence_patterns_window_{window}_successful.csv",   window)
        write_patterns_csv(fail_c,  OUT_DIR / f"tool_sequence_patterns_window_{window}_unsuccessful.csv", window)

        print(f"[OK] Window {window}: all={len(all_c)}, successful={len(succ_c)}, unsuccessful={len(fail_c)}")

if __name__ == "__main__":
    main()
