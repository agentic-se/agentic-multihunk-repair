#!/usr/bin/env python3
"""
Check how many bugs would be filtered out with time_duration < 30 seconds.
"""

import csv

agents = {
    'Qwen Code': 'qwen_code_results/qwen_results/token_and_duration_qwen.csv',
    'Gemini CLI': 'gemini_cli_results/token_and_duration_gemini.csv',
    'OpenAI Codex': 'openai_codex_results/results-codex/token_and_duration_codex.csv',
    'Claude Code': 'claude_code_results/claude_results/token_and_duration_claude.csv'
}

print("Checking duration filtering (< 30 seconds)...")
print("=" * 80)

for agent_name, csv_path in agents.items():
    print(f"\n{agent_name}:")

    total_count = 0
    filtered_out = 0
    kept = 0

    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            total_count += 1
            duration = float(row['time_duration'])
            if duration < 30:
                filtered_out += 1
            else:
                kept += 1

    print(f"  Total bugs: {total_count}")
    print(f"  Duration < 30s (filtered out): {filtered_out} ({filtered_out/total_count*100:.1f}%)")
    print(f"  Duration >= 30s (kept): {kept} ({kept/total_count*100:.1f}%)")

print("\n" + "=" * 80)
print("Summary: Bugs with duration < 30s will be excluded from analysis.")
