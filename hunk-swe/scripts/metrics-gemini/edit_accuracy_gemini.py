#!/usr/bin/env python3
from __future__ import annotations
import argparse
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional
import csv
from collections import defaultdict

A_OR_B_PREFIX_RE = re.compile(r'^(?:a/|b/)+')
PLUS_MINUS_HEADER_RE = re.compile(r'^(?:\+\+\+|\-\-\-)\s+')
GIT_DIFF_LINE_RE = re.compile(r'^diff --git a/(.+?)\s+b/(.+?)\s*$')

NO_EDITS_MARKER = "# No tracked changes detected in src/ or source/"

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Compare edited files in *.diff vs buggy_files JSON; export concise CSVs."
    )
    p.add_argument("--bugs-root", required=True,
                   help="Path to directory containing checked-out bug folders like Chart_2, Cli_7, ...")
    p.add_argument("--json", required=True,
                   help="Path to JSON file mapping bug ids to objects containing 'buggy_files'.")
    p.add_argument("--report-summary", required=True,
                   help="Path to write per-bug counts CSV.")
    p.add_argument("--report-details", required=True,
                   help="Path to write per-edit details CSV (bug,status,path).")
    return p.parse_args()

def load_buggy_files_map(json_path: Path) -> Dict[str, Set[str]]:
    """Hunk4J: dict of {bug_id: {"buggy_files": {...}}}.
    HunkSWE: JSONL with one record per line containing `instance_id` + `patch`."""
    text = json_path.read_text(encoding="utf-8")
    result: Dict[str, Set[str]] = {}
    if json_path.suffix == ".jsonl":
        diff_re = re.compile(r"^diff --git a/(\S+) b/", re.MULTILINE)
        for line in text.splitlines():
            if not line.strip():
                continue
            rec = json.loads(line)
            result[rec["instance_id"]] = set(diff_re.findall(rec.get("patch", "")))
        return result
    data = json.loads(text)
    for bug_id, item in data.items():
        files = set()
        buggy = (item or {}).get("buggy_files", {})
        for _, p in buggy.items():
            norm = normalize_to_src_or_source(p)
            if norm:
                files.add(norm)
        result[bug_id] = files
    return result

def normalize_to_src_or_source(path_str: str) -> Optional[str]:
    p = path_str.strip().replace("\\", "/")
    p = p.lstrip("./")
    p = PLUS_MINUS_HEADER_RE.sub("", p).strip()
    p = A_OR_B_PREFIX_RE.sub("", p)
    idx_src = p.find("src/")
    idx_source = p.find("source/")
    candidates = [i for i in (idx_src, idx_source) if i != -1]
    if candidates:
        return p[min(candidates):]
    # HunkSWE / generic: no src/ or source/ prefix to anchor on — accept the
    # stripped path as-is (Python projects use arbitrary roots like
    # `astropy/modeling/separable.py`).
    return p or None

def parse_diff_paths_with_marker(diff_text: str) -> Tuple[Set[str], bool]:
    saw_no_edits = False
    edited: Set[str] = set()

    in_untracked = False  

    for raw_line in diff_text.splitlines():
        line = raw_line.rstrip("\n")

        if line.strip() == NO_EDITS_MARKER:
            saw_no_edits = True
            continue

        if line.strip().startswith("# Untracked source files"):
            in_untracked = True
            continue

        if in_untracked:
            s = line.strip()
            if not s:
                continue
            if s.startswith("#"):
                in_untracked = False
                continue
            if s.startswith("+ ") or s.startswith("+\t"):
                candidate = s[2:].strip()
                norm = normalize_to_src_or_source(candidate)
                if norm:
                    edited.add(norm)
                continue
            in_untracked = False


        m = GIT_DIFF_LINE_RE.match(line)
        if m:
            a_path, b_path = m.group(1), m.group(2)
            for candidate in (a_path, b_path):
                norm = normalize_to_src_or_source(candidate)
                if norm:
                    edited.add(norm)
            continue

        if line.startswith("--- ") or line.startswith("+++ "):
            norm = normalize_to_src_or_source(line)
            if norm:
                edited.add(norm)
            continue

        if "src/" in line or "source/" in line:
            norm = normalize_to_src_or_source(line)
            if norm:
                edited.add(norm)
                continue
            for token in re.split(r"\s+", line):
                if "src/" in token or "source/" in token:
                    norm2 = normalize_to_src_or_source(token)
                    if norm2:
                        edited.add(norm2)

    return edited, saw_no_edits



