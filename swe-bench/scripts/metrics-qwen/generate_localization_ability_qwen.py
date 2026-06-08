#!/usr/bin/env python3
import csv

# Read the repair ability CSV to get all bugs
with open('qwen_code_results/metrics/qwen_repair_ability.csv', 'r') as f:
    csv_reader = csv.DictReader(f)
    all_bugs = [row['bug_id'] for row in csv_reader]

# Read the edit accuracy summary CSV and create a lookup
edit_accuracy_lookup = {}
with open('qwen_code_results/metrics/qwen_edit_accuracy_summary.csv', 'r') as f:
    csv_reader = csv.DictReader(f)
    for row in csv_reader:
        bug_id = row['bug']
        num_expected = int(row['num_expected']) if row['num_expected'] else 0
        correct_edits = int(row['correct_edits']) if row['correct_edits'] else 0
        edit_accuracy_lookup[bug_id] = (num_expected, correct_edits)

# Prepare output data
output_data = []

for bug_id in all_bugs:
    if bug_id in edit_accuracy_lookup:
        num_expected, correct_edits = edit_accuracy_lookup[bug_id]
        # Localization is 1 when num_expected == correct_edits, regardless of other columns
        localization = 1 if num_expected == correct_edits else 0
    else:
        # Bug not in edit accuracy summary, set localization to 0
        localization = 0

    output_data.append({
        'bug_id': bug_id,
        'localization': localization
    })

# Write output CSV
with open('qwen_code_results/metrics/qwen_localization_ability.csv', 'w', newline='') as f:
    fieldnames = ['bug_id', 'localization']
    writer = csv.DictWriter(f, fieldnames=fieldnames)

    writer.writeheader()
    writer.writerows(output_data)

print(f"Successfully created qwen_localization_ability.csv with {len(output_data)} entries")

# Print some statistics
total_bugs = len(output_data)
successful_localizations = sum(1 for row in output_data if row['localization'] == 1)
print(f"Localization success rate: {successful_localizations}/{total_bugs} ({successful_localizations/total_bugs*100:.1f}%)")
