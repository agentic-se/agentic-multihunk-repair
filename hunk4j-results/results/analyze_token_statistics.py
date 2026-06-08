#!/usr/bin/env python3
"""
Comprehensive token usage analysis across coding agents.
Generates statistics table and key insights for TOSEM paper.
"""

import csv
import numpy as np
from pathlib import Path


def normalize_bug_id(bug_id):
    """Normalize bug_id format (handle both underscore and dash)."""
    return bug_id.replace('_', '-')


def load_token_data(csv_path):
    """Load token and duration data from CSV, filtering duration < 30s."""
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


def calculate_statistics(data, token_type='input'):
    """Calculate comprehensive statistics for a dataset."""
    if token_type == 'input':
        values = np.array([d['input_tokens'] for d in data])
    else:
        values = np.array([d['output_tokens'] for d in data])

    return {
        'count': len(values),
        'mean': np.mean(values),
        'median': np.median(values),
        'std': np.std(values, ddof=1),
        'min': np.min(values),
        'max': np.max(values),
        'q1': np.percentile(values, 25),
        'q3': np.percentile(values, 75)
    }


def main():
    """Main analysis function."""

    # Define agent configurations
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

    print("=" * 80)
    print("TOKEN USAGE ANALYSIS ACROSS CODING AGENTS")
    print("=" * 80)
    print()

    results = {}

    # Analyze each agent
    for agent_name, config in agents.items():
        print(f"\n{agent_name}:")
        print("-" * 80)

        token_data = load_token_data(config['token_path'])
        repair_data = load_repair_ability(config['repair_path'])
        passed, failed = merge_data(token_data, repair_data)

        # Calculate statistics
        pass_input_stats = calculate_statistics(passed, 'input')
        fail_input_stats = calculate_statistics(failed, 'input')
        pass_output_stats = calculate_statistics(passed, 'output')
        fail_output_stats = calculate_statistics(failed, 'output')

        results[agent_name] = {
            'pass': {
                'input': pass_input_stats,
                'output': pass_output_stats
            },
            'fail': {
                'input': fail_input_stats,
                'output': fail_output_stats
            }
        }

        # Print results
        print(f"\nInput Tokens:")
        print(f"  Pass (n={pass_input_stats['count']:3d}): "
              f"mean={pass_input_stats['mean']:10,.0f}, "
              f"median={pass_input_stats['median']:10,.0f}, "
              f"std={pass_input_stats['std']:10,.0f}")
        print(f"  Fail (n={fail_input_stats['count']:3d}): "
              f"mean={fail_input_stats['mean']:10,.0f}, "
              f"median={fail_input_stats['median']:10,.0f}, "
              f"std={fail_input_stats['std']:10,.0f}")

        input_increase = ((fail_input_stats['mean'] - pass_input_stats['mean']) /
                         pass_input_stats['mean'] * 100)
        print(f"  → Failed repairs use {input_increase:+.1f}% more input tokens")

        print(f"\nOutput Tokens:")
        print(f"  Pass (n={pass_output_stats['count']:3d}): "
              f"mean={pass_output_stats['mean']:10,.0f}, "
              f"median={pass_output_stats['median']:10,.0f}, "
              f"std={pass_output_stats['std']:10,.0f}")
        print(f"  Fail (n={fail_output_stats['count']:3d}): "
              f"mean={fail_output_stats['mean']:10,.0f}, "
              f"median={fail_output_stats['median']:10,.0f}, "
              f"std={fail_output_stats['std']:10,.0f}")

        output_increase = ((fail_output_stats['mean'] - pass_output_stats['mean']) /
                          pass_output_stats['mean'] * 100)
        print(f"  → Failed repairs use {output_increase:+.1f}% more output tokens")

    # Generate LaTeX table
    print("\n" + "=" * 80)
    print("LATEX TABLE")
    print("=" * 80)
    print()

    # Generate analysis output directory
    output_dir = Path('analysis')
    output_dir.mkdir(parents=True, exist_ok=True)

    # Write LaTeX table
    latex_file = output_dir / 'token_usage_statistics_table.tex'
    with open(latex_file, 'w') as f:
        f.write("\\begin{table}[t]\n")
        f.write("\\centering\n")
        f.write("\\caption{Token Usage Statistics by Agent and Repair Outcome}\n")
        f.write("\\label{tab:token-usage-statistics}\n")
        f.write("\\begin{tabular}{@{}llrrrr@{}}\n")
        f.write("\\toprule\n")
        f.write("\\textbf{Agent} & \\textbf{Outcome} & \\textbf{n} & \\textbf{Input (mean)} & \\textbf{Output (mean)} & \\textbf{Std Dev} \\\\\n")
        f.write("\\midrule\n")

        agent_order = ['Qwen Code', 'Gemini CLI', 'OpenAI Codex', 'Claude Code']
        for agent_name in agent_order:
            data = results[agent_name]

            pass_n = data['pass']['input']['count']
            pass_input = data['pass']['input']['mean']
            pass_output = data['pass']['output']['mean']
            pass_std = data['pass']['input']['std']

            fail_n = data['fail']['input']['count']
            fail_input = data['fail']['input']['mean']
            fail_output = data['fail']['output']['mean']
            fail_std = data['fail']['input']['std']

            # Format numbers based on magnitude
            if pass_input >= 1e6:
                pass_input_str = f"{pass_input/1e6:.2f}M"
                fail_input_str = f"{fail_input/1e6:.2f}M"
                pass_std_str = f"{pass_std/1e6:.2f}M"
                fail_std_str = f"{fail_std/1e6:.2f}M"
            elif pass_input >= 1e3:
                pass_input_str = f"{pass_input/1e3:.1f}K"
                fail_input_str = f"{fail_input/1e3:.1f}K"
                pass_std_str = f"{pass_std/1e3:.1f}K"
                fail_std_str = f"{fail_std/1e3:.1f}K"
            else:
                pass_input_str = f"{pass_input:.0f}"
                fail_input_str = f"{fail_input:.0f}"
                pass_std_str = f"{pass_std:.0f}"
                fail_std_str = f"{fail_std:.0f}"

            pass_output_str = f"{pass_output/1e3:.1f}K" if pass_output >= 1e3 else f"{pass_output:.0f}"
            fail_output_str = f"{fail_output/1e3:.1f}K" if fail_output >= 1e3 else f"{fail_output:.0f}"

            f.write(f"{agent_name} & Pass & {pass_n} & {pass_input_str} & {pass_output_str} & {pass_std_str} \\\\\n")
            f.write(f"            & Fail & {fail_n} & {fail_input_str} & {fail_output_str} & {fail_std_str} \\\\\n")
            if agent_name != agent_order[-1]:
                f.write("\\midrule\n")

        f.write("\\bottomrule\n")
        f.write("\\end{tabular}\n")
        f.write("\\begin{tablenotes}\n")
        f.write("\\small\n")
        f.write("\\item Input and output tokens shown as mean values. Std Dev refers to input tokens.\n")
        f.write("\\item Bugs with duration $<$ 30 seconds excluded (incomplete processing).\n")
        f.write("\\end{tablenotes}\n")
        f.write("\\end{table}\n")

    print(latex_file.read_text())
    print(f"\nLaTeX table saved to: {latex_file}")

    print("\n" + "=" * 80)
    print("ANALYSIS COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    main()
