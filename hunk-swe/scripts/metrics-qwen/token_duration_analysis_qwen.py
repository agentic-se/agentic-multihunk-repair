#!/usr/bin/env python3
"""
Script to analyze Qwen CLI log files and extract token usage and timing information.
For the first 52 bugs, extracts duration from log files.
For remaining bugs, uses existing duration from CSV file.
"""

import json
import os
import csv
from pathlib import Path
from typing import Dict, List, Optional


def parse_log_file(log_dir: str) -> Optional[Dict[str, any]]:
    """
    Parse a single log directory and extract token counts and duration.

    Args:
        log_dir: Path to the log directory containing qwen-*.json file

    Returns:
        Dictionary with bug_id, total_input_token, total_output_token, time_duration (in seconds)
        Returns None if log file not found or error occurs
    """
    # Extract bug ID from directory name (e.g., "Chart_2" -> "Chart-2")
    dir_name = os.path.basename(log_dir)
    bug_id = dir_name.replace('_', '-')

    # Find the qwen-*.json log file in the directory
    log_dir_path = Path(log_dir)
    log_files = list(log_dir_path.glob('qwen-*.json'))

    if not log_files:
        print(f"  Warning: No qwen-*.json file found in {log_dir}")
        return None

    log_file_path = log_files[0]  # Use the first matching file

    total_input_tokens = 0
    total_output_tokens = 0
    total_duration_ms = 0

    try:
        with open(log_file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # The file contains multiple JSON objects separated by '}\n{'
        # Split and reconstruct each object
        json_objects = []
        parts = content.split('}\n{')

        for i, part in enumerate(parts):
            if i == 0:
                # First object - add closing brace
                json_str = part + '}'
            elif i == len(parts) - 1:
                # Last object - add opening brace
                json_str = '{' + part
            else:
                # Middle objects - add both braces
                json_str = '{' + part + '}'

            try:
                log_entry = json.loads(json_str)
                json_objects.append(log_entry)
            except json.JSONDecodeError:
                # Skip unparseable objects
                continue

        # Process all JSON objects
        for log_entry in json_objects:
            # Look for API response events
            attributes = log_entry.get('attributes', {})
            if attributes.get('event.name') == 'qwen-code.api_response':
                # Accumulate token counts
                input_tokens = attributes.get('input_token_count', 0)
                output_tokens = attributes.get('output_token_count', 0)
                duration = attributes.get('duration_ms', 0)

                total_input_tokens += input_tokens
                total_output_tokens += output_tokens
                total_duration_ms += duration

    except Exception as e:
        print(f"  Error processing {log_file_path}: {e}")
        return None

    # Convert duration from milliseconds to seconds
    time_duration_seconds = total_duration_ms / 1000.0

    return {
        'bug_id': bug_id,
        'total_input_token': total_input_tokens,
        'total_output_token': total_output_tokens,
        'time_duration': round(time_duration_seconds, 2)
    }


def load_existing_durations(csv_path: str) -> Dict[str, float]:
    """
    Load existing CSV file and extract duration data.

    Args:
        csv_path: Path to the existing CSV file

    Returns:
        Dictionary mapping bug_id to duration (in seconds)
    """
    durations = {}
    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                bug_id = row['bug']
                duration = row.get('duration', 'N/A')
                if duration != 'N/A':
                    try:
                        durations[bug_id] = float(duration)
                    except ValueError:
                        durations[bug_id] = 'N/A'
                else:
                    durations[bug_id] = 'N/A'
    except Exception as e:
        print(f"Error loading CSV: {e}")
        return {}

    return durations


def process_all_logs(logs_dir: str, existing_csv: str, output_csv: str):
    """
    Process log files and extract token counts and duration.
    For the first 52 bugs: extract all data from log files.
    For remaining bugs: extract tokens from logs, use duration from existing CSV.

    Args:
        logs_dir: Directory containing the log subdirectories
        existing_csv: Path to existing CSV with duration data for bugs 53+
        output_csv: Path to output CSV file
    """
    logs_path = Path(logs_dir)

    # Load existing duration data
    print(f"Loading existing duration data from {existing_csv}...")
    existing_durations = load_existing_durations(existing_csv)

    if not existing_durations:
        print("Failed to load existing CSV data")
        return

    print(f"Loaded duration data for {len(existing_durations)} bugs")

    # Find all log directories
    log_dirs = [d for d in logs_path.iterdir() if d.is_dir()]

    if not log_dirs:
        print(f"No log directories found in {logs_dir}")
        return

    print(f"Found {len(log_dirs)} log directories to process")

    # Process all log directories
    print(f"\nProcessing log files...")
    results = []

    for log_dir in sorted(log_dirs):
        dir_name = log_dir.name
        bug_id = dir_name.replace('_', '-')

        print(f"Processing {bug_id}...")
        result = parse_log_file(str(log_dir))

        if result:
            # For bugs 53+, use duration from existing CSV if available
            if bug_id in existing_durations and existing_durations[bug_id] != 'N/A':
                result['time_duration'] = existing_durations[bug_id]

            results.append(result)
        else:
            print(f"  Failed to extract data for {bug_id}")

    # Write results to CSV
    print(f"\nWriting results to {output_csv}...")
    with open(output_csv, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = ['bug_id', 'total_input_token', 'total_output_token', 'time_duration']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

        writer.writeheader()
        for result in results:
            writer.writerow(result)

    print(f"\nSuccessfully processed {len(results)} bugs")
    print(f"Results written to {output_csv}")

    # Print summary statistics
    total_input = sum(r['total_input_token'] for r in results)
    total_output = sum(r['total_output_token'] for r in results)

    durations_with_values = [
        r['time_duration'] for r in results
        if r['time_duration'] != 'N/A' and isinstance(r['time_duration'], (int, float))
    ]

    print(f"\nSummary Statistics:")
    print(f"  Total bugs: {len(results)}")
    print(f"  Total input tokens: {total_input:,}")
    print(f"  Total output tokens: {total_output:,}")

    if durations_with_values:
        total_time_seconds = sum(durations_with_values)
        print(f"  Bugs with duration data: {len(durations_with_values)}")
        print(f"  Total time (seconds): {total_time_seconds:,.2f}")
        print(f"  Total time (minutes): {total_time_seconds / 60:.2f}")
        print(f"  Total time (hours): {total_time_seconds / 3600:.2f}")


if __name__ == '__main__':
    # Configuration
    logs_directory = 'collected-qwen-code-logs'
    existing_csv_file = 'qwen_code_results/results-hunk4j-qwen-code.csv'
    output_file = 'token_and_duration_qwen.csv'

    # Run the analysis
    process_all_logs(logs_directory, existing_csv_file, output_file)
