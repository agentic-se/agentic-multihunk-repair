#!/usr/bin/env python3
"""
Generate visualizations comparing successful vs unsuccessful tool sequence patterns
for Qwen and Gemini.
"""

import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

# Paths
QWEN_PASS_CSV = '../qwen_code_results/qwen_results/tools_sequence_qwen/tool_sequence_patterns_window_3_successful.csv'
QWEN_FAIL_CSV = '../qwen_code_results/qwen_results/tools_sequence_qwen/tool_sequence_patterns_window_3_unsuccessful.csv'
GEMINI_PASS_CSV = '../../results/gemini_cli_results/tools_sequence_gemini/tool_sequence_patterns_window_3_successful.csv'
GEMINI_FAIL_CSV = '../../results/gemini_cli_results/tools_sequence_gemini/tool_sequence_patterns_window_3_unsuccessful.csv'

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
    """Get dominant color for pattern based on most frequent tool."""
    tools = [t.strip() for t in pattern.split('->')]
    tool_counts = {}
    for tool in tools:
        tool_counts[tool] = tool_counts.get(tool, 0) + 1

    dominant_tool = max(tool_counts, key=tool_counts.get)
    return COLORS.get(dominant_tool, '#636363')

def shorten_pattern(pattern):
    """Abbreviate tool names."""
    replacements = {
        'SEARCH_FILES': 'SF',
        'SEARCH_CONTENT': 'SC',
        'NAVIGATE': 'NAV',
        'WRITE': 'WR',
        'BUILD': 'BLD',
        'READ': 'RD',
        'TEST': 'TST',
    }
    for long, short in replacements.items():
        pattern = pattern.replace(long, short)
    return pattern

