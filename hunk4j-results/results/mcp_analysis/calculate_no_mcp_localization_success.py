#!/usr/bin/env python3
"""
Calculate localization success for Qwen and Gemini (without MCP) on the 50 MCP experiment bugs.
"""

import pandas as pd
import json
from pathlib import Path


def analyze_localization_success():
    """
    Analyze localization ability for both agents on the 50 bugs used in MCP experiments.

    Returns:
        dict: Localization success statistics for both agents.
    """
    # Load the 50 bugs for MCP experiment
    bugs_50_path = Path("50_random_bugs_for_mcp_experiments_tosem.json")
    with open(bugs_50_path, 'r', encoding='utf-8') as f:
        bugs_50_data = json.load(f)

    # Get the bug IDs (set for fast lookup)
    bugs_50 = set(bugs_50_data.keys())

    print(f"Loaded {len(bugs_50)} bugs from MCP experiment list")

    # Agent configuration
    agents = [
        {
            "key": "qwen_code",
            "name": "Qwen Code",
            "csv_path": "../qwen_code_results/qwen_results/qwen_localization_ability.csv"
        },
        {
            "key": "gemini_cli",
            "name": "Gemini CLI",
            "csv_path": "../gemini_cli_results/gemini_localization_ability.csv"
        }
    ]

    all_results = {}

    print("\n" + "=" * 70)
    print("Calculating localization success for agents on 50 MCP bugs")
    print("=" * 70)

    for agent in agents:
        csv_path = Path(agent["csv_path"])

        # Check if file exists
        if not csv_path.exists():
            print(f"\n{agent['name']}: CSV file not found at {csv_path}")
            continue

        # Load the localization data
        df = pd.read_csv(csv_path)

        # Filter to only the 50 MCP bugs
        df_filtered = df[df['bug_id'].isin(bugs_50)]

        # Remove any empty rows
        df_filtered = df_filtered.dropna()

        # Calculate success statistics
        total_bugs = len(df_filtered)
        successful_localizations = int(df_filtered['localization'].sum())
        failed_localizations = total_bugs - successful_localizations
        success_percentage = (successful_localizations / total_bugs) * 100 if total_bugs > 0 else 0.0

        # Prepare results
        results = {
            "agent": agent["key"],
            "agent_name": agent["name"],
            "total_bugs": total_bugs,
            "successful_localizations": successful_localizations,
            "failed_localizations": failed_localizations,
            "success_percentage": round(success_percentage, 2)
        }

        all_results[agent["key"]] = results

        print(f"\n{agent['name']}:")
        print(f"  Total bugs: {total_bugs}")
        print(f"  Successful localizations: {successful_localizations}")
        print(f"  Failed localizations: {failed_localizations}")
        print(f"  Success percentage: {success_percentage:.2f}%")

    return all_results


def main():
    """Main function to run analysis and save results."""
    # Run analysis
    all_results = analyze_localization_success()

    # Output path
    output_path = Path("no_mcp_localization_success.json")

    # Write to JSON file with pretty formatting
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(all_results, f, indent=2)

    print("\n" + "=" * 70)
    print(f"Results saved to {output_path}")
    print("=" * 70)


if __name__ == "__main__":
    main()
