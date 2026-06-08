#!/usr/bin/env python3
"""
Script to generate a JSON file containing all bugs fixed by each coding agent.
Used for creating Venn diagrams showing overlap of fixes across coding agents.
For TOSEM paper submission.
"""

import csv
import json
from pathlib import Path


def get_fixed_bugs(csv_path):
    """
    Extract bug IDs where repair=1 from a repair ability CSV file.

    Args:
        csv_path (Path): Path to the repair ability CSV file

    Returns:
        list: List of bug IDs that were successfully repaired (repair=1)
    """
    fixed_bugs = []

    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)

        for row in reader:
            bug_id = row['bug_id']
            repair = int(row['repair'])

            # Normalize bug ID: replace hyphen with underscore for consistency
            bug_id = bug_id.replace('-', '_')

            # Only include bugs where repair=1 (successful fix)
            if repair == 1:
                fixed_bugs.append(bug_id)

    return fixed_bugs


def main():
    """Main function to generate fixed bugs JSON file."""

    # Define paths to repair ability CSV files for each agent
    gemini_csv = Path("gemini_cli_results/gemini_repair_ability.csv")
    qwen_csv = Path("qwen_code_results/qwen_results/qwen_repair_ability.csv")
    claude_csv = Path("claude_code_results/claude_results/claude_repair_ability.csv")
    codex_csv = Path("openai_codex_results/results-codex/codex_repair_ability.csv")

    # Extract fixed bugs for each agent
    print("Extracting fixed bugs for each agent...")

    gemini_fixed = get_fixed_bugs(gemini_csv)
    print(f"  Gemini CLI: {len(gemini_fixed)} bugs fixed")

    qwen_fixed = get_fixed_bugs(qwen_csv)
    print(f"  Qwen Code: {len(qwen_fixed)} bugs fixed")

    claude_fixed = get_fixed_bugs(claude_csv)
    print(f"  Claude Code: {len(claude_fixed)} bugs fixed")

    codex_fixed = get_fixed_bugs(codex_csv)
    print(f"  OpenAI Codex: {len(codex_fixed)} bugs fixed")

    # Create the output structure
    fixed_bugs_by_agent = {
        "gemini_cli": gemini_fixed,
        "qwen_code": qwen_fixed,
        "claude_code": claude_fixed,
        "openai_codex": codex_fixed
    }

    # Write to JSON file
    output_path = Path("fixed_bugs_by_agent.json")

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(fixed_bugs_by_agent, f, indent=2)

    print(f"\nResults saved to {output_path}")
    print(f"\nSummary:")
    print(f"  Total bugs fixed by Gemini CLI: {len(gemini_fixed)}")
    print(f"  Total bugs fixed by Qwen Code: {len(qwen_fixed)}")
    print(f"  Total bugs fixed by Claude Code: {len(claude_fixed)}")
    print(f"  Total bugs fixed by OpenAI Codex: {len(codex_fixed)}")


if __name__ == "__main__":
    main()
