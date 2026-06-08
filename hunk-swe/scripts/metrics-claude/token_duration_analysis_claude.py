#!/usr/bin/env python3
"""
Script to analyze Claude Code log files and extract token usage and timing information.
Duration is taken from existing CSV file.
"""

import json
import os
import csv
from pathlib import Path
from typing import Dict, List, Optional


def parse_log_file(log_dir: str) -> Optional[Dict[str, any]]:
    """
    Parse a single log directory and extract token counts.

    Args:
        log_dir: Path to the log directory containing claude-output-*.json or *.jsonl file

    Returns:
        Dictionary with bug_id, total_input_token, total_output_token
        Returns None if log file not found or error occurs
    """
    # Extract bug ID from directory name (e.g., "chart_2" -> "Chart-2")
    dir_name = os.path.basename(log_dir)
    bug_id = dir_name.replace('_', '-').title()

    log_dir_path = Path(log_dir)

    # First try to find claude-output-*.json files
    log_files = list(log_dir_path.glob('claude-output-*.json'))

    # If not found or empty, try .jsonl files
    if not log_files or (log_files and log_files[0].stat().st_size == 0):
        jsonl_files = list(log_dir_path.glob('*.jsonl'))
        if jsonl_files:
            return parse_jsonl_file(jsonl_files[0], bug_id)
        elif not log_files:
            print(f"  Warning: No log file found in {log_dir}")
            return None
        else:
            print(f"  Warning: Log file is empty in {log_dir}")
            return None

    log_file_path = log_files[0]

    total_input_tokens = 0
    total_output_tokens = 0
    total_cache_creation_tokens = 0
    total_cache_read_tokens = 0

    try:
        with open(log_file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # Process all entries in the JSON array
        for entry in data:
            # Look for assistant messages with usage information
            if entry.get('type') == 'assistant' and 'message' in entry:
                usage = entry['message'].get('usage', {})

                # Accumulate token counts
                input_tokens = usage.get('input_tokens', 0)
                output_tokens = usage.get('output_tokens', 0)
                cache_creation = usage.get('cache_creation_input_tokens', 0)
                cache_read = usage.get('cache_read_input_tokens', 0)

                total_input_tokens += input_tokens
                total_output_tokens += output_tokens
                total_cache_creation_tokens += cache_creation
                total_cache_read_tokens += cache_read

    except Exception as e:
        print(f"  Error processing {log_file_path}: {e}")
        return None

    return {
        'bug_id': bug_id,
        'total_input_token': total_input_tokens,
        'total_output_token': total_output_tokens,
        'cache_creation_tokens': total_cache_creation_tokens,
        'cache_read_tokens': total_cache_read_tokens
    }


def parse_jsonl_file(jsonl_path: Path, bug_id: str) -> Optional[Dict[str, any]]:
    """
    Parse a JSONL file and extract token counts.

    Args:
        jsonl_path: Path to the JSONL file
        bug_id: The bug ID

    Returns:
        Dictionary with bug_id, total_input_token, total_output_token
    """
    total_input_tokens = 0
    total_output_tokens = 0
    total_cache_creation_tokens = 0
    total_cache_read_tokens = 0

    try:
        with open(jsonl_path, 'r', encoding='utf-8') as f:
            for line in f:
                if not line.strip():
                    continue

                try:
                    entry = json.loads(line)

                    # Look for assistant messages with usage information
                    if entry.get('type') == 'assistant' and 'message' in entry:
                        usage = entry['message'].get('usage', {})

                        # Accumulate token counts
                        input_tokens = usage.get('input_tokens', 0)
                        output_tokens = usage.get('output_tokens', 0)
                        cache_creation = usage.get('cache_creation_input_tokens', 0)
                        cache_read = usage.get('cache_read_input_tokens', 0)

                        total_input_tokens += input_tokens
                        total_output_tokens += output_tokens
                        total_cache_creation_tokens += cache_creation
                        total_cache_read_tokens += cache_read
                except json.JSONDecodeError:
                    continue

    except Exception as e:
        print(f"  Error processing {jsonl_path}: {e}")
        return None

    return {
        'bug_id': bug_id,
        'total_input_token': total_input_tokens,
        'total_output_token': total_output_tokens,
        'cache_creation_tokens': total_cache_creation_tokens,
        'cache_read_tokens': total_cache_read_tokens
    }


def load_existing_durations(csv_path: str) -> Dict[str, float]:
    """
    Load existing CSV file and extract duration data.

    Args:
        csv_path: Path to the existing CSV file

    Returns:
        Dictionary mapping bug_id (lowercase) to duration (in seconds)
    """
    durations = {}
    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                bug_id = row['bug'].lower()  # Normalize to lowercase
                # Claude CSV uses 'duration_s' field
                duration = row.get('duration_s', 'N/A')
                if duration and duration != 'N/A' and duration != '':
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
    Process log files and extract token counts.
    Duration is always taken from existing CSV.

    Args:
        logs_dir: Directory containing the log subdirectories
        existing_csv: Path to existing CSV with duration data
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
        bug_id = dir_name.replace('_', '-').title()

        print(f"Processing {bug_id}...")
        result = parse_log_file(str(log_dir))

        if result:
            # Use duration from existing CSV (case-insensitive lookup)
            bug_id_lower = bug_id.lower()
            if bug_id_lower in existing_durations:
                result['time_duration'] = existing_durations[bug_id_lower]
            else:
                result['time_duration'] = 'N/A'

            results.append(result)
        else:
            print(f"  Failed to extract data for {bug_id}")

    # Write results to CSV
    print(f"\nWriting results to {output_csv}...")
    with open(output_csv, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = ['bug_id', 'total_input_token', 'total_output_token',
                      'cache_creation_tokens', 'cache_read_tokens', 'time_duration']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

        writer.writeheader()
        for result in results:
            writer.writerow(result)

    print(f"\nSuccessfully processed {len(results)} bugs")
    print(f"Results written to {output_csv}")

    # Print summary statistics
    total_input = sum(r['total_input_token'] for r in results)
    total_output = sum(r['total_output_token'] for r in results)
    total_cache_creation = sum(r['cache_creation_tokens'] for r in results)
    total_cache_read = sum(r['cache_read_tokens'] for r in results)

    durations_with_values = [
        r['time_duration'] for r in results
        if r['time_duration'] != 'N/A' and isinstance(r['time_duration'], (int, float))
    ]

    print(f"\nSummary Statistics:")
    print(f"  Total bugs: {len(results)}")
    print(f"  Total input tokens: {total_input:,}")
    print(f"  Total output tokens: {total_output:,}")
    print(f"  Total cache creation tokens: {total_cache_creation:,}")
    print(f"  Total cache read tokens: {total_cache_read:,}")

    if durations_with_values:
        total_time_seconds = sum(durations_with_values)
        print(f"  Bugs with duration data: {len(durations_with_values)}")
        print(f"  Total time (seconds): {total_time_seconds:,.2f}")
        print(f"  Total time (minutes): {total_time_seconds / 60:.2f}")
        print(f"  Total time (hours): {total_time_seconds / 3600:.2f}")


if __name__ == '__main__':
    # Configuration
    logs_directory = 'collected-claude-logs'
    existing_csv_file = 'results-hunk4j-claude-code.csv'
    output_file = 'token_and_duration_claude.csv'

    # Run the analysis
    process_all_logs(logs_directory, existing_csv_file, output_file)
