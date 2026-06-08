#!/usr/bin/env python3
"""
Calculate localization success statistics for all coding agents.
Outputs results to individual JSON files in each agent's result directory.
"""
import pandas as pd
import json
from pathlib import Path

# Agent configuration with their localization file paths
# Order: Qwen, Gemini, Codex, Claude
agents = [
    {
        "key": "qwen_code",
        "name": "Qwen Code",
        "csv_path": "qwen_code_results/qwen_results/qwen_localization_ability.csv",
        "output_dir": "qwen_code_result_analysis"
    },
    {
        "key": "gemini_cli",
        "name": "Gemini CLI",
        "csv_path": "gemini_cli_results/gemini_localization_ability.csv",
        "output_dir": "gemini_cli_result_analysis"
    },
    {
        "key": "openai_codex",
        "name": "OpenAI Codex",
        "csv_path": "openai_codex_results/results-codex/codex_localization_ability.csv",
        "output_dir": "openai_codex_result_analysis"
    },
    {
        "key": "claude_code",
        "name": "Claude Code",
        "csv_path": "claude_code_results/claude_results/claude_localization_ability.csv",
        "output_dir": "claude_code_result_analysis"
    }
]

all_results = {}

print("Calculating localization success for all agents...")
print("=" * 70)

for agent in agents:
    csv_path = agent["csv_path"]

    # Check if file exists
    if not Path(csv_path).exists():
        print(f"\n{agent['name']}: CSV file not found at {csv_path}")
        continue

    # Load the localization data
    df = pd.read_csv(csv_path)

    # Remove any empty rows
    df = df.dropna()

    # Calculate success statistics
    total_bugs = len(df)
    successful_localizations = int(df['localization'].sum())
    failed_localizations = total_bugs - successful_localizations
    success_percentage = (successful_localizations / total_bugs) * 100

    # Prepare results
    results = {
        "agent": agent["key"],
        "agent_name": agent["name"],
        "total_bugs": total_bugs,
        "successful_localizations": successful_localizations,
        "failed_localizations": failed_localizations,
        "success_percentage": round(success_percentage, 2),
        "success_summary": f"{successful_localizations} ({success_percentage:.2f}%)"
    }

    all_results[agent["key"]] = results

    print(f"\n{agent['name']}:")
    print(f"  Total bugs: {total_bugs}")
    print(f"  Successful localizations: {successful_localizations}")
    print(f"  Failed localizations: {failed_localizations}")
    print(f"  Success percentage: {success_percentage:.2f}%")

# Save combined results to a single JSON file
combined_output = "agents_localization_success.json"
with open(combined_output, 'w') as f:
    json.dump(all_results, f, indent=2)

print("\n" + "=" * 70)
print(f"Combined results saved to: {combined_output}")
