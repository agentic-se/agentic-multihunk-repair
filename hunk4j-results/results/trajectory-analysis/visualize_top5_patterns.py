#!/usr/bin/env python3
"""
Generate bar charts showing top 5 tool sequence patterns (window=5) for Qwen and Claude.
"""

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

# Paths to the CSV files
QWEN_CSV = '../qwen_code_results/qwen_results/tools_sequence_qwen/tool_sequence_patterns_window_5_all.csv'
CLAUDE_CSV = '../../results/claude_code_results/claude_results/tools_sequence_claude/tool_sequence_patterns_window_5_all.csv'

# Color mapping for tool categories
COLORS = {
    'WRITE': '#e74c3c',      # Red
    'READ': '#3498db',       # Blue
    'TEST': '#2ecc71',       # Green
    'BUILD': '#f39c12',      # Orange
    'SEARCH_FILES': '#9b59b6',     # Purple
    'SEARCH_CONTENT': '#1abc9c',   # Teal
    'NAVIGATE': '#95a5a6',   # Gray
}

def get_dominant_color(pattern):
    """Get the dominant tool category color from a pattern."""
    tools = [t.strip() for t in pattern.split('->')]
    # Count occurrences of each tool
    tool_counts = {}
    for tool in tools:
        tool_counts[tool] = tool_counts.get(tool, 0) + 1
    # Return color of most frequent tool
    dominant_tool = max(tool_counts, key=tool_counts.get)
    return COLORS.get(dominant_tool, '#34495e')  # Default dark gray

def shorten_pattern(pattern):
    """Shorten pattern for display by using abbreviations."""
    pattern = pattern.replace('SEARCH_FILES', 'SF')
    pattern = pattern.replace('SEARCH_CONTENT', 'SC')
    pattern = pattern.replace('NAVIGATE', 'NAV')
    pattern = pattern.replace('WRITE', 'WR')
    pattern = pattern.replace('BUILD', 'BLD')
    pattern = pattern.replace('READ', 'RD')
    pattern = pattern.replace('TEST', 'TST')
    return pattern

def create_bar_chart(csv_path, agent_name, output_file):
    """Create horizontal bar chart for top 5 patterns."""
    # Read CSV
    df = pd.read_csv(csv_path)

    # Calculate total count of all window=5 sequences
    total_sequences = df['frequency'].sum()

    # Get top 5
    top5 = df.head(5)

    # Calculate percentages
    top5 = top5.copy()
    top5['percentage'] = (top5['frequency'] / total_sequences) * 100

    # Create figure
    fig, ax = plt.subplots(figsize=(10, 6))

    # Prepare data
    patterns = top5['tool_sequence'].tolist()
    percentages = top5['percentage'].tolist()
    frequencies = top5['frequency'].tolist()
    colors = [get_dominant_color(p) for p in patterns]

    # Shorten patterns for display
    short_patterns = [shorten_pattern(p) for p in patterns]

    # Create horizontal bar chart
    y_pos = range(len(short_patterns))
    bars = ax.barh(y_pos, percentages, color=colors, alpha=0.8, edgecolor='black', linewidth=1.5)

    # Customize
    ax.set_yticks(y_pos)
    ax.set_yticklabels(short_patterns, fontsize=11)
    ax.set_xlabel('Percentage (%)', fontsize=12, fontweight='bold')
    ax.set_title(f'Top 5 Tool Sequence Patterns (Window=5)\n{agent_name}',
                 fontsize=14, fontweight='bold', pad=20)

    # Add percentage labels on bars (with frequency in parentheses)
    for i, (bar, pct, freq) in enumerate(zip(bars, percentages, frequencies)):
        ax.text(pct + 0.1, i, f'{pct:.1f}% (n={freq})', va='center', fontsize=11, fontweight='bold')

    # Add grid
    ax.grid(axis='x', alpha=0.3, linestyle='--')
    ax.set_axisbelow(True)

    # Set x-axis limit with some padding
    ax.set_xlim(0, max(percentages) * 1.15)

    # Invert y-axis so highest frequency is at top
    ax.invert_yaxis()

    # Add legend for abbreviations
    legend_text = 'WR=WRITE, RD=READ, TST=TEST, BLD=BUILD\nSF=SEARCH_FILES, SC=SEARCH_CONTENT, NAV=NAVIGATE'
    ax.text(0.02, 0.02, legend_text, transform=ax.transAxes,
            fontsize=9, verticalalignment='bottom',
            bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))

    plt.tight_layout()
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"Saved: {output_file}")
    plt.close()

def main():
    """Generate both visualizations."""
    print("Generating tool sequence pattern visualizations...")

    # Qwen
    create_bar_chart(QWEN_CSV, 'Qwen Code', 'qwen_top5_patterns_window5.png')

    # Claude
    create_bar_chart(CLAUDE_CSV, 'Claude Code', 'claude_top5_patterns_window5.png')

    print("\nTop 5 patterns for each agent:")
    print("\n=== QWEN ===")
    qwen_df = pd.read_csv(QWEN_CSV)
    qwen_total = qwen_df['frequency'].sum()
    print(f"Total window=5 sequences: {qwen_total}")
    for i, row in qwen_df.head(5).iterrows():
        pct = (row['frequency'] / qwen_total) * 100
        print(f"{i+1}. {row['tool_sequence']}")
        print(f"   Frequency: {row['frequency']} ({pct:.2f}%)")

    print("\n=== CLAUDE ===")
    claude_df = pd.read_csv(CLAUDE_CSV)
    claude_total = claude_df['frequency'].sum()
    print(f"Total window=5 sequences: {claude_total}")
    for i, row in claude_df.head(5).iterrows():
        pct = (row['frequency'] / claude_total) * 100
        print(f"{i+1}. {row['tool_sequence']}")
        print(f"   Frequency: {row['frequency']} ({pct:.2f}%)")

    print("\nDone!")

if __name__ == '__main__':
    main()
