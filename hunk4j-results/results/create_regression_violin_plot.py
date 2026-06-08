#!/usr/bin/env python3
"""
Create violin plot for regression reduction distribution across tools.
Generates publication-quality figure for TOSEM paper.
"""

import csv
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
import seaborn as sns

# Set publication-quality plot style
plt.style.use('seaborn-v0_8-whitegrid')
plt.rcParams['figure.figsize'] = (12, 7)
plt.rcParams['font.size'] = 16
plt.rcParams['axes.labelsize'] = 20
plt.rcParams['axes.titlesize'] = 22
plt.rcParams['xtick.labelsize'] = 16
plt.rcParams['ytick.labelsize'] = 16
plt.rcParams['legend.fontsize'] = 16
plt.rcParams['figure.dpi'] = 300
plt.rcParams['savefig.dpi'] = 300
plt.rcParams['savefig.bbox'] = 'tight'


def read_regression_reduction_values(csv_path):
    """
    Read regression reduction values from CSV file.

    Returns:
        list: List of regression reduction values (excluding "undefined")
    """
    regression_reduction_values = []

    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)

        for row in reader:
            regression_reduction_str = row['regression_reduction']

            # Only collect valid numeric values
            if regression_reduction_str != "undefined":
                regression_reduction = int(regression_reduction_str)
                regression_reduction_values.append(regression_reduction)

    return regression_reduction_values


def main():
    """Main function to create violin plot."""

    # Define tool configurations (ordered from worst to best)
    tools = {
        'Qwen Code': {
            'path': 'qwen_code_results/qwen_results/qwen_repair_ability.csv',
            'color': '#C73E1D'
        },
        'Gemini CLI': {
            'path': 'gemini_cli_results/gemini_repair_ability.csv',
            'color': '#F18F01'
        },
        'OpenAI Codex': {
            'path': 'openai_codex_results/results-codex/codex_repair_ability.csv',
            'color': '#A23B72'
        },
        'Claude Code': {
            'path': 'claude_code_results/claude_results/claude_repair_ability.csv',
            'color': '#2E86AB'
        }
    }

    # Collect data for all tools
    data = []
    labels = []
    colors = []
    stats = {}

    print("Processing tools...")
    print("="*80)

    for tool_name, tool_config in tools.items():
        csv_path = Path(tool_config['path'])
        print(f"\n{tool_name}:")

        rr_values = read_regression_reduction_values(csv_path)

        # Calculate statistics
        rr_array = np.array(rr_values)
        mean = np.mean(rr_array)
        median = np.median(rr_array)
        std = np.std(rr_array, ddof=1)
        q1 = np.percentile(rr_array, 25)
        q3 = np.percentile(rr_array, 75)
        min_val = np.min(rr_array)
        max_val = np.max(rr_array)

        # Count positive, zero, negative
        positive = np.sum(rr_array > 0)
        zero = np.sum(rr_array == 0)
        negative = np.sum(rr_array < 0)
        total = len(rr_array)

        print(f"  Count: {total}")
        print(f"  Mean: {mean:.2f}")
        print(f"  Median: {median:.2f}")
        print(f"  Std Dev: {std:.2f}")
        print(f"  Q1, Q3: {q1:.2f}, {q3:.2f}")
        print(f"  Range: [{min_val:.2f}, {max_val:.2f}]")
        print(f"  Positive: {positive} ({positive/total*100:.1f}%)")
        print(f"  Zero: {zero} ({zero/total*100:.1f}%)")
        print(f"  Negative: {negative} ({negative/total*100:.1f}%)")

        data.append(rr_values)
        labels.append(tool_name)
        colors.append(tool_config['color'])

        stats[tool_name] = {
            'mean': mean,
            'median': median,
            'positive_pct': positive/total*100,
            'negative_pct': negative/total*100
        }

    print("\n" + "="*80)

    # Create the violin plot
    fig, ax = plt.subplots(figsize=(12, 7))

    # Create violin plot
    parts = ax.violinplot(
        data,
        positions=range(len(labels)),
        widths=0.7,
        showmeans=True,
        showmedians=True,
        showextrema=True
    )

    # Customize violin colors
    for i, pc in enumerate(parts['bodies']):
        pc.set_facecolor(colors[i])
        pc.set_alpha(0.7)
        pc.set_edgecolor('black')
        pc.set_linewidth(1.5)

    # Customize mean, median, and extrema lines
    parts['cmeans'].set_color('red')
    parts['cmeans'].set_linewidth(2)
    parts['cmedians'].set_color('blue')
    parts['cmedians'].set_linewidth(2)
    parts['cbars'].set_color('black')
    parts['cmaxes'].set_color('black')
    parts['cmins'].set_color('black')

    # Add horizontal line at y=0
    ax.axhline(y=0, color='black', linestyle='--', linewidth=1.5, alpha=0.5)

    # Add shaded regions
    ax.axhspan(-100, 0, alpha=0.05, color='red', zorder=0)
    ax.axhspan(0, 100, alpha=0.05, color='green', zorder=0)

    # Add text annotations for zones
    ax.text(-0.5, -15, 'Regression\nIntroduction',
            fontsize=14, alpha=0.5, color='red',
            ha='left', va='top')
    ax.text(-0.5, 15, 'Regression\nReduction',
            fontsize=14, alpha=0.5, color='green',
            ha='left', va='bottom')

    # Customize axes
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, fontweight='bold')
    ax.set_ylabel('Regression Reduction',
                  fontweight='bold')

    # Add grid
    ax.grid(True, axis='y', alpha=0.3, linestyle='--', linewidth=0.5)
    ax.set_axisbelow(True)

    # Add legend for mean and median
    from matplotlib.lines import Line2D
    legend_elements = [
        Line2D([0], [0], color='red', linewidth=2, label='Mean'),
        Line2D([0], [0], color='blue', linewidth=2, label='Median')
    ]
    ax.legend(handles=legend_elements, loc='upper right', frameon=True,
              shadow=True, fancybox=True)

    # Set y-axis limits
    ax.set_ylim(-30, 30)

    # Tight layout
    plt.tight_layout()

    # Create output directory
    output_dir = Path('analysis/figures')
    output_dir.mkdir(parents=True, exist_ok=True)

    # Save PDF only (for paper)
    output_pdf = output_dir / 'agent_regression_reduction_violin.pdf'
    plt.savefig(output_pdf, format='pdf', bbox_inches='tight', dpi=300)
    print(f"\nFigure saved: {output_pdf}")

    # Show the plot
    plt.show()


if __name__ == "__main__":
    main()
