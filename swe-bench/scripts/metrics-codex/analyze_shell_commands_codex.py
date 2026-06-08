#!/usr/bin/env python3
import csv
import re
import sys
from collections import defaultdict, Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agent_command_categorization import categorize_command

# Read all shell commands
commands = []
print("Reading shell commands from tools_count_codex.csv...")
with open('results-codex/tools_count_codex.csv', 'r') as f:
    csv_reader = csv.DictReader(f)
    for row in csv_reader:
        if row['function_name'] == 'run_shell_command':
            command = row['command'].strip()
            count = int(row['count'])
            commands.extend([command] * count)

print(f"\nTotal shell command invocations: {len(commands)}")
print(f"Unique shell commands: {len(set(commands))}")

# Count by command
command_counts = Counter(commands)

# Function to extract command base
def get_command_base(cmd):
    """Extract the main command/tool being used"""
    cmd = cmd.strip()
    # Get first token
    first_token = cmd.split()[0] if cmd.split() else cmd
    return first_token

# ``categorize_command`` is imported from agent_command_categorization above.

# Categorize all commands
category_counts = Counter()
category_examples = defaultdict(list)

for cmd, count in command_counts.items():
    category = categorize_command(cmd)
    category_counts[category] += count
    if len(category_examples[category]) < 3:
        category_examples[category].append(cmd)

# Print analysis
print("\n" + "="*80)
print("COMMAND CATEGORY ANALYSIS")
print("="*80)

for category, count in category_counts.most_common():
    percentage = (count / len(commands)) * 100
    print(f"\n{category}: {count} ({percentage:.1f}%)")
    print("  Examples:")
    for example in category_examples[category]:
        print(f"    - {example}")

# Print top individual commands
print("\n" + "="*80)
print("TOP 20 INDIVIDUAL COMMANDS")
print("="*80)
for cmd, count in command_counts.most_common(20):
    percentage = (count / len(commands)) * 100
    print(f"{count:4d} ({percentage:5.1f}%) - {cmd}")

# Analyze command bases
print("\n" + "="*80)
print("COMMAND BASES (First token)")
print("="*80)
base_counts = Counter([get_command_base(cmd) for cmd in commands])
for base, count in base_counts.most_common(15):
    percentage = (count / len(commands)) * 100
    print(f"{count:4d} ({percentage:5.1f}%) - {base}")

# Proposed groupings
print("\n" + "="*80)
print("PROPOSED COLUMN GROUPINGS")
print("="*80)
print("""
Based on the analysis, here are proposed grouping strategies:

OPTION 1 - Detailed (10-12 columns):
  1. defects4j_compile
  2. defects4j_test
  3. defects4j_export
  4. test_scripts (run_bug_exposing_tests.sh, run_all_tests_trace.sh)
  5. git_diff
  6. git_inspection (status, log, show)
  7. git_modification (checkout, restore, reset, add)
  8. build_tools (mvn, gradle, ant)
  9. java_execution
  10. file_operations (rm, mkdir, ls, cp, mv)
  11. search (find, grep)
  12. other

OPTION 2 - Moderate (7-8 columns):
  1. defects4j_compile
  2. defects4j_test
  3. defects4j_other (export, etc.)
  4. test_scripts
  5. git_all (all git commands)
  6. build_and_execution (mvn, gradle, java -cp)
  7. file_operations
  8. other

OPTION 3 - High-level (5-6 columns):
  1. compilation (defects4j compile, build tools)
  2. testing (defects4j test, test scripts)
  3. version_control (all git commands)
  4. environment_setup (defects4j export, file operations)
  5. direct_execution (java -cp)
  6. other

RECOMMENDATION: Option 2 provides a good balance between detail and manageability.
""")
