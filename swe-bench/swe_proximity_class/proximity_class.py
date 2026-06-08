#!/usr/bin/env python3
"""
Spatial proximity classification for SWE-bench multi-hunk bugs.

Extracts the enclosing function/class context directly from the @@ hunk
header (the text after the second @@), avoiding any need for AST parsing
or checked-out repositories.

Proximity classes (same as BIRCH/Defects4J):
  - Nucleus:  all hunks in the same file AND same method
  - Cluster:  all hunks in the same file, different methods
  - Orbit:    multiple files, all in the same package (directory)
  - Sprawl:   multiple files, different packages but LCP > cutoff
  - Fragment: multiple files, LCP <= cutoff
"""

import json
import argparse
import csv
import re
import statistics
import math
from itertools import combinations
from pathlib import PurePosixPath


# ── Hunk context extraction ─────────────────────────────────────────────────

def extract_method_from_header(code: str) -> str:
    """
    Parse the @@ header's trailing context to get the enclosing scope.

    Examples:
      '@@ -55,6 +55,13 @@ class BaseTimeSeries(QTable):'  -> 'BaseTimeSeries'
      '@@ -76,9 +83,10 @@ def _check_required_columns(self):' -> '_check_required_columns'
      '@@ -17,9 +17,9 @@'  (no context)  -> '<module>'
    """
    first_line = code.split("\n")[0] if code else ""
    m = re.match(r"^@@ -\d+(?:,\d+)? \+\d+(?:,\d+)? @@\s*(.*)", first_line)
    if not m:
        return "<module>"

    ctx = m.group(1).strip()
    if not ctx:
        return "<module>"

    # Match 'def method_name(' or 'async def method_name('
    func = re.match(r"(?:async\s+)?def\s+(\w+)\s*\(", ctx)
    if func:
        return func.group(1)

    # Match 'class ClassName'
    cls = re.match(r"class\s+(\w+)", ctx)
    if cls:
        return cls.group(1)

    # Fallback: return the raw context string
    return ctx


# ── Hunk representation ─────────────────────────────────────────────────────

class Hunk:
    __slots__ = ("file", "method", "pkg")

    def __init__(self, file_path: str, method: str, pkg: list[str]):
        self.file = file_path
        self.method = method
        self.pkg = pkg


def build_hunks(entry: dict) -> list[Hunk]:
    hunks = []
    for h in entry.get("buggy_hunks", {}).values():
        f = h.get("file", "")
        method = extract_method_from_header(h.get("code", ""))

        # Package = directory components (everything except the filename)
        pkg = list(PurePosixPath(f).parts[:-1]) if "/" in f else []
        hunks.append(Hunk(f, method, pkg))
    return hunks


# ── Proximity predicates ─────────────────────────────────────────────────────

def longest_common_prefix(a: list[str], b: list[str]) -> int:
    depth = 0
    for x, y in zip(a, b):
        if x == y:
            depth += 1
        else:
            break
    return depth


def SF(H):
    return len({h.file for h in H}) == 1


def SM(H):
    return len({h.method for h in H}) == 1


def SP(H):
    return len({tuple(h.pkg) for h in H}) == 1


def LCP_min(H):
    if len(H) < 2:
        return 0
    return min(longest_common_prefix(a.pkg, b.pkg) for a, b in combinations(H, 2))


def classify(H, cutoff):
    if SF(H):
        return "Nucleus" if SM(H) else "Cluster"
    if SP(H):
        return "Orbit"
    return "Sprawl" if LCP_min(H) > cutoff else "Fragment"


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description="Spatial proximity classification")
    ap.add_argument("input_json")
    ap.add_argument("output_csv")
    ap.add_argument("--threshold", type=int, help="Override LCP cutoff for Sprawl")
    args = ap.parse_args()

    data = json.load(open(args.input_json, encoding="utf-8"))

    # Compute default cutoff from median package depth
    pkg_depths = []
    for entry in data.values():
        H = build_hunks(entry)
        pkg_depths.extend(len(h.pkg) for h in H)

    median_depth = statistics.median(pkg_depths) if pkg_depths else 0
    default_cutoff = math.floor(median_depth / 2)
    cutoff = args.threshold if args.threshold is not None else default_cutoff

    print(f"Median module depth = {median_depth}; cutoff = {cutoff}")

    rows = [("issue_id", "proximity_class")]
    class_counts = {}
    for bug_id, entry in data.items():
        H = build_hunks(entry)
        pc = classify(H, cutoff)
        rows.append((bug_id, pc))
        class_counts[pc] = class_counts.get(pc, 0) + 1

    with open(args.output_csv, "w", newline="", encoding="utf-8") as fh:
        csv.writer(fh).writerows(rows)

    print(f"Wrote {len(rows)-1} rows -> {args.output_csv}")
    print("\nDistribution:")
    for cls in ["Nucleus", "Cluster", "Orbit", "Sprawl", "Fragment"]:
        print(f"  {cls:10s}: {class_counts.get(cls, 0)}")


if __name__ == "__main__":
    main()
