"""
Hunk-Divergence for SWE-bench Verified (Python).

Port of the Defects4J hunk_divergence.py from Java (javalang / JavaParser)
to Python, using the built-in `ast` module for structural distance.

Metrics per hunk pair:
    D_lex  - lexical divergence  (1 - BLEU between patch lines)
    D_ast  - AST-node distance   (LCA path distance, normalised by tree diameter)
    D_dir  - directory distance  (path-segment distance between files)

    pairDiv   = D_lex x (D_ast + γ x D_dir)     γ = 1 same-file, 2 cross-file
    normalised = pairDiv / (1 + γ)
    divergence = ln(n) x mean(normalised)         n = number of hunks

Algorithm 1 of the paper initializes γ ← 1 and only overwrites it to 2
in the cross-file branch (line 21). Same-file pairs therefore divide by
1 + γ = 2, downweighting them relative to cross-file pairs (which divide
by 3). Cap is 0.5 for same-file, 1.0 for cross-file — Div(P) ∈ [0, ln n].
"""

from __future__ import annotations

import argparse
import ast
import csv
import itertools
import json
import math
import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from evaluate_bleu import compute_bleu_score


# ── AST helpers (Python `ast` module) ────────────────────────────────────────

def _build_parent_map(tree: ast.AST) -> Dict[int, ast.AST]:
    """Walk an AST and return id(child) → parent mapping."""
    parents: Dict[int, ast.AST] = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parents[id(child)] = node
    return parents


def _node_depth(node: ast.AST, parents: Dict[int, ast.AST]) -> int:
    d = 0
    n = node
    while id(n) in parents:
        d += 1
        n = parents[id(n)]
    return d


def _lca(u: ast.AST, v: ast.AST,
         parents: Dict[int, ast.AST]) -> Optional[ast.AST]:
    """Lowest common ancestor of two AST nodes."""
    seen: set = set()
    x: Optional[ast.AST] = u
    while x is not None:
        seen.add(id(x))
        x = parents.get(id(x))
    y: Optional[ast.AST] = v
    while y is not None:
        if id(y) in seen:
            return y
        y = parents.get(id(y))
    return None


def _ast_node_distance(u: ast.AST, v: ast.AST,
                       parents: Dict[int, ast.AST]) -> int:
    """Path distance between two nodes via their LCA."""
    w = _lca(u, v, parents)
    du = _node_depth(u, parents)
    dv = _node_depth(v, parents)
    dw = _node_depth(w, parents) if w is not None else 0
    return du + dv - 2 * dw


def _buggy_subtree_root(tree: ast.AST, start: int, end: int,
                        parents: Dict[int, ast.AST]) -> ast.AST:
    best_span: Optional[int] = None
    best_node: Optional[ast.AST] = None

    # DFS pre-order via stack: push children in reverse so the
    # left-most child is popped first, matching JavaParser preorder.
    stack: List[ast.AST] = [tree]
    while stack:
        node = stack.pop()
        ns = getattr(node, "lineno", None)
        ne = getattr(node, "end_lineno", None)
        if ns is not None and ne is not None and ns <= start and ne >= end:
            span = ne - ns
            if best_span is None or span < best_span:
                best_span = span
                best_node = node
        children = list(ast.iter_child_nodes(node))
        for child in reversed(children):
            stack.append(child)

    return best_node if best_node is not None else tree


# Python's `ast` module reuses a *single* shared instance for marker
# nodes like `Load`, `Store`, `Del`, `Add`, `Sub`, `Eq`, `Lt`, `And`,
# `USub`, etc. JavaParser has no equivalent — every Java AST node is a
# distinct object. If we leave these singletons in the adjacency map,
# one shared `Store` becomes a "shortcut" linking every assignment in
# the file (its neighbour list contains every `Name` target tree-wide),
# which silently collapses BFS distances and corrupts the diameter.
#
# These nodes carry type/marker information only — no structural depth —
# so excluding them from the adjacency matches the spirit of the Java
# code and the paper's `treeDiameter` definition.
_AST_SHARED_SINGLETONS = (
    ast.expr_context,
    ast.operator,
    ast.boolop,
    ast.cmpop,
    ast.unaryop,
)


