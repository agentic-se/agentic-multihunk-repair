#!/usr/bin/env python3
"""Regenerate tab:proximity_class:hunk-poly from hunk-poly/ source CSVs.

Reads proximity_class.csv and hunk_divergence.csv (the same inputs the figure
scripts consume), computes per-class counts and mean divergence for the three
subsets (Hunk4J, HunkSWE, PolyHunk), and prints the LaTeX table to stdout.

Re-running keeps the manuscript table in lockstep with the source data — any
drift in the inputs is caught here rather than going stale silently in
evaluation.tex.
"""
from __future__ import annotations

import csv
import statistics
from pathlib import Path

HUNK_POLY = Path(__file__).resolve().parent
DIVERGENCE_CSV = HUNK_POLY / "hunk_divergence.csv"
PROXIMITY_CSV = HUNK_POLY / "proximity_class.csv"

# Increasing dispersion; the table reads top-down by this axis, not alphabetical.
PROXIMITY_ORDER = ["Nucleus", "Cluster", "Orbit", "Sprawl", "Fragment"]


def load():
    div = {}
    with DIVERGENCE_CSV.open() as f:
        for row in csv.DictReader(f):
            div[row["bug_id"]] = float(row["divergence"])
    prox = {}
    with PROXIMITY_CSV.open() as f:
        for row in csv.DictReader(f):
            prox[row["bug_id"]] = row["proximity_class"]
    assert set(div) == set(prox), set(div) ^ set(prox)
    return div, prox


def stats_by_class(bug_ids, div, prox):
    out = {}
    for cls in PROXIMITY_ORDER:
        members = [b for b in bug_ids if prox[b] == cls]
        out[cls] = (len(members), statistics.fmean(div[b] for b in members) if members else 0.0)
    return out


def render(hunk4j, hunkswe, polyhunk):
    body = "\n".join(
        f"  {cls:<8} & {hunk4j[cls][0]:<3} & {hunk4j[cls][1]:.4f} & "
        f"{hunkswe[cls][0]:<3} & {hunkswe[cls][1]:.4f} & "
        f"{polyhunk[cls][0]:<3} & {polyhunk[cls][1]:.4f} \\\\"
        for cls in PROXIMITY_ORDER
    )

    n_h = sum(c for c, _ in hunk4j.values())
    n_s = sum(c for c, _ in hunkswe.values())
    n_p = sum(c for c, _ in polyhunk.values())

    return rf"""\begin{{table}}[t]
\color{{blue}}
\scriptsize
\caption{{\color{{blue}} Spatial proximity class and mean hunk divergence on \benchmarkdataset, broken down by language subset.}}
\label{{tab:proximity_class:hunk-poly}}
\centering
\begin{{tabular}}{{l|cc|cc|cc}}
\toprule
 & \multicolumn{{2}}{{c|}}{{\textbf{{\hunkdefectsforj}} ({n_h})}} & \multicolumn{{2}}{{c|}}{{\textbf{{\hunkswe}} ({n_s})}} & \multicolumn{{2}}{{c}}{{\textbf{{\benchmarkdataset}} ({n_p})}} \\
\textbf{{Proximity Class}} & \textbf{{\#Bugs}} & \textbf{{Mean Div.}} & \textbf{{\#Bugs}} & \textbf{{Mean Div.}} & \textbf{{\#Bugs}} & \textbf{{Mean Div.}} \\
\midrule
{body}
\bottomrule
\end{{tabular}}
\end{{table}}"""


def main():
    div, prox = load()
    bugs = sorted(div)
    hunk4j_bugs = [b for b in bugs if "__" not in b]
    hunkswe_bugs = [b for b in bugs if "__" in b]

    h = stats_by_class(hunk4j_bugs, div, prox)
    s = stats_by_class(hunkswe_bugs, div, prox)
    p = stats_by_class(bugs, div, prox)

    assert (len(hunk4j_bugs), len(hunkswe_bugs), len(bugs)) == (372, 32, 404)
    for cls in PROXIMITY_ORDER:
        assert h[cls][0] + s[cls][0] == p[cls][0], cls

    print(render(h, s, p))


if __name__ == "__main__":
    main()
