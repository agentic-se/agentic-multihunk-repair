#!/usr/bin/env python3
import json
import csv
import re
import sys
from pathlib import Path
from collections import Counter
from typing import List, Dict, Tuple, Optional

# Delegate categorization to the shared SWE-bench module.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agent_command_categorization import categorize_command  # noqa: E402

# -------------------- Config --------------------
DETAILED_CSV = Path("../results/claude_code_results/claude_results/tools_count_detailed_claude.csv").expanduser().resolve()
RESULTS_CSV = Path("../results/claude_code_results/results-hunk4j-claude-code.csv").expanduser().resolve()
OUT_DIR = Path("../results/claude_code_results/claude_results/tools_sequence_claude").expanduser().resolve()

# -------------------- Helpers --------------------
def norm_bug_id(bug: str) -> str:
    """Normalize Chart_14 / Chart-14 / chart_14 to chart_14."""
    bug = bug.strip().lower()
    bug = bug.replace("-", "_")
    return bug

def categorize_bash_command(cmd: str) -> str:
    """Return ``Bash_<bucket>`` using the shared SWE-bench categorizer."""
    return f"Bash_{categorize_command(cmd)}"

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

def parse_log_files(log_dir: Path) -> List[Tuple[str, dict, str]]:
    """
    Parse log files from a bug directory.
    Returns list of (tool_name, tool_input, timestamp) tuples sorted by timestamp.
    """
    events = []

    # Find all jsonl files in the directory
    for log_file in sorted(log_dir.glob("*.jsonl")):
        log_objects = load_jsonl_file(log_file)

        for obj in log_objects:
            # Look for assistant messages with tool_use content
            if obj.get('type') != 'assistant':
                continue

            timestamp = obj.get('timestamp', '')
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
                        events.append((tool_name, tool_input, timestamp))

    # Sort by timestamp
    events.sort(key=lambda e: e[2])
    return events

def extract_tool_sequence(events: List[Tuple[str, dict, str]]) -> List[str]:
    """Extract tool sequence, categorizing Bash commands."""
    seq = []
    for tool_name, tool_input, _ in events:
        if tool_name == 'Bash':
            # Categorize based on command
            cmd = tool_input.get('command', '')
            tool_name = categorize_bash_command(cmd) if cmd else 'Bash_other'
        seq.append(tool_name)
    return seq

def get_ngrams(sequence: List[str], n: int) -> List[Tuple[str, ...]]:
    if len(sequence) < n:
        return []
    return [tuple(sequence[i:i+n]) for i in range(len(sequence)-n+1)]

def read_success_map(csv_path: Path) -> Dict[str, bool]:
    """
    Reads CSV with columns: bug,compiled,tests_pass,failed_tests_count,claude_exit_code,duration_s
    Returns { 'chart-14': True/False }
    """
    mapping: Dict[str, bool] = {}
    with csv_path.open(newline='', encoding='utf-8') as f:
        r = csv.DictReader(f)
        for row in r:
            bug = row.get('bug') or row.get('bug_id') or row.get('id')
            if not bug:
                continue
            bug = norm_bug_id(bug)
            # Check tests_pass column for Claude Code results
            raw = (row.get('tests_pass') or row.get('pass') or '').strip().lower()
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