def _build_adjacency(tree: ast.AST) -> Dict[int, List[ast.AST]]:
    """Undirected parent↔child adjacency map keyed by id(node).

    Direct port of MethodLineExtractor.buildAdjacency: every parent-child
    edge is recorded in both directions so BFS can traverse the tree as
    an undirected graph. Shared singleton marker nodes (Load/Store/Add/
    Eq/...) are skipped — see `_AST_SHARED_SINGLETONS` above for why.
    """
    adj: Dict[int, List[ast.AST]] = {}
    for node in ast.walk(tree):
        if isinstance(node, _AST_SHARED_SINGLETONS):
            continue
        adj.setdefault(id(node), [])
        for child in ast.iter_child_nodes(node):
            if isinstance(child, _AST_SHARED_SINGLETONS):
                continue
            adj.setdefault(id(child), []).append(node)
            adj[id(node)].append(child)
    return adj


def _bfs_farthest(start: ast.AST,
                  adj: Dict[int, List[ast.AST]]) -> Tuple[ast.AST, int]:
    """BFS from `start`; return (farthest reachable node, its distance).

    Direct port of MethodLineExtractor.bfsFarthest.
    """
    from collections import deque
    dist: Dict[int, int] = {id(start): 0}
    queue = deque([start])
    far_node: ast.AST = start
    far_dist = 0
    while queue:
        u = queue.popleft()
        du = dist[id(u)]
        if du > far_dist:
            far_node, far_dist = u, du
        for v in adj.get(id(u), ()):
            if id(v) not in dist:
                dist[id(v)] = du + 1
                queue.append(v)
    return far_node, far_dist


def _subtree_diameter(tree: ast.AST,
                      parents: Dict[int, ast.AST]) -> int:
    """Exact tree diameter via two BFS passes — O(N).
    """
    if not list(ast.iter_child_nodes(tree)):
        return 1

    adj = _build_adjacency(tree)

    # First BFS from the root to find one endpoint of the diameter
    far, _ = _bfs_farthest(tree, adj)
    # Second BFS from that endpoint gives the diameter
    _, diameter = _bfs_farthest(far, adj)
    return diameter or 1


# ── Source file helpers ───────────────────────────────────────────────────────

def _read_source_file(work_dir: Path, instance_id: str,
                      file_path: str) -> Optional[str]:
    """Read a source file from a checked-out SWE-bench instance workspace."""
    fp = work_dir / instance_id / file_path
    if not fp.exists():
        return None
    try:
        return fp.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return None


# ── Patch parsing ────────────────────────────────────────────────────────────

def parse_patch_hunks(patch: str) -> List[Dict]:
    """
    Parse a unified diff into per-hunk dicts with buggy/fixed lines.
    Returns list of {file, start_line, end_line, buggy: [...], fixed: [...]}.
    """
    if not patch or not patch.strip():
        return []

    file_sections = re.split(r"(?=^diff --git )", patch, flags=re.MULTILINE)
    file_sections = [s for s in file_sections if s.strip()]

    hunks = []
    for section in file_sections:
        match = re.search(r"^diff --git a/.+? b/(.+)$", section, re.MULTILINE)
        if not match:
            match = re.search(r"^\+\+\+ b/(.+)$", section, re.MULTILINE)
        file_path = match.group(1) if match else "<unknown>"

        parts = re.split(r"(^@@[^\n]*)", section, flags=re.MULTILINE)
        i = 1
        while i < len(parts) - 1:
            header = parts[i]
            body = parts[i + 1] if i + 1 < len(parts) else ""
            i += 2

            m = re.match(r"^@@ -(\d+)(?:,(\d+))? \+", header)
            if not m:
                continue
            start = int(m.group(1))
            count = int(m.group(2)) if m.group(2) is not None else 1
            end = start + count - 1

            buggy_lines, fixed_lines = [], []
            for line in body.splitlines():
                if line.startswith("-") and not line.startswith("---"):
                    buggy_lines.append(line[1:])
                elif line.startswith("+") and not line.startswith("+++"):
                    fixed_lines.append(line[1:])

            hunks.append({
                "file": file_path,
                "start_line": start,
                "end_line": end,
                "buggy": buggy_lines,
                "fixed": fixed_lines,
            })

    return hunks


# ── AST metrics for a single source file ─────────────────────────────────────

