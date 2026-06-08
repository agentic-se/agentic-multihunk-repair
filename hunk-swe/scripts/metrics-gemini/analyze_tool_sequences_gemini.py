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
LOGS_DIR = Path.home() / "Desktop" / "logs" / "372_bugs"   # where *_logs.json live
RESULTS_CSV = Path("../results/full_gemini_cli_run.csv").expanduser().resolve()
OUT_DIR     = Path("../results/tools_sequence").expanduser().resolve()

# -------------------- Helpers --------------------
def norm_bug_id(bug: str) -> str:
    """Normalize Chart_14 / Chart-14 to Chart-14."""
    bug = bug.strip()
    bug = bug.replace("_", "-")
    return bug

def categorize_shell_command(cmd: str) -> str:
    """Return ``run_shell_command_<bucket>`` using the shared SWE-bench categorizer."""
    return f"run_shell_command_{categorize_command(cmd)}"

def parse_log_file(log_path: Path) -> List[dict]:
    """Parse a *_logs.json file; extract tool call events sorted by timestamp."""
    with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()

    # split on '}{' boundaries; be lenient with whitespace
    parts = re.split(r'\}\s*\{', content)
    objs = []
    for i, part in enumerate(parts):
        if i > 0:
            part = '{' + part
        if i < len(parts) - 1:
            part = part + '}'
        try:
            obj = json.loads(part)
            objs.append(obj)
        except json.JSONDecodeError:
            # also try NDJSON line-by-line for this part
            for line in part.splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    objs.append(obj)
                except json.JSONDecodeError:
                    pass

    events = []
    for obj in objs:
        if isinstance(obj, dict) and 'attributes' in obj and isinstance(obj['attributes'], dict):
            attrs = obj['attributes']
            if attrs.get('event.name', '') == 'gemini_cli.tool_call':
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
    Returns { 'Chart-14': True/False }
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

def find_logs() -> Dict[str, Path]:
    """
    Map bug id -> path to its *_logs.json (first match).
    Accepts Chart_14 or Chart-14 in filename.
    """
    mapping: Dict[str, Path] = {}
    if not LOGS_DIR.exists():
        print(f"[ERROR] Logs dir not found: {LOGS_DIR}")
        return mapping
    for p in sorted(LOGS_DIR.glob("*_logs.json")):
        # e.g., Chart-14_logs.json or Chart_14_logs.json
        stem = p.stem  # Chart-14_logs
        bug = stem.replace('_logs', '')
        bug = norm_bug_id(bug)
        mapping[bug] = p
    return mapping

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
    print(f"Analyzing logs in {LOGS_DIR}")
    logs_map = find_logs()
    if not logs_map:
        print("[ERROR] No *_logs.json files found.")
        return

    success_map = read_success_map(RESULTS_CSV)
    print(f"Loaded {len(success_map)} bug results from {RESULTS_CSV}")

    all_sequences: Dict[str, List[str]] = {}
    processed = 0
    for bug, log_path in logs_map.items():
        try:
            events = parse_log_file(log_path)
            if not events:
                continue
            seq = extract_tool_sequence(events)
            all_sequences[bug] = seq
            processed += 1
            if processed % 50 == 0:
                print(f"Processed {processed} logs...")
        except Exception as e:
            print(f"[WARN] {bug}: {e}")

    print(f"Total bugs with sequences: {len(all_sequences)}")

    for window in (3, 4, 5):
        all_c, succ_c, fail_c = count_by_bucket(all_sequences, success_map, window)

        write_patterns_csv(all_c,   OUT_DIR / f"tool_sequence_patterns_window_{window}_all.csv",          window)
        write_patterns_csv(succ_c,  OUT_DIR / f"tool_sequence_patterns_window_{window}_successful.csv",   window)
        write_patterns_csv(fail_c,  OUT_DIR / f"tool_sequence_patterns_window_{window}_unsuccessful.csv", window)

        print(f"[OK] Wrote window {window} CSVs to {OUT_DIR}")

if __name__ == "__main__":
    main()
