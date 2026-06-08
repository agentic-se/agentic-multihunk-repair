#!/usr/bin/env python3
import csv
import argparse
from collections import defaultdict, Counter
from pathlib import Path

def normalize_bug_id(bug: str) -> str:
    """Normalize bug IDs so Chart-2, Chart_2, chart-2, chart_2 all map consistently."""
    b = (bug or "").strip().lower()
    b = b.replace("-", "_")
    return b

def parse_bool(val: str) -> bool:
    v = (val or "").strip().lower()
    return v in {"yes", "y", "true", "t", "1", "pass", "passed"}

def load_results(results_csv):
    """
    Expected header (case-insensitive acceptable):
      bug, pass, test_fail, compile_fail, failed_tests
    Only 'bug' and 'pass' are needed.
    """
    results = {}
    with open(results_csv, newline='') as f:
        reader = csv.DictReader(f)
        # make header keys case-insensitive
        field_map = {k.lower(): k for k in reader.fieldnames or []}
        if "bug" not in field_map or "pass" not in field_map:
            raise ValueError(f"results CSV must contain 'bug' and 'pass' headers. Found: {reader.fieldnames}")
        for row in reader:
            bug_raw = row[field_map["bug"]]
            passed_raw = row[field_map["pass"]]
            bug = normalize_bug_id(bug_raw)
            results[bug] = parse_bool(passed_raw)
    return results

def load_divergence(divergence_csv):
    """
    Accepts either:
      - No header: bug,hunk_count,divergence
      - Or with header containing 'bug' and a float column named like 'divergence' or the 3rd column.
    """
    divergences = {}
    with open(divergence_csv, newline='') as f:
        sniffer = csv.Sniffer()
        sample = f.read(2048)
        f.seek(0)
        has_header = sniffer.has_header(sample)
        reader = csv.reader(f)
        header = None
        if has_header:
            header = next(reader, None)
        for row in reader:
            if not row or len(row) < 2:
                continue
            if header:
                # Try by name first
                h_lower = [c.strip().lower() for c in header]
                try:
                    bug_idx = h_lower.index("bug")
                except ValueError:
                    bug_idx = 0
                # find a float-ish column preference order
                div_idx = None
                for name in ("divergence", "avg_divergence", "hunk_divergence", "div"):
                    if name in h_lower:
                        div_idx = h_lower.index(name)
                        break
                if div_idx is None:
                    # fallback: try 3rd column if present
                    div_idx = 2 if len(row) >= 3 else len(row) - 1
            else:
                bug_idx = 0
                div_idx = 2 if len(row) >= 3 else 1
            bug = normalize_bug_id(row[bug_idx])
            try:
                divergences[bug] = float(row[div_idx])
            except (ValueError, IndexError, TypeError):
                # skip non-numeric lines / bad rows
                continue
    return divergences

def load_proximity(proximity_csv):
    """
    Accepts either:
      - No header: bug, proximity_class
      - Or header with 'bug' and a class column ('proximity', 'class', 'proximity_class').
    """
    proximity = {}
    with open(proximity_csv, newline='') as f:
        sniffer = csv.Sniffer()
        sample = f.read(2048)
        f.seek(0)
        has_header = sniffer.has_header(sample)
        reader = csv.reader(f)
        header = None
        if has_header:
            header = next(reader, None)
        for row in reader:
            if not row or len(row) < 2:
                continue
            if header:
                h_lower = [c.strip().lower() for c in header]
                try:
                    bug_idx = h_lower.index("bug")
                except ValueError:
                    bug_idx = 0
                # find class column
                cls_idx = None
                for name in ("proximity", "proximity_class", "class", "cls"):
                    if name in h_lower:
                        cls_idx = h_lower.index(name)
                        break
                if cls_idx is None:
                    cls_idx = 1
            else:
                bug_idx, cls_idx = 0, 1
            bug = normalize_bug_id(row[bug_idx])
            cls = row[cls_idx].strip()
            if cls:
                proximity[bug] = cls
    return proximity

def main(results_csv, divergence_csv, proximity_csv, output_csv=None):
    results = load_results(results_csv)
    divergences = load_divergence(divergence_csv)
    proximity = load_proximity(proximity_csv)

    # Diagnostics
    set_results = set(results.keys())
    set_divs   = set(divergences.keys())
    set_prox   = set(proximity.keys())
    overlap_div = set_results & set_divs
    overlap_prox = set_results & set_prox

    if not overlap_div:
        print("[WARN] No overlap between results and divergence CSVs after normalization.")
        print(f"  results examples: {sorted(list(set_results))[:5]}")
        print(f"  divergence examples: {sorted(list(set_divs))[:5]}")
    if not overlap_prox:
        print("[WARN] No overlap between results and proximity CSVs after normalization.")
        print(f"  results examples: {sorted(list(set_results))[:5]}")
        print(f"  proximity examples: {sorted(list(set_prox))[:5]}")

    # Average divergences by pass/fail
    passed_vals, failed_vals = [], []
    for bug in overlap_div:
        if results.get(bug, False):
            passed_vals.append(divergences[bug])
        else:
            failed_vals.append(divergences[bug])

    avg_pass = sum(passed_vals) / len(passed_vals) if passed_vals else 0.0
    avg_fail = sum(failed_vals) / len(failed_vals) if failed_vals else 0.0

    print("=== Average Divergence (Claude Code) ===")
    print(f"Passed: {avg_pass:.4f} ({len(passed_vals)} bugs using overlap={len(overlap_div)})")
    print(f"Not Passed: {avg_fail:.4f} ({len(failed_vals)} bugs using overlap={len(overlap_div)})\n")

    # Proximity class pass/fail tallies (only for bugs present in results+proximity)
    prox_counts = defaultdict(lambda: {"pass": 0, "fail": 0})
    for bug in set_results & set_prox:
        cls = proximity[bug]
        if results[bug]:
            prox_counts[cls]["pass"] += 1
        else:
            prox_counts[cls]["fail"] += 1

    print("=== Proximity Class Outcomes (Claude Code) ===")
    if not prox_counts:
        print("(no overlapping bugs with proximity classes)")
    else:
        for cls, counts in sorted(prox_counts.items()):
            print(f"{cls}: passed={counts['pass']}, not_passed={counts['fail']}")

    # Optional CSV output
    if output_csv:
        outp = Path(output_csv)
        outp.parent.mkdir(parents=True, exist_ok=True)
        with open(outp, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["metric", "value"])
            w.writerow(["avg_divergence_passed", f"{avg_pass:.6f}"])
            w.writerow(["avg_divergence_not_passed", f"{avg_fail:.6f}"])
            w.writerow(["count_passed_divergence", len(passed_vals)])
            w.writerow(["count_not_passed_divergence", len(failed_vals)])
            for cls, counts in sorted(prox_counts.items()):
                w.writerow([f"proximity::{cls}::passed", counts["pass"]])
                w.writerow([f"proximity::{cls}::not_passed", counts["fail"]])
        print(f"\n[OK] Wrote summary → {outp}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Compute avg divergence by pass/fail and proximity class counts for Claude Code.")
    parser.add_argument("--results", required=True, help="CSV with columns: bug,pass,... (header required)")
    parser.add_argument("--divergence", required=True, help="CSV with bug and a divergence float column")
    parser.add_argument("--proximity", required=True, help="CSV with bug and proximity class")
    parser.add_argument("--output", help="Optional path to write a summary CSV")
    args = parser.parse_args()
    main(args.results, args.divergence, args.proximity, args.output)
