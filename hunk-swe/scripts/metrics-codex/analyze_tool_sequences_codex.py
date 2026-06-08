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
LOGS_DIR = Path("collected-codex-cli-logs").expanduser().resolve()
RESULTS_CSV = Path("results-hunk4j-codex-cli.csv").expanduser().resolve()
OUT_DIR = Path("results-codex/tools_sequence_codex").expanduser().resolve()

# -------------------- Helpers --------------------
def norm_bug_id(bug: str) -> str:
    """Normalize Chart_14 / Chart-14 to Chart_14."""
    # Keep underscores for consistency with log directory names
    return bug.strip().replace('-', '_')

def categorize_shell_command(cmd: str) -> str:
    """Return ``run_shell_command_<bucket>`` using the shared SWE-bench categorizer."""
    return f"run_shell_command_{categorize_command(cmd)}"

def parse_log_file(log_path: Path) -> List[dict]:
    """Parse a Codex JSONL file; extract tool call events sorted by timestamp."""
    events = []
    try:
        with log_path.open('r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    if isinstance(obj, dict) and obj.get('type') == 'function_call':
                        events.append(obj)
                except json.JSONDecodeError:
                    continue
    except Exception as e:
        print(f"[WARN] Failed to parse {log_path}: {e}")

    # Sort by timestamp if available
    events.sort(key=lambda e: e.get('timestamp', ''))
    return events

def extract_tool_sequence(events: List[dict]) -> List[str]:
    seq = []
    for e in events:
        fn = e.get('name', '')
        if not fn:
            continue

        # Normalize function name
        if fn == 'shell':
            # Parse arguments to categorize shell command
            args_str = e.get('arguments', '{}')
            try:
                args = json.loads(args_str) if isinstance(args_str, str) else args_str
            except json.JSONDecodeError:
                args = {}

            cmd = args.get('command', '')
            # Extract actual command from array format
            if isinstance(cmd, list) and len(cmd) >= 3:
                cmd = cmd[2]  # Get the actual command
            elif isinstance(cmd, list):
                cmd = ' '.join(cmd)

            fn = categorize_shell_command(cmd) if cmd else 'run_shell_command_other'
        elif fn == 'read_file':
            fn = 'read_file'
        elif fn == 'write_file':
            fn = 'write_file'
        elif fn == 'edit_file':
            fn = 'edit_file'

        seq.append(fn)
    return seq

def get_ngrams(sequence: List[str], n: int) -> List[Tuple[str, ...]]:
    if len(sequence) < n:
        return []
    return [tuple(sequence[i:i+n]) for i in range(len(sequence)-n+1)]

def read_success_map(csv_path: Path) -> Dict[str, bool]:
    """
    Reads CSV with columns: bug,pass,...
    Returns { 'Chart_14': True/False }
    """
    mapping: Dict[str, bool] = {}
    if not csv_path.exists():
        print(f"[WARN] Results CSV not found: {csv_path}")
        return mapping

    with csv_path.open(newline='', encoding='utf-8') as f:
        r = csv.DictReader(f)
        for row in r:
            bug = row.get('bug') or row.get('bug_id') or row.get('id')
            if not bug:
                continue
            bug = norm_bug_id(bug)
            raw = (row.get('pass') or '').strip()
            mapping[bug] = raw == 'Yes'  # Match exact format from results CSV
    return mapping

def find_logs() -> Dict[str, Path]:
    """
    Map bug id -> path to its JSONL file (first match).
    """
    mapping: Dict[str, Path] = {}
    if not LOGS_DIR.exists():
        print(f"[ERROR] Logs dir not found: {LOGS_DIR}")
        return mapping

    for bug_dir in sorted(LOGS_DIR.iterdir()):
        if not bug_dir.is_dir():
            continue

        bug = norm_bug_id(bug_dir.name)

        # Find JSONL file
        jsonl_files = list(bug_dir.glob("codex-session-*.jsonl"))
        if jsonl_files:
            mapping[bug] = jsonl_files[0]  # Use first file

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
        print("[ERROR] No JSONL files found.")
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
