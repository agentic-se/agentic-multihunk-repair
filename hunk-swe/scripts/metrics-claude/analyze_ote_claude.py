#!/usr/bin/env python3
"""
Script to analyze OTE (Over-The-Edit) metrics by comparing diff files with ground truth.

This script:
1. Reads .diff files and extracts modified files
2. Compares with ground truth buggy_files from method_multihunk.json
3. Generates a CSV with bug_id, num_expected, correct_edits, ote, and missed_edits
"""

import json
import os
import re
import csv
from pathlib import Path
from collections import defaultdict


def extract_files_from_diff(diff_path):
    """
    Extract the list of modified files from a diff file.

    Args:
        diff_path: Path to the .diff file

    Returns:
        Set of file paths that were modified
    """
    modified_files = set()

    with open(diff_path, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            # Look for lines like: --- a/path/to/file.java
            # or: +++ b/path/to/file.java
            if line.startswith('--- a/') or line.startswith('+++ b/'):
                # Extract the file path after "a/" or "b/"
                file_path = line.split('/', 1)[1].strip()
                modified_files.add(file_path)

    return modified_files


def extract_bug_id(diff_path):
    """
    Extract bug ID from the directory name.

    Args:
        diff_path: Path to the .diff file (e.g., .../chart_14/patch-*.diff)

    Returns:
        Bug ID in format like "Chart_14"
    """
    # Get the parent directory name (e.g., "chart_14")
    dir_name = Path(diff_path).parent.name

    # Convert to format like "Chart_14"
    parts = dir_name.split('_')
    if len(parts) == 2:
        project = parts[0].capitalize()
        number = parts[1]
        return f"{project}_{number}"

    return dir_name


def load_ground_truth(json_path):
    """
    Load ground truth data from method_multihunk.json.

    Args:
        json_path: Path to the ground truth JSON file

    Returns:
        Dictionary mapping bug_id to list of buggy files
    """
    with open(json_path, 'r') as f:
        data = json.load(f)

    ground_truth = {}
    for bug_id, bug_data in data.items():
        if 'buggy_files' in bug_data:
            # Extract the list of files from the buggy_files dict
            buggy_files = list(bug_data['buggy_files'].values())
            ground_truth[bug_id] = buggy_files

    return ground_truth


def analyze_edits(diff_files, ground_truth):
    """
    Analyze edits by comparing diff files with ground truth.

    Args:
        diff_files: List of paths to .diff files
        ground_truth: Dictionary mapping bug_id to list of buggy files

    Returns:
        List of result dictionaries with analysis for each bug
    """
    results = []

    for diff_path in diff_files:
        bug_id = extract_bug_id(diff_path)
        modified_files = extract_files_from_diff(diff_path)

        # Get ground truth buggy files for this bug
        expected_files = set(ground_truth.get(bug_id, []))
        num_expected = len(expected_files)

        # Calculate metrics
        correct_edits = len(modified_files & expected_files)  # Intersection
        ote = len(modified_files - expected_files)  # Modified but not in ground truth
        missed_edits = len(expected_files - modified_files)  # In ground truth but not modified

        results.append({
            'bug_id': bug_id,
            'num_expected': num_expected,
            'correct_edits': correct_edits,
            'ote': ote,
            'missed_edits': missed_edits
        })

    return results


def write_csv(results, output_path):
    """
    Write results to a CSV file.

    Args:
        results: List of result dictionaries
        output_path: Path to output CSV file
    """
    fieldnames = ['bug_id', 'num_expected', 'correct_edits', 'ote', 'missed_edits']

    with open(output_path, 'w', newline='') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)


def main():
    # Configuration
    ground_truth_path = os.path.expanduser('~/Desktop/birch/oak/config/method_multihunk.json')
    diff_base_dir = Path.cwd()  # Current directory
    output_csv = 'ote_analysis.csv'

    # Find all .diff files
    print("Searching for .diff files...")
    diff_files = list(diff_base_dir.glob('**/*.diff'))
    print(f"Found {len(diff_files)} .diff files")

    # Load ground truth
    print(f"Loading ground truth from {ground_truth_path}...")
    ground_truth = load_ground_truth(ground_truth_path)
    print(f"Loaded ground truth for {len(ground_truth)} bugs")

    # Analyze edits
    print("Analyzing edits...")
    results = analyze_edits(diff_files, ground_truth)

    # Write results
    print(f"Writing results to {output_csv}...")
    write_csv(results, output_csv)

    # Print summary statistics
    print("\n=== Summary ===")
    print(f"Total bugs analyzed: {len(results)}")

    total_expected = sum(r['num_expected'] for r in results)
    total_correct = sum(r['correct_edits'] for r in results)
    total_ote = sum(r['ote'] for r in results)
    total_missed = sum(r['missed_edits'] for r in results)

    print(f"Total expected edits: {total_expected}")
    print(f"Total correct edits: {total_correct}")
    print(f"Total OTE (over-the-edit): {total_ote}")
    print(f"Total missed edits: {total_missed}")

    if total_expected > 0:
        precision = total_correct / (total_correct + total_ote) if (total_correct + total_ote) > 0 else 0
        recall = total_correct / total_expected if total_expected > 0 else 0
        print(f"\nPrecision: {precision:.2%}")
        print(f"Recall: {recall:.2%}")

    print(f"\nResults saved to {output_csv}")


if __name__ == '__main__':
    main()