def read_diff_files(logs_dir: Path) -> List[Path]:
    return sorted(logs_dir.glob("*.diff"))

def collect_bug_dirs(bugs_root: Path) -> List[Path]:
    bug_dirs = []
    for child in sorted(bugs_root.iterdir()):
        if child.is_dir() and (child / "logs").is_dir():
            bug_dirs.append(child)
    return bug_dirs

def analyze_bug(bug_dir: Path) -> Tuple[Set[str], bool]:
    """
    Returns:
      - union_paths: set of normalized edited paths across all diffs
      - saw_no_edits_marker_any: True if any diff had the no-edits marker
    """
    logs_dir = bug_dir / "logs"
    diff_files = read_diff_files(logs_dir)
    if len(diff_files) > 1:
        print(f"[WARN] {bug_dir.name}: found {len(diff_files)} *.diff files; expected 1", file=sys.stderr)

    union_paths: Set[str] = set()
    saw_no_edits_any = False

    for df in diff_files:
        try:
            text = df.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            text = df.read_bytes().decode("utf-8", errors="ignore")

        paths, saw_no_edits = parse_diff_paths_with_marker(text)
        union_paths.update(paths)
        saw_no_edits_any = saw_no_edits_any or saw_no_edits

    return union_paths, saw_no_edits_any

def main() -> None:
    args = parse_args()
    bugs_root = Path(args.bugs_root).expanduser().resolve()
    json_path = Path(args.json).expanduser().resolve()

    if not bugs_root.is_dir():
        print(f"ERROR: --bugs-root not found or not a directory: {bugs_root}", file=sys.stderr)
        sys.exit(2)
    if not json_path.is_file():
        print(f"ERROR: --json not found or not a file: {json_path}", file=sys.stderr)
        sys.exit(2)

    buggy_map = load_buggy_files_map(json_path)
    bug_dirs = collect_bug_dirs(bugs_root)

    # CSV rows
    summary_rows: List[Dict[str, object]] = []
    detail_rows: List[Dict[str, str]] = []

    print(f"\nScanning bugs at: {bugs_root}")
    print(f"Using mapping from: {json_path}\n")

    for bug_dir in bug_dirs:
        bug_id = bug_dir.name
        expected = buggy_map.get(bug_id, set())

        union_paths, saw_no_edits = analyze_bug(bug_dir)

        matches = sorted(union_paths & expected)
        edited_not_in_json = sorted(union_paths - expected)
        json_not_in_diff = sorted(expected - union_paths)

        # ---- Terminal (optional minimal report) ----
        print(f"=== {bug_id} ===")
        print(f"  matches: {len(matches)}, miss(edits not in JSON): {len(edited_not_in_json)}, missed_expected: {len(json_not_in_diff)}")
        if not union_paths and saw_no_edits:
            print("  (no edits made)")

        # ---- DETAILS CSV (concise) ----
        # One row per *edited* path only
        for p in matches:
            detail_rows.append({"bug": bug_id, "status": "match", "path": p})
        for p in edited_not_in_json:
            detail_rows.append({"bug": bug_id, "status": "miss", "path": p})

        # If truly no edits and we saw the marker, write a single no_edits row
        if not union_paths and saw_no_edits:
            detail_rows.append({"bug": bug_id, "status": "no_edits", "path": ""})

        # ---- SUMMARY CSV row ----
        summary_rows.append({
            "bug": bug_id,
            "num_expected": len(expected),
            "correct_edits": len(matches),
            "ote": len(edited_not_in_json),
            "missed_edits": len(json_not_in_diff),
        })

    # ---- Write CSVs ----
    out_summary = Path(args.report_summary).expanduser().resolve()
    out_summary.parent.mkdir(parents=True, exist_ok=True)
    with out_summary.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=[
            "bug",
            "num_expected",
            "correct_edits",
            "ote",
            "missed_edits",
        ])
        w.writeheader()
        w.writerows(summary_rows)
    print(f"Wrote per-bug summary → {out_summary}")

    out_details = Path(args.report_details).expanduser().resolve()
    out_details.parent.mkdir(parents=True, exist_ok=True)
    with out_details.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["bug", "status", "path"])
        w.writeheader()
        w.writerows(detail_rows)
    print(f"Wrote per-edit details → {out_details}")

if __name__ == "__main__":
    main()