def compute_ast_metrics_for_file(
    source: str,
    hunk_ranges: List[Tuple[int, int, int]],
) -> Tuple[int, Dict[str, int]]:
    """
    Parse a Python source file and compute AST metrics.

    Args:
        source: full Python source text
        hunk_ranges: list of (hunk_index, start_line, end_line)

    Returns:
        (diameter, {f"{i}_{j}": ast_distance, ...})
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return 1, {}

    parents = _build_parent_map(tree)
    diameter = _subtree_diameter(tree, parents)

    # For each hunk, take the LCA of all AST nodes starting in its range
    hunk_roots: Dict[int, ast.AST] = {}
    for idx, start, end in hunk_ranges:
        hunk_roots[idx] = _buggy_subtree_root(tree, start, end, parents)

    # Pairwise AST distance between hunk roots
    pairs: Dict[str, int] = {}
    for (i, _, _), (j, _, _) in itertools.combinations(hunk_ranges, 2):
        dist = _ast_node_distance(hunk_roots[i], hunk_roots[j], parents)
        pairs[f"{i}_{j}"] = dist

    return diameter, pairs


# ── Core divergence computation ──────────────────────────────────────────────

def compute_metrics_for_bug(
    bug_id: str,
    hunks: List[Dict],
    ast_metrics: Dict[str, Dict],
) -> Tuple[float, List[List]]:
    """
    Compute hunk divergence for a single bug.

    Args:
        bug_id: instance_id
        hunks: list of hunk dicts with file, patch_lines, hunk_id
        ast_metrics: {file_path: {diameter: int, pairs: {i_j: dist}}}

    Returns:
        (divergence_score, [[i, j, D_lex, D_ast, D_dir, normalised], ...])
    """
    n = len(hunks)
    if n < 2:
        return 0.0, []

    sum_norm = 0.0
    pair_rows: List[List] = []

    for i, j in itertools.combinations(range(n), 2):
        hi, hj = hunks[i], hunks[j]

        # Lexical divergence
        D_lex = 1.0 - compute_bleu_score(
            "\n".join(hi["patch_lines"]),
            "\n".join(hj["patch_lines"]),
        )

        if hi["file"] == hj["file"]:
            # Same file: use AST distance. γ stays at its initial value
            # of 1 (Algorithm 1, Line 1) — only the cross-file branch
            # overwrites it to 2 (Line 21). This downweights same-file
            # pairs by maxDiv = 1 + 1 = 2.
            fm = ast_metrics.get(hi["file"], {})
            diam = fm.get("diameter", 1)
            key = f"{hi['hunk_id']}_{hj['hunk_id']}"
            raw_ast = fm.get("pairs", {}).get(key, 0)
            if diam > 0:
                D_ast = math.log1p(raw_ast) / math.log1p(diam)
            else:
                D_ast = 0.0
            gamma = 1.0
            D_dir = 0.0
        else:
            # Cross-file: max AST distance, use directory distance
            gamma = 2.0
            D_ast = 1.0
            seg_i = hi["file"].split("/")
            seg_j = hj["file"].split("/")

            common = 0
            for a, b in zip(seg_i, seg_j):
                if a == b:
                    common += 1
                else:
                    break

            maxlen = max(len(seg_i), len(seg_j))
            D_dir = 1.0 - (common / maxlen) if maxlen > 0 else 1.0

        pairDiv = D_lex * (D_ast + gamma * D_dir)
        maxDiv = 1.0 + gamma
        normalised = pairDiv / maxDiv

        sum_norm += normalised
        pair_rows.append([
            i, j,
            f"{D_lex:.4f}",
            f"{D_ast:.4f}",
            f"{D_dir:.4f}",
            f"{normalised:.4f}",
        ])

    avg_pair = (2.0 * sum_norm) / (n * (n - 1))
    divergence = math.log(n) * avg_pair
    return divergence, pair_rows


# ── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compute Hunk-Divergence for SWE-bench Verified multi-hunk bugs"
    )
    parser.add_argument(
        "--multihunk-json",
        default="../swe_bench_verified/multihunk_swe_bench_verified.json",
        help="JSON with multi-hunk bug data (output of analyze_multihunk.py)",
    )
    parser.add_argument(
        "--swe-bench-jsonl",
        default="../swe_bench_verified/swe_bench.jsonl",
        help="SWE-bench JSONL with repo, base_commit, and patch fields",
    )
    parser.add_argument(
        "--work-dir",
        default="~/WORK_DIR",
        help="Root directory containing checked-out SWE-bench instance workspaces",
    )
    parser.add_argument(
        "--out",
        default="total_hunk_divergence_results.csv",
    )
    parser.add_argument(
        "--pair-out",
        default="pairwise_hunk_divergence_results.csv",
    )
    args = parser.parse_args()

    # Load multi-hunk bug metadata
    multihunk = json.load(open(args.multihunk_json, encoding="utf-8"))

    # Build lookup: instance_id → {repo, base_commit, patch}
    swe_lookup: Dict[str, Dict] = {}
    with open(args.swe_bench_jsonl, encoding="utf-8") as f:
        for line in f:
            rec = json.loads(line.strip())
            iid = rec["instance_id"]
            if iid in multihunk:
                swe_lookup[iid] = {
                    "repo": rec["repo"],
                    "base_commit": rec["base_commit"],
                    "patch": rec["patch"],
                }

    work_dir = Path(args.work_dir).expanduser()

    per_bug_rows: List[List] = []
    per_pair_rows: List[List] = []

    for bug_id, entry in multihunk.items():
        swe_rec = swe_lookup.get(bug_id)
        if swe_rec is None:
            print(f"  SKIP {bug_id} — not found in JSONL")
            continue

        buggy_hunks = entry.get("buggy_hunks", {})
        if len(buggy_hunks) < 2:
            print(f"  SKIP {bug_id} — fewer than 2 hunks ({len(buggy_hunks)})")
            continue

        # Parse patch for buggy/fixed lines
        patch_hunks = parse_patch_hunks(swe_rec["patch"])

        # Group hunks by file for AST computation
        hunks_by_file: Dict[str, List[Tuple[int, int, int]]] = {}
        hunk_list: List[Dict] = []

        for hunk_id_str, h in buggy_hunks.items():
            hunk_id = int(hunk_id_str)
            file_rel = h["file"]
            start = h["start_line"]
            end = h["end_line"]

            # Match patch lines from parsed patch
            plines: List[str] = []
            if hunk_id < len(patch_hunks):
                ph = patch_hunks[hunk_id]
                plines = ph["buggy"] + ph["fixed"]

            hunk_list.append({
                "file": file_rel,
                "patch_lines": plines,
                "hunk_id": hunk_id,
            })

            hunks_by_file.setdefault(file_rel, []).append(
                (hunk_id, start, end)
            )

        # Compute AST metrics per file (only for files with ≥2 hunks)
        ast_metrics: Dict[str, Dict] = {}
        for file_rel, ranges in hunks_by_file.items():
            if len(ranges) < 2:
                continue
            source = _read_source_file(work_dir, bug_id, file_rel)
            if source is None:
                print(f"  WARN {bug_id}: cannot read {file_rel}")
                ast_metrics[file_rel] = {"diameter": 1, "pairs": {}}
                continue
            diameter, pairs = compute_ast_metrics_for_file(source, ranges)
            ast_metrics[file_rel] = {"diameter": diameter, "pairs": pairs}

        # Compute divergence
        div, pairs = compute_metrics_for_bug(bug_id, hunk_list, ast_metrics)

        per_bug_rows.append([bug_id, len(hunk_list), f"{div:.4f}"])
        for row in pairs:
            per_pair_rows.append([bug_id] + row)

        print(f"{bug_id:50s}  ({len(hunk_list)} hunks)  divergence = {div:.4f}")

    # Write CSVs
    with open(args.out, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["bug_id", "hunk_count", "divergence"])
        w.writerows(per_bug_rows)

    with open(args.pair_out, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow([
            "bug_id", "hunk_i", "hunk_j",
            "lexical_distance", "ast_distance",
            "file_distance", "pair_divergence",
        ])
        w.writerows(per_pair_rows)

    print(f"\n✓ per-bug  → {args.out}  ({len(per_bug_rows)} bugs)")
    print(f"✓ per-pair → {args.pair_out}  ({len(per_pair_rows)} pairs)")


if __name__ == "__main__":
    main()
