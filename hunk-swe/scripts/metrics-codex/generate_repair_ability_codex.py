#!/usr/bin/env python3
import csv
import json
from pathlib import Path

# Read the JSON file to get triggered_tests count
json_path = Path.home() / 'Desktop' / 'birch' / 'oak' / 'config' / 'method_multihunk.json'
with open(json_path, 'r') as f:
    json_data = json.load(f)

# Read the CSV file
with open('results-hunk4j-codex-cli.csv', 'r') as f:
    csv_reader = csv.DictReader(f)
    csv_data = list(csv_reader)

# Prepare output data
output_data = []

for row in csv_data:
    bug_id = row['bug']  # Keep as is (Chart-14)

    # Get repair: 1 if pass is Yes, else 0
    repair = 1 if row['pass'] == 'Yes' else 0

    # Get failed_test_prior from JSON (number of triggered_tests)
    # Normalize bug_id for JSON lookup (Chart-14 -> Chart_14)
    bug_id_normalized = bug_id.replace('-', '_')
    if bug_id_normalized in json_data:
        triggered_tests = json_data[bug_id_normalized].get('triggered_tests', {})
        failed_test_prior = len(triggered_tests)
    else:
        failed_test_prior = 0

    # Get failed_test_after: count number of tests in failed_tests
    failed_tests_str = row['failed_tests'].strip()
    if failed_tests_str:
        # Count semicolon-separated tests
        failed_test_after = len([t.strip() for t in failed_tests_str.split(';') if t.strip()])
    else:
        failed_test_after = 0

    # Get compile_fail: 1 if compile_fail is Yes, else 0
    compile_fail = 1 if row['compile_fail'] == 'Yes' else 0

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
with open('results-codex/codex_repair_ability.csv', 'w', newline='') as f:
    fieldnames = ['bug_id', 'repair', 'failed_test_prior', 'failed_test_after', 'regression_reduction', 'compile_fail']
    writer = csv.DictWriter(f, fieldnames=fieldnames)

    writer.writeheader()
    writer.writerows(output_data)

print(f"Successfully created codex_repair_ability.csv with {len(output_data)} entries")
