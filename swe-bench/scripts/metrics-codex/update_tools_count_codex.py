#!/usr/bin/env python3
import csv
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agent_command_categorization import categorize_command

# Read the detailed CSV to get shell command breakdown
bug_command_counts = defaultdict(lambda: {
    'run_shell_command_test': 0,
    'run_shell_command_python_exec': 0,
    'run_shell_command_git_all': 0,
    'run_shell_command_package_install': 0,
    'run_shell_command_file_operations': 0,
    'run_shell_command_text_search': 0,
    'run_shell_command_other': 0
})

print("Reading tools_count_codex.csv to analyze shell commands...")
with open('results-codex/tools_count_codex.csv', 'r') as f:
    csv_reader = csv.DictReader(f)
    for row in csv_reader:
        if row['function_name'] == 'run_shell_command':
            bug = row['bug']
            command = row['command'].strip()
            count = int(row['count'])

            # Categorize the command
            category = categorize_command(command)
            bug_command_counts[bug][f'run_shell_command_{category}'] += count

print(f"Analyzed commands for {len(bug_command_counts)} bugs")

# Read the existing aggregated CSV
print("Reading tools_count_all_codex.csv...")
with open('results-codex/tools_count_all_codex.csv', 'r') as f:
    csv_reader = csv.DictReader(f)
    rows = list(csv_reader)
    fieldnames = list(csv_reader.fieldnames)

print(f"Found {len(rows)} bugs in the aggregated CSV")

# Stale columns from earlier (Defects4J / pre-Option-B SWE-bench) runs that
# should be stripped if present so a re-run on a previously-aggregated CSV
# is idempotent.
old_columns = [
    'run_shell_command_find',
    'run_shell_command_grep',
    'run_shell_command_defects4j_compile',
    'run_shell_command_defects4j_test',
    'run_shell_command_defects4j_other',
    'run_shell_command_build_and_execution',
    'run_shell_command_bug_exposing_test',
    # Prior SWE-bench split-test buckets, replaced by single `..._test`.
    'run_shell_command_pytest_test',
    'run_shell_command_test_scripts',
]

fieldnames = [f for f in fieldnames if f not in old_columns]

# Add new columns after run_shell_command
new_columns = [
    'run_shell_command_test',
    'run_shell_command_python_exec',
    'run_shell_command_git_all',
    'run_shell_command_package_install',
    'run_shell_command_file_operations',
    'run_shell_command_text_search',
    'run_shell_command_other'
]

# Insert new columns after run_shell_command
try:
    rsc_index = fieldnames.index('run_shell_command')
    for i, col in enumerate(new_columns):
        fieldnames.insert(rsc_index + 1 + i, col)
except ValueError:
    # If run_shell_command not found, just append
    fieldnames.extend(new_columns)

# Update rows with new data
for row in rows:
    bug = row['bug']

    # Remove old columns
    for old_col in old_columns:
        row.pop(old_col, None)

    # Add new columns
    if bug in bug_command_counts:
        for col in new_columns:
            row[col] = bug_command_counts[bug][col]
    else:
        for col in new_columns:
            row[col] = 0

# Write updated CSV
print("Writing updated CSV...")
with open('results-codex/tools_count_all_codex.csv', 'w', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)

print(f"Successfully updated tools_count_all_codex.csv with {len(new_columns)} columns")

# Print summary statistics
print("\n" + "="*80)
print("SUMMARY STATISTICS")
print("="*80)

total_counts = defaultdict(int)
for bug_counts in bug_command_counts.values():
    for col, count in bug_counts.items():
        total_counts[col] += count

for col in new_columns:
    total = total_counts[col]
    print(f"{col.replace('run_shell_command_', '')}: {total}")

print("\n" + "="*80)
print("SAMPLE DATA (first 5 bugs with shell commands)")
print("="*80)
count = 0
for bug, counts in sorted(bug_command_counts.items()):
    if any(counts.values()):
        print(f"\n{bug}:")
        for key, val in counts.items():
            if val > 0:
                print(f"  {key.replace('run_shell_command_', '')}: {val}")
        count += 1
        if count >= 5:
            break
