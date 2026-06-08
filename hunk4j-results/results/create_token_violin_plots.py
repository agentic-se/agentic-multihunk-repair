#!/usr/bin/env python3
"""
Create violin plots for input and output token distribution across agents.
Shows pass vs fail outcomes with individual y-axis scales per agent.
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
    """Normalize bug_id format (handle both underscore and dash)."""
    return bug_id.replace('_', '-')


def load_token_data(csv_path):
    """Load token and duration data from CSV."""
    tokens = {}
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            bug_id = normalize_bug_id(row['bug_id'])
            duration = float(row['time_duration'])

            # Skip bugs with duration < 30 seconds
            if duration < 30:
                continue

            # Handle different column name formats (Codex vs others)
            input_col = 'input_token' if 'input_token' in row else 'total_input_token'
            output_col = 'output_token' if 'output_token' in row else 'total_output_token'

            tokens[bug_id] = {
                'input_tokens': int(row[input_col]),
                'output_tokens': int(row[output_col]),
                'duration': duration
            }
    return tokens


def load_repair_ability(csv_path):
    """Load repair ability data (pass/fail status)."""
    repairs = {}
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            bug_id = normalize_bug_id(row['bug_id'])
            repairs[bug_id] = {
                'repair': int(row['repair']),
                'compile_fail': int(row['compile_fail'])
            }
    return repairs


def merge_data(token_data, repair_data):
    """Merge token and repair data."""
    passed = []
    failed = []

    for bug_id in token_data:
        if bug_id in repair_data:
            entry = {
                'bug_id': bug_id,
                'input_tokens': token_data[bug_id]['input_tokens'],
                'output_tokens': token_data[bug_id]['output_tokens'],
                'duration': token_data[bug_id]['duration'],
                'repair': repair_data[bug_id]['repair']
            }

            if entry['repair'] == 1:
                passed.append(entry)
            else:
                failed.append(entry)

    return passed, failed


def create_violin_plot(all_data, token_type='input'):
    """Create violin plot for input or output tokens."""

    fig, axes = plt.subplots(1, 4, figsize=(16, 5))

    # Order: Qwen, Gemini, Codex, Claude
    agent_names = ['Qwen Code', 'Gemini CLI', 'OpenAI Codex', 'Claude Code']

    for idx, agent_name in enumerate(agent_names):
        ax = axes[idx]

        passed, failed = all_data[agent_name]

        # Extract token values
        if token_type == 'input':
            pass_tokens = [d['input_tokens'] for d in passed]
            fail_tokens = [d['input_tokens'] for d in failed]
            ylabel = 'Input Tokens'
        else:
            pass_tokens = [d['output_tokens'] for d in passed]
            fail_tokens = [d['output_tokens'] for d in failed]
            ylabel = 'Output Tokens'

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
        ax.set_title(agent_name, fontweight='bold')

        # Use log scale for Claude Code due to extreme outliers
        if agent_name == 'Claude Code' and token_type == 'input':
            ax.set_yscale('log')
            ax.yaxis.set_major_formatter(FuncFormatter(format_large_number))
            # Add log scale indicator to y-label
            ax.set_ylabel(ylabel + ' (Log scale)', fontweight='bold')
        else:
            # Format y-axis with K, M, B suffixes
            ax.yaxis.set_major_formatter(FuncFormatter(format_large_number))
            ax.set_ylabel(ylabel, fontweight='bold')

        # Add grid
        ax.grid(True, axis='y', alpha=0.3, linestyle='--', linewidth=0.5)
        ax.set_axisbelow(True)

        # Print statistics
        print(f"\n{agent_name} - {token_type.capitalize()} Tokens:")
        print(f"  Pass: n={len(pass_tokens)}, mean={np.mean(pass_tokens):,.0f}, median={np.median(pass_tokens):,.0f}")
        print(f"  Fail: n={len(fail_tokens)}, mean={np.mean(fail_tokens):,.0f}, median={np.median(fail_tokens):,.0f}")

    plt.tight_layout()

    return fig


def main():
    """Main function to create violin plots."""

    # Define agent configurations (ordered: Qwen, Gemini, Codex, Claude)
    agents = {
        'Qwen Code': {
            'token_path': 'qwen_code_results/qwen_results/token_and_duration_qwen.csv',
            'repair_path': 'qwen_code_results/qwen_results/qwen_repair_ability.csv'
        },
        'Gemini CLI': {
            'token_path': 'gemini_cli_results/token_and_duration_gemini.csv',
            'repair_path': 'gemini_cli_results/gemini_repair_ability.csv'
        },
        'OpenAI Codex': {
            'token_path': 'openai_codex_results/results-codex/token_and_duration_codex.csv',
            'repair_path': 'openai_codex_results/results-codex/codex_repair_ability.csv'
        },
        'Claude Code': {
            'token_path': 'claude_code_results/claude_results/token_and_duration_claude.csv',
            'repair_path': 'claude_code_results/claude_results/claude_repair_ability.csv'
        }
    }

    # Load and merge data for all agents
    all_data = {}
    print("Loading data for all agents...")
    print("=" * 80)

    for agent_name, config in agents.items():
        print(f"\nProcessing {agent_name}...")
        token_data = load_token_data(config['token_path'])
        repair_data = load_repair_ability(config['repair_path'])
        passed, failed = merge_data(token_data, repair_data)

        print(f"  After filtering (duration >= 30s):")
        print(f"    Pass: {len(passed)}")
        print(f"    Fail: {len(failed)}")
        print(f"    Total: {len(passed) + len(failed)}")

        all_data[agent_name] = (passed, failed)

    print("\n" + "=" * 80)

    # Create output directory
    output_dir = Path('analysis/figures')
    output_dir.mkdir(parents=True, exist_ok=True)

    # Create input token violin plot
    print("\nCreating input token violin plot...")
    fig_input = create_violin_plot(all_data, token_type='input')
    output_input = output_dir / 'agent_input_token_distribution_violin.pdf'
    fig_input.savefig(output_input, format='pdf', bbox_inches='tight', dpi=300)
    print(f"Saved: {output_input}")

    # Create output token violin plot
    print("\nCreating output token violin plot...")
    fig_output = create_violin_plot(all_data, token_type='output')
    output_output = output_dir / 'agent_output_token_distribution_violin.pdf'
    fig_output.savefig(output_output, format='pdf', bbox_inches='tight', dpi=300)
    print(f"Saved: {output_output}")

    print("\n" + "=" * 80)
    print("Violin plots created successfully!")

    plt.show()


if __name__ == "__main__":
    main()
