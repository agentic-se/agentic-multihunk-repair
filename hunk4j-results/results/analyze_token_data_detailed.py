#!/usr/bin/env python3
"""
Detailed token usage analysis to understand the updated data.
Examines patterns, distributions, and cross-agent comparisons.
"""

import csv
import numpy as np
from pathlib import Path


def normalize_bug_id(bug_id):
    """Normalize bug_id format."""
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

            # Handle different column name formats
            input_col = 'input_token' if 'input_token' in row else 'total_input_token'
            output_col = 'output_token' if 'output_token' in row else 'total_output_token'

            tokens[bug_id] = {
                'input_tokens': int(row[input_col]),
                'output_tokens': int(row[output_col]),
                'duration': duration
            }
    return tokens


def load_repair_ability(csv_path):
    """Load repair ability data."""
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


def analyze_agent(agent_name, passed, failed):
    """Detailed analysis for one agent."""
    print(f"\n{'='*80}")
    print(f"{agent_name}")
    print(f"{'='*80}")

    # Sample sizes
    print(f"\nSample Sizes:")
    print(f"  Pass: {len(passed)}")
    print(f"  Fail: {len(failed)}")
    print(f"  Total: {len(passed) + len(failed)}")

    # Input token statistics
    pass_input = np.array([d['input_tokens'] for d in passed])
    fail_input = np.array([d['input_tokens'] for d in failed])

    print(f"\nInput Tokens:")
    print(f"  Pass:")
    print(f"    Mean:   {np.mean(pass_input):>12,.0f}")
    print(f"    Median: {np.median(pass_input):>12,.0f}")
    print(f"    Std:    {np.std(pass_input, ddof=1):>12,.0f}")
    print(f"    Min:    {np.min(pass_input):>12,.0f}")
    print(f"    Max:    {np.max(pass_input):>12,.0f}")
    print(f"    Q1:     {np.percentile(pass_input, 25):>12,.0f}")
    print(f"    Q3:     {np.percentile(pass_input, 75):>12,.0f}")

    print(f"  Fail:")
    print(f"    Mean:   {np.mean(fail_input):>12,.0f}")
    print(f"    Median: {np.median(fail_input):>12,.0f}")
    print(f"    Std:    {np.std(fail_input, ddof=1):>12,.0f}")
    print(f"    Min:    {np.min(fail_input):>12,.0f}")
    print(f"    Max:    {np.max(fail_input):>12,.0f}")
    print(f"    Q1:     {np.percentile(fail_input, 25):>12,.0f}")
    print(f"    Q3:     {np.percentile(fail_input, 75):>12,.0f}")

    input_change = ((np.mean(fail_input) - np.mean(pass_input)) / np.mean(pass_input) * 100)
    print(f"  → Failed repairs: {input_change:+.1f}% change in mean input tokens")

    # Output token statistics
    pass_output = np.array([d['output_tokens'] for d in passed])
    fail_output = np.array([d['output_tokens'] for d in failed])

    print(f"\nOutput Tokens:")
    print(f"  Pass:")
    print(f"    Mean:   {np.mean(pass_output):>12,.0f}")
    print(f"    Median: {np.median(pass_output):>12,.0f}")
    print(f"    Std:    {np.std(pass_output, ddof=1):>12,.0f}")

    print(f"  Fail:")
    print(f"    Mean:   {np.mean(fail_output):>12,.0f}")
    print(f"    Median: {np.median(fail_output):>12,.0f}")
    print(f"    Std:    {np.std(fail_output, ddof=1):>12,.0f}")

    output_change = ((np.mean(fail_output) - np.mean(pass_output)) / np.mean(pass_output) * 100)
    print(f"  → Failed repairs: {output_change:+.1f}% change in mean output tokens")

    # Duration analysis
    pass_duration = np.array([d['duration'] for d in passed])
    fail_duration = np.array([d['duration'] for d in failed])

    print(f"\nDuration (seconds):")
    print(f"  Pass: mean={np.mean(pass_duration):,.0f}, median={np.median(pass_duration):,.0f}")
    print(f"  Fail: mean={np.mean(fail_duration):,.0f}, median={np.median(fail_duration):,.0f}")

    return {
        'pass_input_mean': np.mean(pass_input),
        'fail_input_mean': np.mean(fail_input),
        'pass_output_mean': np.mean(pass_output),
        'fail_output_mean': np.mean(fail_output),
        'input_change_pct': input_change,
        'output_change_pct': output_change,
        'pass_count': len(passed),
        'fail_count': len(failed)
    }


def main():
    """Main analysis function."""

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

    print("="*80)
    print("DETAILED TOKEN USAGE ANALYSIS")
    print("="*80)

    all_results = {}

    # Analyze each agent
    for agent_name, config in agents.items():
        token_data = load_token_data(config['token_path'])
        repair_data = load_repair_ability(config['repair_path'])
        passed, failed = merge_data(token_data, repair_data)

        results = analyze_agent(agent_name, passed, failed)
        all_results[agent_name] = results

    # Cross-agent comparison
    print(f"\n{'='*80}")
    print("CROSS-AGENT COMPARISON")
    print(f"{'='*80}")

    print(f"\nRepair Success Rates:")
    for agent_name, results in all_results.items():
        total = results['pass_count'] + results['fail_count']
        rate = results['pass_count'] / total * 100
        print(f"  {agent_name:15s}: {results['pass_count']:3d}/{total:3d} = {rate:5.1f}%")

    print(f"\nMean Input Tokens (Successful Repairs):")
    sorted_by_input = sorted(all_results.items(), key=lambda x: x[1]['pass_input_mean'])
    for agent_name, results in sorted_by_input:
        print(f"  {agent_name:15s}: {results['pass_input_mean']:>12,.0f}")

    print(f"\nMean Output Tokens (Successful Repairs):")
    sorted_by_output = sorted(all_results.items(), key=lambda x: x[1]['pass_output_mean'])
    for agent_name, results in sorted_by_output:
        print(f"  {agent_name:15s}: {results['pass_output_mean']:>12,.0f}")

    print(f"\nInput Token Change for Failed Repairs:")
    for agent_name, results in all_results.items():
        print(f"  {agent_name:15s}: {results['input_change_pct']:>+7.1f}%")

    print(f"\nOutput Token Change for Failed Repairs:")
    for agent_name, results in all_results.items():
        print(f"  {agent_name:15s}: {results['output_change_pct']:>+7.1f}%")

    # Efficiency analysis
    print(f"\n{'='*80}")
    print("EFFICIENCY ANALYSIS")
    print(f"{'='*80}")

    print(f"\nTokens per Successful Repair (Input + Output):")
    for agent_name, results in sorted_by_input:
        total_tokens = results['pass_input_mean'] + results['pass_output_mean']
        print(f"  {agent_name:15s}: {total_tokens:>12,.0f}")

    print(f"\nTokens per Failed Repair (Input + Output):")
    sorted_by_fail = sorted(all_results.items(),
                           key=lambda x: x[1]['fail_input_mean'] + x[1]['fail_output_mean'])
    for agent_name, results in sorted_by_fail:
        total_tokens = results['fail_input_mean'] + results['fail_output_mean']
        print(f"  {agent_name:15s}: {total_tokens:>12,.0f}")

    print(f"\n{'='*80}")
    print("ANALYSIS COMPLETE")
    print(f"{'='*80}")


if __name__ == "__main__":
    main()
