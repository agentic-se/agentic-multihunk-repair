#!/usr/bin/env python3
"""
Script to analyze Gemini CLI log files and extract token usage and timing information.
"""

import json
import os
import csv
from pathlib import Path
from typing import Dict, List


def parse_log_file(log_file_path: str) -> Dict[str, any]:
    """
    Parse a single log file and extract token counts and duration.

    Args:
        log_file_path: Path to the log file

    Returns:
        Dictionary with bug_id, total_input_token, total_output_token, time_duration
    """
    # Extract bug ID from filename (e.g., "Chart-2_logs.json" -> "Chart-2")
    filename = os.path.basename(log_file_path)
    bug_id = filename.replace('_logs.json', '')

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
            except json.JSONDecodeError as e:
                # Skip unparseable objects
                continue

        # Process all JSON objects
        for log_entry in json_objects:
            # Look for API response events
            if (log_entry.get('attributes', {}).get('event.name') == 'gemini_cli.api_response'):
                attributes = log_entry.get('attributes', {})

                # Accumulate token counts
                input_tokens = attributes.get('input_token_count', 0)
                output_tokens = attributes.get('output_token_count', 0)
                duration = attributes.get('duration_ms', 0)

                total_input_tokens += input_tokens
                total_output_tokens += output_tokens
                total_duration_ms += duration

    except Exception as e:
        print(f"Error processing {log_file_path}: {e}")
        return None

    return {
        'bug_id': bug_id,
        'total_input_token': total_input_tokens,
        'total_output_token': total_output_tokens,
        'time_duration': total_duration_ms
    }


def process_all_logs(logs_dir: str, output_csv: str):
    """
    Process all log files in the directory and write results to CSV.

    Args:
        logs_dir: Directory containing the log files
        output_csv: Path to output CSV file
    """
    logs_path = Path(logs_dir)

    # Find all JSON log files
    log_files = list(logs_path.glob('*_logs.json'))

    if not log_files:
        print(f"No log files found in {logs_dir}")
        return

    print(f"Found {len(log_files)} log files to process")

    # Process each log file
    results = []
    for log_file in sorted(log_files):
        print(f"Processing {log_file.name}...")
        result = parse_log_file(str(log_file))
        if result:
            results.append(result)

    # Write results to CSV
    if results:
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
        total_time = sum(r['time_duration'] for r in results)

        print(f"\nSummary Statistics:")
        print(f"  Total input tokens: {total_input:,}")
        print(f"  Total output tokens: {total_output:,}")
        print(f"  Total time (ms): {total_time:,}")
        print(f"  Total time (minutes): {total_time / 60000:.2f}")
    else:
        print("No valid results to write")


if __name__ == '__main__':
    # Configuration
    logs_directory = '372_bugs'
    output_file = 'token_and_duration_gemini.csv'

    # Run the analysis
    process_all_logs(logs_directory, output_file)
