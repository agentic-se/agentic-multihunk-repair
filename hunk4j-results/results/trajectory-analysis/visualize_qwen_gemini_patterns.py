#!/usr/bin/env python3
"""
Generate high-quality visualizations comparing tool sequence patterns
for the two worst-performing agents: Qwen vs Gemini.

Shows contrasting failure modes:
- Qwen: Navigation overhead
- Gemini: Over-modification
"""

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

# Paths
QWEN_CSV = '../qwen_code_results/qwen_results/tools_sequence_qwen/tool_sequence_patterns_window_3_all.csv'
GEMINI_CSV = '../../results/gemini_cli_results/tools_sequence_gemini/tool_sequence_patterns_window_3_all.csv'

# Professional colorblind-friendly palette (based on ColorBrewer)
COLORS = {
    'WRITE': '#d73027',       # Red-orange
    'READ': '#4575b4',        # Blue
    'TEST': '#91bfdb',        # Light blue
    'BUILD': '#fee090',       # Light yellow
    'SEARCH_FILES': '#fc8d59', # Orange
    'SEARCH_CONTENT': '#91cf60', # Green
    'NAVIGATE': '#bdbdbd',    # Gray
    'VCS': '#636363',         # Dark gray
}

def get_pattern_color(pattern):
    """
    Determine the dominant color for a pattern based on most frequent tool.
    For patterns with NAVIGATE, always return NAVIGATE color to highlight navigation overhead.
    """
    if 'NAVIGATE' in pattern:
        return COLORS['NAVIGATE']

    tools = [t.strip() for t in pattern.split('->')]
    tool_counts = {}
    for tool in tools:
        tool_counts[tool] = tool_counts.get(tool, 0) + 1

    dominant_tool = max(tool_counts, key=tool_counts.get)
    return COLORS.get(dominant_tool, '#34495e')

def shorten_pattern(pattern):
    """Abbreviate tool names for cleaner display."""
    replacements = {
        'SEARCH_FILES': 'SF',
        'SEARCH_CONTENT': 'SC',
        'NAVIGATE': 'NAV',
        'WRITE': 'WR',
        'BUILD': 'BLD',
        'READ': 'RD',
        'TEST': 'TST',
        'VCS': 'VCS'
    }
    for long, short in replacements.items():
        pattern = pattern.replace(long, short)
    return pattern

def create_comparison_chart(qwen_csv, gemini_csv, output_file):
    """
    Create side-by-side horizontal bar charts comparing Qwen vs Gemini.
    """
    # Read data
    qwen_df = pd.read_csv(qwen_csv)
    gemini_df = pd.read_csv(gemini_csv)

    # Calculate percentages
    qwen_total = qwen_df['frequency'].sum()
    gemini_total = gemini_df['frequency'].sum()

    qwen_df['percentage'] = (qwen_df['frequency'] / qwen_total) * 100
    gemini_df['percentage'] = (gemini_df['frequency'] / gemini_total) * 100

    # Get top 5
    qwen_top5 = qwen_df.head(5).copy()
    gemini_top5 = gemini_df.head(5).copy()

    # Create figure with two subplots side by side
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6))

    # === QWEN (Left) ===
    qwen_patterns = qwen_top5['tool_sequence'].tolist()
    qwen_percentages = qwen_top5['percentage'].tolist()
    qwen_colors = [get_pattern_color(p) for p in qwen_patterns]
    qwen_short = [shorten_pattern(p) for p in qwen_patterns]

    y_pos = range(len(qwen_short))
    bars1 = ax1.barh(y_pos, qwen_percentages, color=qwen_colors,
                     alpha=0.85, edgecolor='black', linewidth=1.5)

    ax1.set_yticks(y_pos)
    ax1.set_yticklabels(qwen_short, fontsize=12, fontfamily='monospace')
    ax1.set_xlabel('Percentage (%)', fontsize=13, fontweight='bold')
    ax1.set_title('Qwen Code', fontsize=14, fontweight='bold', pad=15)
    ax1.invert_yaxis()
    ax1.grid(axis='x', alpha=0.3, linestyle='--')
    ax1.set_axisbelow(True)
    ax1.set_xlim(0, max(qwen_percentages) * 1.2)

    # Add percentage labels
    for i, (bar, pct, freq) in enumerate(zip(bars1, qwen_percentages, qwen_top5['frequency'])):
        ax1.text(pct + 0.15, i, f'{pct:.2f}%',
                va='center', fontsize=11, fontweight='bold')

    # === GEMINI (Right) ===
    gemini_patterns = gemini_top5['tool_sequence'].tolist()
    gemini_percentages = gemini_top5['percentage'].tolist()
    gemini_colors = [get_pattern_color(p) for p in gemini_patterns]
    gemini_short = [shorten_pattern(p) for p in gemini_patterns]

    y_pos = range(len(gemini_short))
    bars2 = ax2.barh(y_pos, gemini_percentages, color=gemini_colors,
                     alpha=0.85, edgecolor='black', linewidth=1.5)

    ax2.set_yticks(y_pos)
    ax2.set_yticklabels(gemini_short, fontsize=12, fontfamily='monospace')
    ax2.set_xlabel('Percentage (%)', fontsize=13, fontweight='bold')
    ax2.set_title('Gemini CLI', fontsize=14, fontweight='bold', pad=15)
    ax2.invert_yaxis()
    ax2.grid(axis='x', alpha=0.3, linestyle='--')
    ax2.set_axisbelow(True)
    ax2.set_xlim(0, max(gemini_percentages) * 1.2)

    # Add percentage labels
    for i, (bar, pct, freq) in enumerate(zip(bars2, gemini_percentages, gemini_top5['frequency'])):
        ax2.text(pct + 0.4, i, f'{pct:.2f}%',
                va='center', fontsize=11, fontweight='bold')

    plt.tight_layout()
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"✓ Saved: {output_file}")
    plt.close()

