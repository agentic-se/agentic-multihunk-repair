#!/usr/bin/env python3
import csv
import sys
from collections import defaultdict
from pathlib import Path

# Delegate categorization to the shared SWE-bench module
# (hunk-swe/scripts/agent_command_categorization/categorizer.py).
# We insert the sibling scripts/ directory on sys.path so the import
# resolves regardless of the CWD the script is invoked from. The
# `# noqa: E402` silences flake8's "module-level import not at top of
# file" warning, which fires because this import sits *after* the
# sys.path.insert above; that's intentional and the standard pattern.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agent_command_categorization import categorize_command

# Read the detailed CSV to get Bash command breakdown
bug_command_counts = defaultdict(lambda: {
    'Bash_test': 0,
    'Bash_python_exec': 0,
    'Bash_git_all': 0,
    'Bash_package_install': 0,
    'Bash_file_operations': 0,
    'Bash_text_search': 0,
    'Bash_other': 0
})

print("Reading tools_count_claude.csv to analyze Bash commands...")
with open('results/tools_count_claude.csv', 'r') as f:
    csv_reader = csv.DictReader(f)
    for row in csv_reader:
        if row['tool_name'] == 'Bash':
            bug = row['bug']
            command = row['command'].strip()
            count = int(row['count'])

            # Categorize the command
            category = categorize_command(command)
            bug_command_counts[bug][f'Bash_{category}'] += count

print(f"Analyzed commands for {len(bug_command_counts)} bugs")

# Read the existing aggregated CSV
print("Reading tools_count_all_claude.csv...")
with open('results/tools_count_all_claude.csv', 'r') as f:
    csv_reader = csv.DictReader(f)
    rows = list(csv_reader)
    fieldnames = list(csv_reader.fieldnames)

print(f"Found {len(rows)} bugs in the aggregated CSV")

# Stale columns from earlier (Defects4J) runs that should be stripped if
# present so a re-run on a previously-aggregated CSV is idempotent. NONE
# of these are written by this script -- they're only listed here so we
# can drop them from `fieldnames` before adding the new SWE-bench buckets
# (see `new_columns` below).
old_columns = [
    'Bash_find',
    'Bash_grep',
    'Bash_defects4j_compile',
    'Bash_defects4j_test',
    'Bash_defects4j_other',
    'Bash_build_and_execution',
    'Bash_bug_exposing_test',
    # Prior SWE-bench split-test buckets, replaced by single `Bash_test`.
    'Bash_pytest_test',
    'Bash_test_scripts',
]

fieldnames = [f for f in fieldnames if f not in old_columns]

# Add new columns after Bash
new_columns = [
    'Bash_test',
    'Bash_python_exec',
    'Bash_git_all',
    'Bash_package_install',
    'Bash_file_operations',
    'Bash_text_search',
    'Bash_other'
]

# Insert new columns after Bash
try:
    bash_index = fieldnames.index('Bash')
    for i, col in enumerate(new_columns):
        fieldnames.insert(bash_index + 1 + i, col)
except ValueError:
    # If Bash not found, just append
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
with open('results/tools_count_all_claude.csv', 'w', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)

print(f"Successfully updated tools_count_all_claude.csv with {len(new_columns)} columns")

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
    print(f"{col.replace('Bash_', '')}: {total}")

print("\n" + "="*80)
print("SAMPLE DATA (first 5 bugs with Bash commands)")
print("="*80)
count = 0
for bug, counts in sorted(bug_command_counts.items()):
    if any(counts.values()):
        print(f"\n{bug}:")
        for key, val in counts.items():
            if val > 0:
                print(f"  {key.replace('Bash_', '')}: {val}")
        count += 1
        if count >= 5:
            break
