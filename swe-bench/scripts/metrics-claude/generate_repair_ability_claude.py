#!/usr/bin/env python3
import csv
import json
from pathlib import Path

# Configuration
CONFIG_JSON = Path.home() / 'Desktop' / 'birch' / 'oak' / 'config' / 'method_multihunk.json'
RESULTS_CSV = Path.home() / 'Desktop' / 'birch' / 'oak' / 'results' / 'claude_code_results' / 'results-with-failing-test-case-names-hunk4j-claude-code.csv'
OUTPUT_CSV = Path('results/claude_results/claude_repair_ability.csv')

def main():
    # Read the JSON file to get triggered_tests count
    print(f"Reading config from {CONFIG_JSON}...")
    if not CONFIG_JSON.exists():
        print(f"ERROR: {CONFIG_JSON} not found")
        return

    with CONFIG_JSON.open('r') as f:
        json_data = json.load(f)

    # Read the CSV file
    print(f"Reading results from {RESULTS_CSV}...")
    if not RESULTS_CSV.exists():
        print(f"ERROR: {RESULTS_CSV} not found")
        return

    with RESULTS_CSV.open('r') as f:
        csv_reader = csv.DictReader(f)
        csv_data = list(csv_reader)

    # Prepare output data
    output_data = []

    for row in csv_data:
        bug_id_raw = row.get('bug', row.get('bug_id', '')).strip()
        # Convert chart-14 to Chart_14 or Chart-14 to Chart_14
        bug_id = bug_id_raw.replace('-', '_')

        # Get repair: 1 if tests_pass is Yes, else 0
        tests_pass_val = row.get('tests_pass', '').strip()
        repair = 1 if tests_pass_val.lower() in ('yes', 'true', 'pass', 'passed', '1') else 0

        # Get failed_test_prior from JSON (number of triggered_tests)
        if bug_id in json_data:
            triggered_tests = json_data[bug_id].get('triggered_tests', {})
            failed_test_prior = len(triggered_tests)
        else:
            failed_test_prior = 0

        # Get failed_test_after from failed_tests_count column
        failed_tests_count = row.get('failed_tests_count', '0').strip()
        try:
            failed_test_after = int(failed_tests_count) if failed_tests_count else 0
        except ValueError:
            failed_test_after = 0

        # Get compile_fail: 1 if compiled is No, else 0 (inverted from compiled column)
        compiled_val = row.get('compiled', '').strip()
        compile_fail = 1 if compiled_val.lower() in ('no', 'false', '0') else 0

        # Calculate regression_reduction
        if compile_fail:
            regression_reduction = "undefined"
        else:
            regression_reduction = failed_test_prior - failed_test_after

        output_data.append({
            'bug_id': bug_id,
            'repair': repair,
            'failed_test_prior': failed_test_prior,
            'failed_test_after': failed_test_after,
            'regression_reduction': regression_reduction,
            'compile_fail': compile_fail
        })

    # Write output CSV
    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_CSV.open('w', newline='') as f:
        fieldnames = ['bug_id', 'repair', 'failed_test_prior', 'failed_test_after', 'regression_reduction', 'compile_fail']
        writer = csv.DictWriter(f, fieldnames=fieldnames)

        writer.writeheader()
        writer.writerows(output_data)

    print(f"Successfully created {OUTPUT_CSV} with {len(output_data)} entries")

    # Print summary statistics
    total_repairs = sum(row['repair'] for row in output_data)
    total_compile_fails = sum(row['compile_fail'] for row in output_data)
    avg_delta = sum(row['regression_reduction'] for row in output_data) / len(output_data) if output_data else 0

    print(f"\nSummary:")
    print(f"  Total bugs: {len(output_data)}")
    print(f"  Repairs: {total_repairs} ({total_repairs/len(output_data)*100:.1f}%)")
    print(f"  Compile failures: {total_compile_fails} ({total_compile_fails/len(output_data)*100:.1f}%)")
    print(f"  Average failure delta: {avg_delta:.2f}")

if __name__ == "__main__":
    main()
