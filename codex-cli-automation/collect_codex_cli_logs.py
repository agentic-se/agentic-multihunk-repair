#!/usr/bin/env python3
"""
Collect all logs from workspace bug directories into a single folder.
Validates that each bug has all three expected log files.
"""

import shutil
from pathlib import Path


def main():
    workspace = Path("workspace")
    output_dir = Path("collected-codex-cli-logs")

    if not workspace.exists():
        print(f"Error: {workspace} not found")
        return

    output_dir.mkdir(exist_ok=True)
    print(f"Collecting logs to: {output_dir}/")
    print()

    collected = 0
    skipped = 0
    incomplete = []

    for bug_dir in sorted(workspace.iterdir()):
        if not bug_dir.is_dir():
            continue

        logs_dir = bug_dir / "logs"

        if not logs_dir.exists() or not logs_dir.is_dir():
            skipped += 1
            continue

        log_files = list(logs_dir.glob("*"))

        if not log_files:
            skipped += 1
            continue

        # Check for the three expected log files
        has_session = bool(list(logs_dir.glob("codex-session-rollout-*.jsonl")))
        has_run = bool(list(logs_dir.glob("run-*.log")))
        has_patch = bool(list(logs_dir.glob("patch-*.diff")))

        missing = []
        if not has_session:
            missing.append("codex-session-rollout-*.jsonl")
        if not has_run:
            missing.append("run-*.log")
        if not has_patch:
            missing.append("patch-*.diff")

        dest_dir = output_dir / bug_dir.name

        if dest_dir.exists():
            shutil.rmtree(dest_dir)

        shutil.copytree(logs_dir, dest_dir)

        file_count = len(list(dest_dir.glob("*")))

        if missing:
            print(f"⚠ {bug_dir.name}: {file_count} file(s) - MISSING: {', '.join(missing)}")
            incomplete.append((bug_dir.name, missing))
        else:
            print(f"✓ {bug_dir.name}: {file_count} file(s)")

        collected += 1

    print()
    print(f"Summary:")
    print(f"  Collected: {collected} bug(s)")
    print(f"  Complete: {collected - len(incomplete)} bug(s)")
    print(f"  Incomplete: {len(incomplete)} bug(s)")
    print(f"  Skipped: {skipped} bug(s) (no logs)")
    print(f"  Output: {output_dir.absolute()}/")

    if incomplete:
        print()
        print("Bugs with missing logs:")
        for bug_name, missing in incomplete:
            print(f"  - {bug_name}: missing {', '.join(missing)}")


if __name__ == "__main__":
    main()
