#!/usr/bin/env python3
import csv
import os
import glob

# Read the CSV file
csv_path = '/Users/danielding/Desktop/qwen_logs/token_and_duration_qwen.csv'
logs_dir = '/Users/danielding/Desktop/qwen_logs/collected-qwen-code-logs'

# Read all data
rows = []
with open(csv_path, 'r') as f:
    reader = csv.DictReader(f)
    for row in reader:
        rows.append(row)

# Process each row
for row in rows:
    bug_id = row['bug_id']
    output_token = int(row['total_output_token'])

    # Check if output token is low (< 1000)
    is_low_token = output_token < 1000

    # Check diff_patch file (convert bug_id dashes to underscores for directory names)
    bug_dir = bug_id.replace('-', '_')
    bug_path = os.path.join(logs_dir, bug_dir)
    has_no_modifications = False

    # Look for patch-*.diff files
    if os.path.exists(bug_path):
        patch_files = glob.glob(os.path.join(bug_path, 'patch-*.diff'))

        if patch_files:
            # Read the first patch file found
            try:
                with open(patch_files[0], 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read().strip()
                    # Check if patch shows no modifications
                    if not content or len(content) < 10:  # Very minimal diff
                        has_no_modifications = True
                    # Check for "no tracked changes" message
                    elif 'no tracked changes' in content.lower() or 'no changes' in content.lower():
                        has_no_modifications = True
            except Exception as e:
                # If we can't read the file, assume there are modifications
                has_no_modifications = False
        else:
            # If no patch file exists, consider it as no modifications
            has_no_modifications = True
    else:
        # If directory doesn't exist, consider it as no modifications
        has_no_modifications = True

    # Set unread_instruction flag
    # 1 if low token AND no files modified, 0 otherwise
    if is_low_token and has_no_modifications:
        row['unread_instruction'] = '1'
    else:
        row['unread_instruction'] = '0'

    # Print for debugging
    if row['unread_instruction'] == '1':
        print(f"{bug_id}: low_token={is_low_token}, no_mods={has_no_modifications} -> UNREAD")

# Write updated CSV
output_path = '/Users/danielding/Desktop/qwen_logs/token_and_duration_qwen_updated.csv'
fieldnames = ['bug_id', 'total_input_token', 'total_output_token', 'time_duration', 'unread_instruction']

with open(output_path, 'w', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)

print(f"\nUpdated CSV written to: {output_path}")
print(f"Total bugs analyzed: {len(rows)}")
print(f"Unread instruction cases: {sum(1 for r in rows if r['unread_instruction'] == '1')}")
