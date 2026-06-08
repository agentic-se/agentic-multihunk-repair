#!/usr/bin/env python3
"""
Analyze Claude cache token usage.
"""

import csv
import numpy as np


def normalize_bug_id(bug_id):
    return bug_id.replace('_', '-')


def load_claude_data():
    """Load Claude token data including cache information."""
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

    # Merge
    passed = []
    failed = []

    for bug_id in tokens:
        if bug_id in repairs:
            entry = {
                'bug_id': bug_id,
                'input': tokens[bug_id]['input'],
                'output': tokens[bug_id]['output'],
                'cache_creation': tokens[bug_id]['cache_creation'],
                'cache_read': tokens[bug_id]['cache_read'],
                'total_input': tokens[bug_id]['input'] + tokens[bug_id]['cache_creation'] + tokens[bug_id]['cache_read']
            }

            if repairs[bug_id] == 1:
                passed.append(entry)
            else:
                failed.append(entry)

    return passed, failed


def main():
    print("="*80)
    print("CLAUDE CACHE TOKEN ANALYSIS")
    print("="*80)

    passed, failed = load_claude_data()

    print(f"\nSample sizes:")
    print(f"  Pass: {len(passed)}")
    print(f"  Fail: {len(failed)}")

    # Pass statistics
    pass_input = np.array([d['input'] for d in passed])
    pass_cache_creation = np.array([d['cache_creation'] for d in passed])
    pass_cache_read = np.array([d['cache_read'] for d in passed])
    pass_total_input = np.array([d['total_input'] for d in passed])
    pass_output = np.array([d['output'] for d in passed])

    print(f"\nPASS (n={len(passed)}):")
    print(f"  New input tokens:        {np.mean(pass_input):>12,.0f}  (std={np.std(pass_input, ddof=1):>10,.0f})")
    print(f"  Cache creation tokens:   {np.mean(pass_cache_creation):>12,.0f}  (std={np.std(pass_cache_creation, ddof=1):>10,.0f})")
    print(f"  Cache read tokens:       {np.mean(pass_cache_read):>12,.0f}  (std={np.std(pass_cache_read, ddof=1):>10,.0f})")
    print(f"  Total input (new+cache): {np.mean(pass_total_input):>12,.0f}  (std={np.std(pass_total_input, ddof=1):>10,.0f})")
    print(f"  Output tokens:           {np.mean(pass_output):>12,.0f}")

    # Fail statistics
    fail_input = np.array([d['input'] for d in failed])
    fail_cache_creation = np.array([d['cache_creation'] for d in failed])
    fail_cache_read = np.array([d['cache_read'] for d in failed])
    fail_total_input = np.array([d['total_input'] for d in failed])
    fail_output = np.array([d['output'] for d in failed])

    print(f"\nFAIL (n={len(failed)}):")
    print(f"  New input tokens:        {np.mean(fail_input):>12,.0f}  (std={np.std(fail_input, ddof=1):>10,.0f})")
    print(f"  Cache creation tokens:   {np.mean(fail_cache_creation):>12,.0f}  (std={np.std(fail_cache_creation, ddof=1):>10,.0f})")
    print(f"  Cache read tokens:       {np.mean(fail_cache_read):>12,.0f}  (std={np.std(fail_cache_read, ddof=1):>10,.0f})")
    print(f"  Total input (new+cache): {np.mean(fail_total_input):>12,.0f}  (std={np.std(fail_total_input, ddof=1):>10,.0f})")
    print(f"  Output tokens:           {np.mean(fail_output):>12,.0f}")

    # Comparison
    print(f"\n{'='*80}")
    print("COMPARISON")
    print(f"{'='*80}")

    input_change = ((np.mean(fail_input) - np.mean(pass_input)) / np.mean(pass_input) * 100)
    cache_creation_change = ((np.mean(fail_cache_creation) - np.mean(pass_cache_creation)) / np.mean(pass_cache_creation) * 100)
    total_input_change = ((np.mean(fail_total_input) - np.mean(pass_total_input)) / np.mean(pass_total_input) * 100)
    cache_read_change = ((np.mean(fail_cache_read) - np.mean(pass_cache_read)) / np.mean(pass_cache_read) * 100)
    output_change = ((np.mean(fail_output) - np.mean(pass_output)) / np.mean(pass_output) * 100)

    print(f"\nFailed repairs vs Successful repairs:")
    print(f"  New input tokens:      {input_change:>+7.1f}%")
    print(f"  Cache creation tokens: {cache_creation_change:>+7.1f}%")
    print(f"  Total input tokens:    {total_input_change:>+7.1f}%")
    print(f"  Cache read tokens:     {cache_read_change:>+7.1f}%")
    print(f"  Output tokens:         {output_change:>+7.1f}%")

    # Cost analysis
    print(f"\n{'='*80}")
    print("COST ANALYSIS")
    print(f"{'='*80}")
    print("\nClaude pricing:")
    print("  - Input tokens: $3.00 per million")
    print("  - Cache creation: $3.75 per million (1.25x input)")
    print("  - Cache read: $0.30 per million (0.1x input)")
    print("  - Output tokens: $15.00 per million")

    # Pass costs
    pass_input_cost = np.mean(pass_input) / 1e6 * 3.00
    pass_cache_creation_cost = np.mean(pass_cache_creation) / 1e6 * 3.75
    pass_cache_read_cost = np.mean(pass_cache_read) / 1e6 * 0.30
    pass_output_cost = np.mean(pass_output) / 1e6 * 15.00
    pass_total_cost = pass_input_cost + pass_cache_creation_cost + pass_cache_read_cost + pass_output_cost

    print(f"\nCost per bug (Pass):")
    print(f"  New input:       ${pass_input_cost:.6f}")
    print(f"  Cache creation:  ${pass_cache_creation_cost:.6f}")
    print(f"  Cache read:      ${pass_cache_read_cost:.6f}")
    print(f"  Output:          ${pass_output_cost:.6f}")
    print(f"  Total:           ${pass_total_cost:.6f}")

    # Fail costs
    fail_input_cost = np.mean(fail_input) / 1e6 * 3.00
    fail_cache_creation_cost = np.mean(fail_cache_creation) / 1e6 * 3.75
    fail_cache_read_cost = np.mean(fail_cache_read) / 1e6 * 0.30
    fail_output_cost = np.mean(fail_output) / 1e6 * 15.00
    fail_total_cost = fail_input_cost + fail_cache_creation_cost + fail_cache_read_cost + fail_output_cost

    print(f"\nCost per bug (Fail):")
    print(f"  New input:       ${fail_input_cost:.6f}")
    print(f"  Cache creation:  ${fail_cache_creation_cost:.6f}")
    print(f"  Cache read:      ${fail_cache_read_cost:.6f}")
    print(f"  Output:          ${fail_output_cost:.6f}")
    print(f"  Total:           ${fail_total_cost:.6f}")

    print(f"\nTotal cost for 288 bugs (273 pass + 15 fail):")
    total_cost = (273 * pass_total_cost) + (15 * fail_total_cost)
    print(f"  ${total_cost:.2f}")


if __name__ == "__main__":
    main()
