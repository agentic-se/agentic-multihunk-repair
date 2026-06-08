#!/usr/bin/env python3
"""
Analyze and visualize token statistics (input/output) across coding agents.
Shows distribution by agent and pass/fail status.
"""

import csv
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
import pandas as pd

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
            # Handle different column name formats (Codex vs others)
            input_col = 'input_token' if 'input_token' in row else 'total_input_token'
            output_col = 'output_token' if 'output_token' in row else 'total_output_token'
            tokens[bug_id] = {
                'input_tokens': int(row[input_col]),
                'output_tokens': int(row[output_col]),
                'duration': float(row['time_duration'])
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
    merged = []
    for bug_id in token_data:
        if bug_id in repair_data:
            entry = {
                'bug_id': bug_id,
                'input_tokens': token_data[bug_id]['input_tokens'],
                'output_tokens': token_data[bug_id]['output_tokens'],
                'duration': token_data[bug_id]['duration'],
                'repair': repair_data[bug_id]['repair'],
                'compile_fail': repair_data[bug_id]['compile_fail']
            }
            merged.append(entry)
    return merged


def main():
    """Main analysis function."""

    # Define agent configurations
    agents = {
        'Qwen Code': {
            'token_path': 'qwen_code_results/qwen_results/token_and_duration_qwen.csv',
            'repair_path': 'qwen_code_results/qwen_results/qwen_repair_ability.csv',
            'color': '#C73E1D'
        },
        'Gemini CLI': {
            'token_path': 'gemini_cli_results/token_and_duration_gemini.csv',
            'repair_path': 'gemini_cli_results/gemini_repair_ability.csv',
            'color': '#F18F01'
        },
        'OpenAI Codex': {
            'token_path': 'openai_codex_results/results-codex/token_and_duration_codex.csv',
            'repair_path': 'openai_codex_results/results-codex/codex_repair_ability.csv',
            'color': '#A23B72'
        },
        'Claude Code': {
            'token_path': 'claude_code_results/claude_results/token_and_duration_claude.csv',
            'repair_path': 'claude_code_results/claude_results/claude_repair_ability.csv',
            'color': '#2E86AB'
        }
    }

    # Load and merge data for all agents
    all_data = {}
    print("Loading data for all agents...")
    print("=" * 80)

    for agent_name, config in agents.items():
        print(f"\n{agent_name}:")
        token_data = load_token_data(config['token_path'])
        repair_data = load_repair_ability(config['repair_path'])
        merged = merge_data(token_data, repair_data)

        # Calculate statistics
        input_tokens = [d['input_tokens'] for d in merged]
        output_tokens = [d['output_tokens'] for d in merged]
        passed = [d for d in merged if d['repair'] == 1]
        failed = [d for d in merged if d['repair'] == 0]

        print(f"  Total bugs: {len(merged)}")
        print(f"  Passed: {len(passed)} ({len(passed)/len(merged)*100:.1f}%)")
        print(f"  Failed: {len(failed)} ({len(failed)/len(merged)*100:.1f}%)")
        print(f"  Input tokens:  mean={np.mean(input_tokens):,.0f}, median={np.median(input_tokens):,.0f}")
        print(f"  Output tokens: mean={np.mean(output_tokens):,.0f}, median={np.median(output_tokens):,.0f}")

        all_data[agent_name] = {
            'merged': merged,
            'color': config['color'],
            'passed': passed,
            'failed': failed
        }

    print("\n" + "=" * 80)
    print("\nData loaded successfully. Ready to create visualizations.")
    print("Visualizations will be saved to analysis/figures/")

    # Create output directory
    output_dir = Path('analysis/figures')
    output_dir.mkdir(parents=True, exist_ok=True)

    return all_data, agents


if __name__ == "__main__":
    data, agents = main()
