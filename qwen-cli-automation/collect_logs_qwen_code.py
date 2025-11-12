#!/usr/bin/env python3

from pathlib import Path
import shutil
import sys

workspace = Path("workspace")
output = Path("collected-qwen-code-logs")

if not workspace.exists():
    print(f"Error: {workspace}/ not found")
    sys.exit(1)

output.mkdir(exist_ok=True)
collected = no_logs = errors = files_copied = 0
missing_files = []

for bug_dir in sorted(workspace.iterdir()):
    if not bug_dir.is_dir():
        continue

    logs_dir = bug_dir / "logs"
    if not logs_dir.exists():
        no_logs += 1
        continue

    try:
        # Check required files
        has_qwen = bool(list(logs_dir.glob("qwen-*.json")))
        has_run = bool(list(logs_dir.glob("run-*.log")))
        has_patch = bool(list(logs_dir.glob("patch-*.diff")))

        missing = []
        if not has_qwen:
            missing.append("qwen-*.json")
        if not has_run:
            missing.append("run-*.log")
        if not has_patch:
            missing.append("patch-*.diff")

        if missing:
            missing_files.append((bug_dir.name, missing))

        # Copy files
        bug_output = output / bug_dir.name
        bug_output.mkdir(exist_ok=True)

        bug_files = 0
        for log_file in logs_dir.iterdir():
            if log_file.is_file():
                shutil.copy2(log_file, bug_output / log_file.name)
                bug_files += 1

        files_copied += bug_files
        collected += 1
    except Exception as e:
        print(f"Error {bug_dir.name}: {e}")
        errors += 1

print(f"Bugs collected: {collected}, Files copied: {files_copied}")
print(f"No logs: {no_logs}, Errors: {errors}")

if missing_files:
    print(f"\nBugs with missing files: {len(missing_files)}")
    for bug, missing in missing_files:
        print(f"  {bug}: {', '.join(missing)}")

print(f"\nOutput: {output}/")