def create_pass_fail_comparison(pass_csv, fail_csv, agent_name, output_file):
    """Create side-by-side Pass vs Fail comparison with Ali's improvements."""

    # Determine if this is Qwen (all text inside) or Gemini (selective placement)
    is_qwen = 'qwen' in output_file.lower()

    # Read data
    pass_df = pd.read_csv(pass_csv)
    fail_df = pd.read_csv(fail_csv)

    # Calculate percentages
    pass_total = pass_df['frequency'].sum()
    fail_total = fail_df['frequency'].sum()
    pass_df['percentage'] = (pass_df['frequency'] / pass_total) * 100
    fail_df['percentage'] = (fail_df['frequency'] / fail_total) * 100

    # Get top 5 by frequency
    pass_top5 = pass_df.head(5).copy()
    fail_top5 = fail_df.head(5).copy()

    # Create figure - wide for maximum space utilization
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))

    # Professional muted green/red colors
    pass_color = '#81C784'  # Muted green
    fail_color = '#E57373'  # Muted red

    # === PASS (Left) - GREEN ===
    pass_patterns = pass_top5['tool_sequence'].apply(shorten_pattern).tolist()
    pass_frequencies = pass_top5['frequency'].tolist()
    pass_percentages = pass_top5['percentage'].tolist()

    y_pos = np.arange(len(pass_patterns))
    bars1 = ax1.barh(y_pos, pass_frequencies, height=0.9,
                     color=pass_color, edgecolor='black', linewidth=1.2)

    # Add text INSIDE bars (Qwen: all inside; Gemini: only top bar inside, rest outside)
    for i, (bar, pattern, freq, pct) in enumerate(zip(bars1, pass_patterns, pass_frequencies, pass_percentages)):
        bar_width = bar.get_width()

        # Pattern text (left side of bar)
        ax1.text(4, i, pattern,
                 va='center', ha='left',
                 fontsize=16, fontweight='bold',
                 color='white', family='monospace')

        # Frequency count AND percentage
        if is_qwen:  # Qwen: ALL inside
            ax1.text(bar_width - 4, i, f'{freq} ({pct:.2f}%)',
                     va='center', ha='right',
                     fontsize=12, fontweight='bold',
                     color='white')
        else:  # Gemini: Top bar inside, rest outside
            if i == 0:  # Top bar - text inside
                ax1.text(bar_width - 4, i, f'{freq} ({pct:.2f}%)',
                         va='center', ha='right',
                         fontsize=12, fontweight='bold',
                         color='white')
            else:  # All other bars - text outside
                ax1.text(bar_width + 3, i, f'{freq} ({pct:.2f}%)',
                         va='center', ha='left',
                         fontsize=12, fontweight='bold',
                         color='black')

    # Remove y-axis labels - text is inside bars
    ax1.set_yticks([])
    ax1.set_yticklabels([])
    ax1.set_xlabel('Frequency', fontsize=12, fontweight='bold')
    ax1.invert_yaxis()
    # Reduce vertical space - add padding to prevent overlap with x-axis
    ax1.set_ylim(len(pass_patterns) - 0.4, -0.55)
    ax1.spines['left'].set_visible(True)
    ax1.spines['top'].set_visible(True)
    ax1.spines['right'].set_visible(True)
    ax1.spines['bottom'].set_visible(True)
    # Make spines (box) more visible
    for spine in ax1.spines.values():
        spine.set_edgecolor('black')
        spine.set_linewidth(1.5)
    # Qwen: tight xlim (all inside); Gemini: minimal space for outside labels
    ax1.set_xlim(0, max(pass_frequencies) * (1.01 if is_qwen else 1.015))
    ax1.grid(axis='x', alpha=0.25, linestyle='--', linewidth=0.8)
    ax1.set_axisbelow(True)

    # === FAIL (Right) - RED ===
    fail_patterns = fail_top5['tool_sequence'].apply(shorten_pattern).tolist()
    fail_frequencies = fail_top5['frequency'].tolist()
    fail_percentages = fail_top5['percentage'].tolist()

    y_pos = np.arange(len(fail_patterns))
    bars2 = ax2.barh(y_pos, fail_frequencies, height=0.9,
                     color=fail_color, edgecolor='black', linewidth=1.2)

    # Add text INSIDE bars (Qwen: all inside; Gemini: only top bar inside, rest outside)
    for i, (bar, pattern, freq, pct) in enumerate(zip(bars2, fail_patterns, fail_frequencies, fail_percentages)):
        bar_width = bar.get_width()

        # Pattern text (left side of bar) - always inside
        ax2.text(5, i, pattern,
                 va='center', ha='left',
                 fontsize=16, fontweight='bold',
                 color='white', family='monospace')

        # Frequency count AND percentage
        if is_qwen:  # Qwen: ALL inside
            ax2.text(bar_width - 4, i, f'{freq} ({pct:.2f}%)',
                     va='center', ha='right',
                     fontsize=12, fontweight='bold',
                     color='white')
        else:  # Gemini: Top bar inside, rest outside
            if i == 0:  # Top bar - text inside
                ax2.text(bar_width - 5, i, f'{freq} ({pct:.2f}%)',
                         va='center', ha='right',
                         fontsize=12, fontweight='bold',
                         color='white')
            else:  # All other bars - text outside
                ax2.text(bar_width + 3, i, f'{freq} ({pct:.2f}%)',
                         va='center', ha='left',
                         fontsize=12, fontweight='bold',
                         color='black')

    # Remove y-axis labels
    ax2.set_yticks([])
    ax2.set_yticklabels([])
    ax2.set_xlabel('Frequency', fontsize=12, fontweight='bold')
    ax2.invert_yaxis()
    # Reduce vertical space - add padding to prevent overlap with x-axis
    ax2.set_ylim(len(fail_patterns) - 0.4, -0.55)
    ax2.spines['left'].set_visible(True)
    ax2.spines['top'].set_visible(True)
    ax2.spines['right'].set_visible(True)
    ax2.spines['bottom'].set_visible(True)
    # Make spines (box) more visible
    for spine in ax2.spines.values():
        spine.set_edgecolor('black')
        spine.set_linewidth(1.5)
    # Qwen: tight xlim (all inside); Gemini: minimal space for outside labels
    ax2.set_xlim(0, max(fail_frequencies) * (1.01 if is_qwen else 1.015))
    ax2.grid(axis='x', alpha=0.25, linestyle='--', linewidth=0.8)
    ax2.set_axisbelow(True)

    # No overall title - caption will explain
    plt.tight_layout()
    plt.savefig(output_file, dpi=300, bbox_inches='tight', facecolor='white')
    print(f"✓ Saved: {output_file}")
    plt.close()

def main():
    """Generate visualizations."""
    import os

    # Create output directory
    output_dir = 'diagrams/tool-sequences'
    os.makedirs(output_dir, exist_ok=True)

    print("Generating improved Pass vs Fail sequence pattern visualizations...")

    # Qwen Pass vs Fail
    create_pass_fail_comparison(QWEN_PASS_CSV, QWEN_FAIL_CSV,
                               'Qwen Code', f'{output_dir}/qwen_pass_fail_sequences.png')

    # Gemini Pass vs Fail
    create_pass_fail_comparison(GEMINI_PASS_CSV, GEMINI_FAIL_CSV,
                               'Gemini CLI', f'{output_dir}/gemini_pass_fail_sequences.png')

    print("\n✓ All visualizations generated!")
    print(f"\nFiles saved to: {output_dir}/")
    print("  - qwen_pass_fail_sequences.png")
    print("  - gemini_pass_fail_sequences.png")
    print("\nImprovements applied:")
    print("  ✅ Pattern text INSIDE bars")
    print("  ✅ Frequency counts INSIDE bars")
    print("  ✅ No y-axis labels (maximum space)")
    print("  ✅ No redundant titles")
    print("  ✅ Muted green/red colors")
    print("  ✅ Correct x-axis (Frequency)")
    print("\nReady for paper submission!")

if __name__ == '__main__':
    main()
