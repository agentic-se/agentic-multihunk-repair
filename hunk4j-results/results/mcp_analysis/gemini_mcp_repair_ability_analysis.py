#!/usr/bin/env python3
"""
Analysis script for Gemini CLI MCP repair ability results.
Generates summary statistics for TOSEM paper submission.
"""

import csv
import json
from pathlib import Path


def analyze_gemini_mcp_repair_ability():
    """
    Analyze gemini_repair_ability_mcp.csv and generate summary statistics.

    Returns:
        dict: Summary statistics including total bugs, compile success,
              repair success, and regression reduction metrics.
    """
    # Path to input CSV
    csv_path = Path("../gemini_cli_results/mcp-gemini/gemini_repair_ability_mcp.csv")

    # Initialize counters
    total_bugs = 0
    compile_success_count = 0
    repair_success_count = 0
    regression_reduction_total = 0
    regression_reduction_count = 0  # Count of bugs with valid regression_reduction

    # Read and process CSV
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)

        for row in reader:
            total_bugs += 1

            # Parse fields
            repair = int(row['repair'])
            compile_fail = int(row['compile_fail'])
            regression_reduction_str = row['regression_reduction']

            # Count compile successes (compile_fail = 0 means success)
            if compile_fail == 0:
                compile_success_count += 1

            # Count repair successes (repair = 1 means success)
            if repair == 1:
                repair_success_count += 1

            # Process regression_reduction (only if not "undefined")
            # regression_reduction = failed_test_prior - failed_test_after
            # If positive: fewer tests failed after (better - regression reduced)
            # If negative: more tests failed after (worse - regression introduced)
            # If "undefined": compile failed, no valid test results
            if regression_reduction_str != "undefined":
                regression_reduction = int(regression_reduction_str)
                regression_reduction_total += regression_reduction
                regression_reduction_count += 1

    # Calculate averages (2 decimal points)
    # Compile and repair success are percentages (multiply by 100)
    compile_success_avg = round((compile_success_count / total_bugs) * 100, 2) if total_bugs > 0 else 0.0
    repair_success_avg = round((repair_success_count / total_bugs) * 100, 2) if total_bugs > 0 else 0.0
    # Regression reduction is an average count (do NOT multiply by 100)
    # Only calculate from bugs where regression_reduction is not "undefined"
    regression_reduction_avg = round(regression_reduction_total / regression_reduction_count, 2) if regression_reduction_count > 0 else 0.0

    # Create summary dictionary
    summary = {
        "total_bugs": total_bugs,
        "compile_success_total": compile_success_count,
        "compile_success_avg": compile_success_avg,
        "repair_success_total": repair_success_count,
        "repair_success_avg": repair_success_avg,
        "regression_reduction_total": regression_reduction_total,
        "regression_reduction_count": regression_reduction_count,
        "regression_reduction_avg": regression_reduction_avg
    }

    return summary


def main():
    """Main function to run analysis and save results."""
    # Run analysis
    summary = analyze_gemini_mcp_repair_ability()

    # Output path
    output_path = Path("gemini_mcp_repair_ability_analysis.json")

    # Write to JSON file with pretty formatting
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2)

    print(f"Analysis complete. Results saved to {output_path}")
    print(f"\nSummary Statistics:")
    print(f"  Total bugs: {summary['total_bugs']}")
    print(f"  Compile success: {summary['compile_success_total']} ({summary['compile_success_avg']}%)")
    print(f"  Repair success: {summary['repair_success_total']} ({summary['repair_success_avg']}%)")
    print(f"  Regression reduction (valid count: {summary['regression_reduction_count']}): {summary['regression_reduction_total']} (avg: {summary['regression_reduction_avg']})")


if __name__ == "__main__":
    main()
