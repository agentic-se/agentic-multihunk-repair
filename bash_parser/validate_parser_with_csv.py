#!/usr/bin/env python3
"""
Validate ShellCommandParser against real CSV data.

This script reads actual commands from multiple CSV files (Gemini, Claude, Qwen)
and validates the parser behavior on 100+ real-world examples.

Run with: python validate_parser_with_csv.py
"""

import csv
import sys
from pathlib import Path
from collections import Counter, defaultdict
from typing import List, Dict, Tuple
from shell_command_parser import ShellCommandParser


def load_commands_from_csv(csv_path: Path, limit: int = None) -> List[Tuple[str, str, int]]:
    """
    Load shell commands from a tools_count CSV file.

    Args:
        csv_path: Path to the CSV file
        limit: Maximum number of unique commands to load

    Returns:
        List of (bug_id, command, count) tuples
    """
    commands = []

    if not csv_path.exists():
        print(f"Warning: {csv_path} not found")
        return commands

    with csv_path.open(newline='') as f:
        reader = csv.DictReader(f)
        for row in reader:
            # For Gemini/Qwen: function_name column
            # For Claude: tool_name column
            tool_col = row.get('function_name') or row.get('tool_name', '')

            if tool_col in ('run_shell_command', 'Bash'):
                bug = row.get('bug', 'unknown')
                command = row.get('command', '').strip()
                count = int(row.get('count', '1') or '1')

                if command:
                    commands.append((bug, command, count))

            if limit and len(commands) >= limit:
                break

    return commands


def analyze_parsing_results(commands: List[Tuple[str, str, int]]) -> Dict:
    """
    Analyze parser performance on a set of commands.

    Returns:
        Dictionary with analysis results
    """
    parser = ShellCommandParser()

    stats = {
        'total_commands': len(commands),
        'parsed_successfully': 0,
        'failed_to_parse': 0,
        'empty_results': 0,
        'command_type_distribution': Counter(),
        'extracted_command_distribution': Counter(),
        'examples_by_category': defaultdict(list),
        'problematic_commands': [],
    }

    for bug, command, count in commands:
        try:
            result = parser.parse_command(command)

            if result:
                stats['parsed_successfully'] += 1

                for cmd in result:
                    stats['extracted_command_distribution'][cmd] += count
                    category = parser.categorize_command(cmd)
                    stats['command_type_distribution'][category] += count

                    # Keep examples
                    if len(stats['examples_by_category'][category]) < 5:
                        stats['examples_by_category'][category].append(
                            (bug, command[:100], result)
                        )
            else:
                stats['empty_results'] += 1
                stats['problematic_commands'].append((bug, command[:100]))

        except Exception as e:
            stats['failed_to_parse'] += 1
            stats['problematic_commands'].append((bug, command[:100], str(e)))

    return stats


def print_analysis(name: str, stats: Dict):
    """Print analysis results in a readable format."""
    print("\n" + "=" * 80)
    print(f"ANALYSIS: {name}")
    print("=" * 80)

    print(f"\nTotal commands analyzed: {stats['total_commands']}")
    print(f"Parsed successfully: {stats['parsed_successfully']}")
    print(f"Empty results: {stats['empty_results']}")
    print(f"Failed to parse: {stats['failed_to_parse']}")

    success_rate = (stats['parsed_successfully'] / max(stats['total_commands'], 1)) * 100
    print(f"Success rate: {success_rate:.1f}%")

    print("\n" + "-" * 80)
    print("COMMAND CATEGORY DISTRIBUTION")
    print("-" * 80)
    for category, count in stats['command_type_distribution'].most_common():
        print(f"  {category:30s}: {count:5d}")

    print("\n" + "-" * 80)
    print("TOP EXTRACTED COMMANDS")
    print("-" * 80)
    for cmd, count in stats['extracted_command_distribution'].most_common(20):
        print(f"  {cmd:30s}: {count:5d}")

    if stats['problematic_commands']:
        print("\n" + "-" * 80)
        print(f"PROBLEMATIC COMMANDS (showing first 10)")
        print("-" * 80)
        for i, item in enumerate(stats['problematic_commands'][:10], 1):
            if len(item) == 3:
                bug, cmd, error = item
                print(f"  {i}. [{bug}] {cmd}")
                print(f"      Error: {error}")
            else:
                bug, cmd = item
                print(f"  {i}. [{bug}] {cmd}")
                print(f"      (empty result)")

    print("\n" + "-" * 80)
    print("EXAMPLE EXTRACTIONS BY CATEGORY")
    print("-" * 80)
    for category in sorted(stats['examples_by_category'].keys()):
        print(f"\n  {category}:")
        for bug, original_cmd, extracted in stats['examples_by_category'][category][:3]:
            print(f"    Input:  {original_cmd}")
            print(f"    Output: {extracted}")


