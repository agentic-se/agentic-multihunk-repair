#!/usr/bin/env python3
"""
UpSet-style plot of coding agents by spatial proximity class.
Adapted for coding agents: Gemini CLI, Qwen Code, Claude Code, OpenAI Codex
For TOSEM paper submission.
"""
import argparse
import json
import csv
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path

# --- Configuration ---
AGENTS = [
    "gemini_cli",
    "qwen_code",
    "claude_code",
    "openai_codex",
]

DISPLAY_NAMES = {
    "gemini_cli":   "Gemini CLI",
    "qwen_code":    "Qwen Code",
    "claude_code":  "Claude Code",
    "openai_codex": "OpenAI Codex",
}

PROX_CLASSES = ["Nucleus", "Cluster", "Orbit", "Sprawl", "Fragment"]

CLASS_COLORS = {
    "Nucleus":  "#1f77b4",
    "Cluster":  "#aec7e8",
    "Orbit":    "#ff7f0e",
    "Sprawl":   "#ffbb78",
    "Fragment": "#2ca02c"
}

# --- CLI parsing ---
def parse_args():
    p = argparse.ArgumentParser(
        description="Custom UpSet-style plot of coding agents by spatial proximity"
    )
    p.add_argument(
        "--fixed", default="fixed_bugs_by_agent.json",
        help="Path to fixed_bugs_by_agent.json"
    )
    p.add_argument(
        "--proximity", default="proximity_class.csv",
        help="Path to proximity_class.csv"
    )
    p.add_argument(
        "--output", default="plots/upset_plot_agent_repair_proximity.pdf",
        help="Output PDF path"
    )
    return p.parse_args()

# --- Data loaders ---
def load_fixed(path: str) -> dict[str, set[str]]:
    """Load fixed bugs by agent from JSON."""
    data = json.load(open(path, encoding="utf-8"))
    mapping: dict[str, set[str]] = {}
    for agent in AGENTS:
        if agent in data:
            # Ensure bug IDs use underscores consistently
            mapping[agent] = set(data[agent])
    return mapping

def load_proximity(path: str) -> dict[str, str]:
    """Load proximity class mapping from CSV."""
    prox = {}
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            bug = row["bug_id"].strip()
            prox[bug] = row["proximity_class"].strip()
    return prox

# --- Build membership DataFrame ---
def build_df(fixed_map: dict[str, set[str]], prox_map: dict[str, str]) -> pd.DataFrame:
    """Build DataFrame with agent membership and proximity class for each bug."""
    all_bugs = set().union(*fixed_map.values())
    recs = []
    for bug in sorted(all_bugs):
        rec = {agent: (bug in fixed_map.get(agent, ())) for agent in AGENTS}
        rec["prox"] = prox_map.get(bug, "UNKNOWN")
        recs.append((bug, rec))
    return pd.DataFrame.from_dict({b: r for b, r in recs}, orient="index")

# --- Main plotting ---
def main():
    args = parse_args()
    fixed_map = load_fixed(args.fixed)
    prox_map = load_proximity(args.proximity)
    df = build_df(fixed_map, prox_map)

    # Build the 4-digit pattern string
    df["pattern"] = df[AGENTS].apply(
        lambda r: "".join("1" if r[agent] else "0" for agent in AGENTS), axis=1
    )

    # Pivot to counts
    pivot = df.pivot_table(
        index="pattern", columns="prox", aggfunc="size", fill_value=0
    ).reindex(columns=PROX_CLASSES, fill_value=0)
    pivot["total"] = pivot.sum(axis=1)
    pivot = pivot.sort_values("total", ascending=True)

    patterns = pivot.index.to_list()
    counts_by_class = pivot[PROX_CLASSES].to_numpy()  # (n_patterns × 5)
    totals = pivot["total"].to_numpy()
    n_patterns = len(patterns)

    # --- Start plotting ---
    # Optimal width for 10 bars, reduced height with legend inside plot area
    fig = plt.figure(figsize=(18, 18))
    gs = fig.add_gridspec(2, 1, height_ratios=(10, 1), hspace=0.0)

    # Top: stacked bar + annotations
    ax0 = fig.add_subplot(gs[0])
    x = np.arange(n_patterns)
    bottom = np.zeros(n_patterns)
    for i, cls in enumerate(PROX_CLASSES):
        vals = counts_by_class[:, i]
        bars = ax0.bar(x, vals, bottom=bottom, color=CLASS_COLORS[cls], label=cls)

        # Annotate each segment (show ALL non-zero values)
        for xi, v in enumerate(vals):
            if v > 0:
                y = bottom[xi] + v / 2
                ax0.text(
                    xi, y, str(int(v)),
                    ha="center", va="center",
                    fontsize=14, color="white", fontweight="bold"
                )
        bottom += vals

    # Annotate total above
    for xi, tot in zip(x, totals):
        ax0.text(xi, tot + 1.0, str(int(tot)), ha="center", fontsize=20, fontweight="bold")

    ax0.set_ylabel("Intersection Size", fontsize=22, fontweight="bold")
    ax0.set_xticks([])
    # Set very tight y-axis limit to minimize empty space at top
    ax0.set_ylim(0, max(totals) + 3)
    # Position legend lower to save vertical space
    ax0.legend(title="Proximity Class", ncol=2,
               title_fontsize=16, fontsize=20, loc="upper left", frameon=True, bbox_to_anchor=(0.0, 0.95))
    ax0.grid(axis='y', alpha=0.3, linestyle='--')
    ax0.tick_params(axis='y', labelsize=20)

    # Bottom: dot-matrix + connectors
    ax1 = fig.add_subplot(gs[1], sharex=ax0)
    connector_color = "#333333"  # Dark gray for all connectors and dots
    for xi, pat in enumerate(patterns):
        ys = [i for i, ch in enumerate(pat) if ch == "1"]
        if not ys:
            continue
        # Connector
        ax1.vlines(xi, min(ys), max(ys), color=connector_color, linewidth=4)
        # Dots
        ax1.scatter([xi] * len(ys), ys, color=connector_color, s=150, zorder=3)

    ax1.set_yticks(range(len(AGENTS)))
    ax1.set_yticklabels([DISPLAY_NAMES[agent] for agent in AGENTS], fontsize=20, fontweight="bold")
    ax1.invert_yaxis()
    ax1.set_xlim(-0.5, n_patterns - 0.5)
    ax1.set_ylim(len(AGENTS) - 0.5, -0.5)  # Tighter y-limits
    ax1.set_xticks([])
    ax1.tick_params(axis='y', length=0, pad=1)  # Remove tick marks, minimal padding
    ax1.margins(y=0.05)  # Minimal margins

    # Adjust margins
    fig.subplots_adjust(top=0.95, bottom=0.08, left=0.12, right=0.97)
    plt.tight_layout()

    # Save to PDF
    plt.savefig(args.output, format='pdf', bbox_inches='tight')
    print(f"UpSet plot saved to: {args.output}")

    # Print summary
    print("\n" + "=" * 70)
    print("Summary Statistics")
    print("=" * 70)
    print(f"Total bugs analyzed: {len(df)}")
    print(f"Unique intersection patterns: {n_patterns}")
    print(f"Bugs by proximity class:")
    for cls in PROX_CLASSES:
        count = sum(df["prox"] == cls)
        print(f"  {cls}: {count}")
    print("\nUpSet plot generation complete!")
    print("=" * 70)

if __name__ == "__main__":
    main()
