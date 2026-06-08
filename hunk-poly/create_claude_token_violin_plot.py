#!/usr/bin/env python3
"""
Create violin plot for Claude showing all token components including cache.
"""

import csv
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
from matplotlib.ticker import FuncFormatter

# Set publication-quality plot style
plt.style.use('seaborn-v0_8-whitegrid')
plt.rcParams['font.size'] = 14
plt.rcParams['axes.labelsize'] = 16
plt.rcParams['axes.titlesize'] = 18
plt.rcParams['xtick.labelsize'] = 14
plt.rcParams['ytick.labelsize'] = 14
plt.rcParams['legend.fontsize'] = 14
plt.rcParams['figure.dpi'] = 300
plt.rcParams['savefig.dpi'] = 300
plt.rcParams['savefig.bbox'] = 'tight'


def format_large_number(x, pos):
    """Format large numbers with K, M, B suffixes."""
    if x >= 1e9:
        return f'{x/1e9:.1f}B'
    elif x >= 1e6:
        return f'{x/1e6:.1f}M'
    elif x >= 1e3:
        return f'{x/1e3:.1f}K'
    else:
        return f'{x:.0f}'


def normalize_bug_id(bug_id):
    return bug_id.replace('_', '-')


def load_claude_data():
    """Load Claude token data with cache breakdown."""
    tokens = {}
    with open('claude_code_results/claude_results/token_and_duration_claude.csv', 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            bug_id = normalize_bug_id(row['bug_id'])
            duration = float(row['time_duration'])
            if duration < 30:
                continue

            tokens[bug_id] = {
                'input': int(row['total_input_token']),
                'output': int(row['total_output_token']),
                'cache_creation': int(row['cache_creation_tokens']),
                'cache_read': int(row['cache_read_tokens'])
            }

    repairs = {}
    with open('claude_code_results/claude_results/claude_repair_ability.csv', 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            bug_id = normalize_bug_id(row['bug_id'])
            repairs[bug_id] = int(row['repair'])

    # Separate by outcome
    passed = []
    failed = []

    for bug_id in tokens:
        if bug_id in repairs:
            entry = {
                'input': tokens[bug_id]['input'],
                'cache_creation': tokens[bug_id]['cache_creation'],
                'cache_read': tokens[bug_id]['cache_read'],
                'output': tokens[bug_id]['output'],
                'total_input': tokens[bug_id]['input'] + tokens[bug_id]['cache_creation'] + tokens[bug_id]['cache_read']
            }

            if repairs[bug_id] == 1:
                passed.append(entry)
            else:
                failed.append(entry)

    return passed, failed


def create_claude_violin_plot(passed, failed):
    """Create violin plot with 3 subplots for Claude input token components."""

    fig, axes = plt.subplots(1, 3, figsize=(14, 5))

    token_types = [
        ('input', 'New Input'),
        ('cache_creation', 'Cache Creation'),
        ('cache_read', 'Cache Read')
    ]

    for idx, (token_key, label) in enumerate(token_types):
        ax = axes[idx]

        # Extract token values
        pass_tokens = [d[token_key] for d in passed]
        fail_tokens = [d[token_key] for d in failed]

        # Create violin plot
        positions = [1, 2]
        data = [pass_tokens, fail_tokens]

        parts = ax.violinplot(
            data,
            positions=positions,
            widths=0.7,
            showmeans=True,
            showmedians=True,
            showextrema=True
        )

        # Color the violins
        colors = ['green', 'red']
        for i, pc in enumerate(parts['bodies']):
            pc.set_facecolor(colors[i])
            pc.set_alpha(0.7)
            pc.set_edgecolor('black')
            pc.set_linewidth(1.5)

        # Customize extrema lines
        parts['cbars'].set_color('black')
        parts['cmaxes'].set_color('black')
        parts['cmins'].set_color('black')

        # Customize mean and median lines
        parts['cmedians'].set_color('darkblue')
        parts['cmedians'].set_linewidth(2)
        parts['cmeans'].set_color('red')
        parts['cmeans'].set_linewidth(2)

        # Set labels and title
        ax.set_xticks(positions)
        ax.set_xticklabels(['Pass', 'Fail'], fontweight='bold')
        ax.set_title(label, fontweight='bold')
        ax.set_ylabel('Tokens', fontweight='bold')

        # Format y-axis
        ax.yaxis.set_major_formatter(FuncFormatter(format_large_number))

        # Add grid
        ax.grid(True, axis='y', alpha=0.3, linestyle='--', linewidth=0.5)
        ax.set_axisbelow(True)

        # Print statistics
        print(f"\n{label}:")
        print(f"  Pass: n={len(pass_tokens)}, mean={np.mean(pass_tokens):,.0f}, median={np.median(pass_tokens):,.0f}")
        print(f"  Fail: n={len(fail_tokens)}, mean={np.mean(fail_tokens):,.0f}, median={np.median(fail_tokens):,.0f}")

    plt.tight_layout()

    return fig


def main():
    """Main function."""
    print("="*80)
    print("CREATING CLAUDE TOKEN VIOLIN PLOT")
    print("="*80)

    # Load data
    print("\nLoading Claude Code data...")
    passed, failed = load_claude_data()

    print(f"  Pass: {len(passed)}")
    print(f"  Fail: {len(failed)}")

    # Create plot
    print("\nCreating violin plots...")
    fig = create_claude_violin_plot(passed, failed)

    # Save
    output_dir = Path('analysis/figures')
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / 'claude_input_token_distribution_violin.pdf'
    fig.savefig(output_path, format='pdf', bbox_inches='tight', dpi=300)

    print(f"\nSaved: {output_path}")

    print("\n" + "="*80)
    print("COMPLETE")
    print("="*80)

    plt.show()


if __name__ == "__main__":
    main()
