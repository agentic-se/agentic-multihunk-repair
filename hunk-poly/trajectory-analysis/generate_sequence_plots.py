#!/usr/bin/env python3
"""
Window-configurable wrapper around the UNMODIFIED
`visualize_pass_fail_sequences.py`. Imports its `create_pass_fail_comparison`
function and calls it once per (agent × window) combination, so the same
rendering logic produces window-3 / window-4 / window-5 plots side by side.

The original script hard-codes window-3 CSV paths and emits the two PNGs
the paper currently uses for Figs 9 / 10. This wrapper does NOT change
the plotting logic — it only varies which CSV the function reads and
what filename the PNG lands at.

Usage:
    python3 generate_sequence_plots.py                # windows 3,4,5 for Qwen+Gemini
    python3 generate_sequence_plots.py --window 4     # just window 4
    python3 generate_sequence_plots.py --windows 3 5  # selected windows
    python3 generate_sequence_plots.py --agents qwen  # restrict agents

Outputs go to:
    diagrams/tool-sequences/<agent>_pass_fail_sequences_w<N>.png
"""
import argparse
import os
import sys
from pathlib import Path

# Import the unchanged plotting function from the migrated visualize script.
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from visualize_pass_fail_sequences import create_pass_fail_comparison  # noqa: E402

AGENT_CSV_TEMPLATE = {
    # cwd is hunk-poly/trajectory-analysis/; these are the same relative paths
    # the unmodified script uses for its hard-coded window-3 case.
    "qwen":   ("../qwen_code_results/qwen_results/tools_sequence_qwen",
               "Qwen Code"),
    "gemini": ("../../results/gemini_cli_results/tools_sequence_gemini",
               "Gemini CLI"),
    "claude": ("../claude_code_results/claude_results/tools_sequence_claude",
               "Claude Code"),
    "codex":  ("../openai_codex_results/results-codex/tools_sequence_codex",
               "OpenAI Codex"),
}


def main():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--window", type=int, choices=(3, 4, 5),
                   help="Plot only one window size.")
    g.add_argument("--windows", type=int, nargs="+", choices=(3, 4, 5),
                   help="Plot selected window sizes.")
    ap.add_argument("--agents", nargs="+",
                    choices=list(AGENT_CSV_TEMPLATE),
                    default=["qwen", "gemini"],
                    help="Agents to plot (default: qwen gemini — Figs 9 & 10).")
    ap.add_argument("--out-dir", default="diagrams/tool-sequences",
                    help="Output directory (relative to cwd).")
    args = ap.parse_args()

    if args.window is not None:
        windows = [args.window]
    elif args.windows is not None:
        windows = sorted(set(args.windows))
    else:
        windows = [3, 4, 5]

    os.makedirs(args.out_dir, exist_ok=True)

    for w in windows:
        print(f"\n=== window {w} ===")
        for agent in args.agents:
            seq_dir, display = AGENT_CSV_TEMPLATE[agent]
            pass_csv = f"{seq_dir}/tool_sequence_patterns_window_{w}_successful.csv"
            fail_csv = f"{seq_dir}/tool_sequence_patterns_window_{w}_unsuccessful.csv"
            out_png = f"{args.out_dir}/{agent}_pass_fail_sequences_w{w}.png"
            if not Path(pass_csv).exists() or not Path(fail_csv).exists():
                print(f"  [skip] {agent} window={w}: missing input CSVs")
                continue
            create_pass_fail_comparison(pass_csv, fail_csv, display, out_png)
    print("\nDone.")


if __name__ == "__main__":
    main()