def create_separate_charts(qwen_csv, gemini_csv):
    """Create individual high-resolution charts for each agent."""

    # Read data
    qwen_df = pd.read_csv(qwen_csv)
    gemini_df = pd.read_csv(gemini_csv)

    # Calculate percentages
    qwen_total = qwen_df['frequency'].sum()
    gemini_total = gemini_df['frequency'].sum()

    qwen_df['percentage'] = (qwen_df['frequency'] / qwen_total) * 100
    gemini_df['percentage'] = (gemini_df['frequency'] / gemini_total) * 100

    # Qwen individual
    qwen_top5 = qwen_df.head(5).copy()
    fig, ax = plt.subplots(figsize=(10, 6))

    qwen_patterns = qwen_top5['tool_sequence'].tolist()
    qwen_percentages = qwen_top5['percentage'].tolist()
    qwen_colors = [get_pattern_color(p) for p in qwen_patterns]
    qwen_short = [shorten_pattern(p) for p in qwen_patterns]

    y_pos = range(len(qwen_short))
    bars = ax.barh(y_pos, qwen_percentages, color=qwen_colors,
                   alpha=0.85, edgecolor='black', linewidth=1.5)

    ax.set_yticks(y_pos)
    ax.set_yticklabels(qwen_short, fontsize=13, fontfamily='monospace')
    ax.set_xlabel('Percentage of All 3-Step Sequences (%)', fontsize=13, fontweight='bold')
    ax.set_title('Qwen Code', fontsize=15, fontweight='bold', pad=20)
    ax.invert_yaxis()
    ax.grid(axis='x', alpha=0.3, linestyle='--')
    ax.set_axisbelow(True)
    ax.set_xlim(0, max(qwen_percentages) * 1.25)

    for i, (bar, pct) in enumerate(zip(bars, qwen_percentages)):
        ax.text(pct + 0.15, i, f'{pct:.2f}%',
                va='center', fontsize=12, fontweight='bold')

    plt.tight_layout()
    plt.savefig('qwen_top5_patterns_window3.png', dpi=300, bbox_inches='tight')
    print(f"✓ Saved: qwen_top5_patterns_window3.png")
    plt.close()

    # Gemini individual
    gemini_top5 = gemini_df.head(5).copy()
    fig, ax = plt.subplots(figsize=(10, 6))

    gemini_patterns = gemini_top5['tool_sequence'].tolist()
    gemini_percentages = gemini_top5['percentage'].tolist()
    gemini_colors = [get_pattern_color(p) for p in gemini_patterns]
    gemini_short = [shorten_pattern(p) for p in gemini_patterns]

    y_pos = range(len(gemini_short))
    bars = ax.barh(y_pos, gemini_percentages, color=gemini_colors,
                   alpha=0.85, edgecolor='black', linewidth=1.5)

    ax.set_yticks(y_pos)
    ax.set_yticklabels(gemini_short, fontsize=13, fontfamily='monospace')
    ax.set_xlabel('Percentage of All 3-Step Sequences (%)', fontsize=13, fontweight='bold')
    ax.set_title('Gemini CLI', fontsize=15, fontweight='bold', pad=20)
    ax.invert_yaxis()
    ax.grid(axis='x', alpha=0.3, linestyle='--')
    ax.set_axisbelow(True)
    ax.set_xlim(0, max(gemini_percentages) * 1.25)

    for i, (bar, pct) in enumerate(zip(bars, gemini_percentages)):
        ax.text(pct + 0.4, i, f'{pct:.2f}%',
                va='center', fontsize=12, fontweight='bold')

    plt.tight_layout()
    plt.savefig('gemini_top5_patterns_window3.png', dpi=300, bbox_inches='tight')
    print(f"✓ Saved: gemini_top5_patterns_window3.png")
    plt.close()