def validate_specific_cases():
    """Validate specific important cases that must work correctly."""
    parser = ShellCommandParser()

    test_cases = [
        # (input_command, expected_commands, description)
        (
            "defects4j test -t org.apache.commons.cli.BasicParserTest::testPropertyOptionGroup && "
            "defects4j test -t org.apache.commons.cli.BasicParserTest::testPropertyOptionUnexpected && "
            "defects4j test -t org.apache.commons.cli.DefaultParserTest::testPropertyOptionGroup",
            ["defects4j test"],
            "Multiple defects4j test commands should deduplicate"
        ),
        (
            "defects4j compile && defects4j test",
            ["defects4j compile", "defects4j test"],
            "Compile and test should both be extracted"
        ),
        (
            "ant clean && ant compile.test && defects4j test",
            ["ant", "defects4j test"],
            "Mixed build commands"
        ),
        (
            "git diff > fix.patch",
            ["git diff"],
            "Git diff with redirection"
        ),
        (
            "ls -t all_tests_trace.*.log | head -n 1",
            ["ls", "head"],
            "Pipe with ls and head"
        ),
        (
            "./run_bug_exposing_tests.sh",
            ["run_bug_exposing_tests.sh"],
            "Test script"
        ),
    ]

    print("\n" + "=" * 80)
    print("CRITICAL TEST CASES VALIDATION")
    print("=" * 80)

    all_passed = True
    for i, (input_cmd, expected, description) in enumerate(test_cases, 1):
        result = parser.parse_command(input_cmd)
        passed = result == expected

        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"\n{i}. {description}")
        print(f"   Status: {status}")
        print(f"   Input:    {input_cmd[:70]}")
        print(f"   Expected: {expected}")
        print(f"   Got:      {result}")

        if not passed:
            all_passed = False

    return all_passed


def main():
    """Main validation function."""
    print("=" * 80)
    print("SHELL COMMAND PARSER VALIDATION")
    print("=" * 80)
    print("\nThis script validates the parser against 100+ real CSV examples")
    print("from Gemini, Claude, and Qwen agent runs.\n")

    repo_root = Path(__file__).resolve().parents[1]
    results_dir = repo_root / "results"

    # Define CSV paths
    csv_files = {
        "Gemini": results_dir / "gemini_cli_results" / "tools_count_gemini.csv",
        "Claude": results_dir / "claude_code_results" / "claude_results" / "tools_count_claude.csv",
        "Qwen": results_dir / "qwen_code_results" / "qwen_results" / "tools_count_qwen.csv",
    }

    all_commands = []
    for name, path in csv_files.items():
        commands = load_commands_from_csv(path, limit=150)
        print(f"Loaded {len(commands)} commands from {name}")
        all_commands.extend(commands)

    print(f"\nTotal commands loaded: {len(all_commands)}")

    # Analyze each dataset separately
    for name, path in csv_files.items():
        commands = load_commands_from_csv(path, limit=150)
        if commands:
            stats = analyze_parsing_results(commands)
            print_analysis(name, stats)

    # Validate critical cases
    critical_passed = validate_specific_cases()

    # Final summary
    print("\n" + "=" * 80)
    print("FINAL VALIDATION SUMMARY")
    print("=" * 80)

    combined_stats = analyze_parsing_results(all_commands)
    success_rate = (combined_stats['parsed_successfully'] / max(combined_stats['total_commands'], 1)) * 100

    print(f"\nTotal commands validated: {combined_stats['total_commands']}")
    print(f"Overall success rate: {success_rate:.1f}%")
    print(f"Critical test cases: {'✓ ALL PASSED' if critical_passed else '✗ SOME FAILED'}")

    if success_rate >= 95.0 and critical_passed:
        print("\n✓ VALIDATION SUCCESSFUL - Parser is ready for production use!")
        return 0
    elif success_rate >= 90.0:
        print("\n⚠ VALIDATION MOSTLY SUCCESSFUL - Review problematic commands above")
        return 0
    else:
        print("\n✗ VALIDATION FAILED - Parser needs improvement")
        return 1


if __name__ == '__main__':
    sys.exit(main())
