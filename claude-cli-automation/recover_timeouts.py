#!/usr/bin/env python3
"""
Recovery script for timed-out bug processing
Runs defects4j compile and test to get actual results
"""

import csv
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

def run_defects4j_tests(bug_dir):
    """Run defects4j compile and test, return (compiled, tests_pass, failed_count)."""
    # Compile
    result = subprocess.run(
        ["defects4j", "compile"],
        cwd=bug_dir,
        capture_output=True,
        timeout=600
    )
    if result.returncode != 0:
        return False, False, 0

    # Test
    result = subprocess.run(
        ["defects4j", "test"],
        cwd=bug_dir,
        capture_output=True,
        text=True,
        timeout=1800
    )

    failed_tests = [line.strip()[2:] for line in result.stdout.splitlines() if line.strip().startswith("- ")]
    tests_pass = result.returncode == 0 and len(failed_tests) == 0

    return True, tests_pass, len(failed_tests)

def main():
    results_csv = Path("./results.csv").resolve()
    results_dir = results_csv.parent
    prompts_dir = Path("./prompts").resolve()

    # Find orphaned status files
    status_files = list(results_dir.glob(".processing-*.json"))

    if not status_files:
        print("No orphaned status files found")
        return 0

    print(f"Found {len(status_files)} orphaned status file(s)")

    # Process each timeout
    for status_file in status_files:
        status_data = json.loads(status_file.read_text())
        project = status_data["project"]
        bug_id = status_data["bug_id"]
        start_time = datetime.fromisoformat(status_data["start_time"])
        duration = (datetime.now() - start_time).total_seconds()

        # Find bug directory
        bug_dir = prompts_dir / f"{project.lower()}_{bug_id}_buggy"

        if not bug_dir.exists():
            print(f"Bug directory not found: {bug_dir}")
            compiled, tests_pass, failed_count = False, False, 0
        else:
            print(f"Running tests for {project}-{bug_id}...")
            compiled, tests_pass, failed_count = run_defects4j_tests(bug_dir)

        # Write to CSV
        file_exists = results_csv.exists()
        with open(results_csv, 'a', newline='') as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(['bug', 'compiled', 'tests_pass', 'failed_tests_count', 'claude_exit_code', 'duration_s'])
            writer.writerow([
                f"{project}-{bug_id}",
                'Yes' if compiled else 'No',
                'Yes' if tests_pass else 'No',
                failed_count,
                'TIMEOUT',
                f"{duration:.1f}"
            ])

        print(f"Processed: {project}-{bug_id}, compiled={compiled}, tests_pass={tests_pass}")
        status_file.unlink()

    print(f"Results saved to: {results_csv}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