def print_summary_stats():
    """Print detailed statistics for paper description."""
    qwen_df = pd.read_csv(QWEN_CSV)
    gemini_df = pd.read_csv(GEMINI_CSV)

    qwen_total = qwen_df['frequency'].sum()
    gemini_total = gemini_df['frequency'].sum()

    qwen_df['percentage'] = (qwen_df['frequency'] / qwen_total) * 100
    gemini_df['percentage'] = (gemini_df['frequency'] / gemini_total) * 100

    print("\n" + "=" * 80)
    print("SUMMARY STATISTICS FOR PAPER")
    print("=" * 80)

    print(f"\n=== QWEN CODE ===")
    print(f"Total 3-step sequences: {qwen_total:,}")
    print(f"Unique patterns: {len(qwen_df):,}")
    print(f"\nTop 5 patterns:")
    for i, row in qwen_df.head(5).iterrows():
        print(f"  {i+1}. {row['tool_sequence']}")
        print(f"     {row['percentage']:.2f}% (n={row['frequency']})")

    # Count NAVIGATE
    nav_in_top10 = sum(1 for _, row in qwen_df.head(10).iterrows() if 'NAVIGATE' in row['tool_sequence'])
    print(f"\nNAVIGATE appears in {nav_in_top10}/10 top patterns")

    print(f"\n=== GEMINI CLI ===")
    print(f"Total 3-step sequences: {gemini_total:,}")
    print(f"Unique patterns: {len(gemini_df):,}")
    print(f"\nTop 5 patterns:")
    for i, row in gemini_df.head(5).iterrows():
        print(f"  {i+1}. {row['tool_sequence']}")
        print(f"     {row['percentage']:.2f}% (n={row['frequency']})")

    # Check WRITE -> WRITE -> WRITE
    www = gemini_df[gemini_df['tool_sequence'] == 'WRITE -> WRITE -> WRITE']
    if len(www) > 0:
        print(f"\nWRITE → WRITE → WRITE: {www.iloc[0]['percentage']:.2f}% (highest concentration)")

    print("\n" + "=" * 80)
    print("KEY INSIGHTS")
    print("=" * 80)
    print("\n1. Qwen exhibits navigation overhead:")
    print(f"   - NAVIGATE appears in {nav_in_top10}/10 top patterns")
    print(f"   - Top pattern: NAVIGATE → TEST → NAVIGATE (3.23%)")
    print(f"   - Wastes computational budget on directory changes")

    print("\n2. Gemini exhibits over-modification:")
    print(f"   - WRITE → WRITE → WRITE is top pattern (8.74%)")
    print(f"   - 2.7x higher concentration than Qwen's top pattern")
    print(f"   - Batches modifications without intermediate validation")

    print("\n3. Contrasting failure modes:")
    print("   - Qwen: Fragmented patterns (max 3.23%), high navigation overhead")
    print("   - Gemini: Concentrated patterns (max 8.74%), excessive consecutive writes")

def main():
    """Generate all visualizations and statistics."""
    print("Generating tool sequence pattern visualizations...")
    print("Comparing two worst-performing agents: Qwen vs Gemini")

    # Create comparison chart
    create_comparison_chart(QWEN_CSV, GEMINI_CSV,
                           'qwen_vs_gemini_patterns_comparison.png')

    # Create individual charts
    create_separate_charts(QWEN_CSV, GEMINI_CSV)

    # Print statistics
    print_summary_stats()

    print("\n" + "=" * 80)
    print("✓ ALL VISUALIZATIONS GENERATED")
    print("=" * 80)
    print("\nFiles created:")
    print("  1. qwen_vs_gemini_patterns_comparison.png - Side-by-side comparison")
    print("  2. qwen_top5_patterns_window3.png - Qwen individual chart")
    print("  3. gemini_top5_patterns_window3.png - Gemini individual chart")
    print("\nReady for inclusion in TOSEM paper!")

if __name__ == '__main__':
    main()
