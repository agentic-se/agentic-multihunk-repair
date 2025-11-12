#!/usr/bin/env python3
"""
Collect all Claude logs from bug directories into a central location.
"""

import json
import shutil
import subprocess
import os
from pathlib import Path
from datetime import datetime
from typing import Optional

def ts() -> str:
    return datetime.now().strftime("%Y-%m-%d-%H%M%S")

def ensure_dir(p: Path) -> Path:
    p.mkdir(parents=True, exist_ok=True)
    return p

def run_cmd_stream(cmd, cwd: Optional[Path] = None, timeout: Optional[int] = None) -> tuple[int, str]:
    """Run command and return (exit_code, output)."""
    try:
        result = subprocess.run(
            cmd,
            cwd=str(cwd) if cwd else None,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=timeout
        )
        return result.returncode, result.stdout
    except subprocess.TimeoutExpired:
        return 124, ""
    except Exception:
        return -1, ""

def save_patch(bug_dir: Path, logs_dir: Path, base_rev: Optional[str]) -> Path:
    ensure_dir(logs_dir)
    patch_path = logs_dir / f"patch-{ts()}.diff"

    # Only include these directories
    included_paths = ["src", "source"]

    diff_target = base_rev if base_rev else "HEAD"

    # Diff tracked file changes in included paths
    code1, diff1 = run_cmd_stream(
        ["git", "diff", "--no-ext-diff", "--binary", diff_target, "--"] + included_paths,
        cwd=bug_dir, timeout=120
    )

    # Diff staged changes in included paths
    code2, diff2 = run_cmd_stream(
        ["git", "diff", "--no-ext-diff", "--binary", "--staged", "--"] + included_paths,
        cwd=bug_dir, timeout=120
    )

    # Untracked files in included paths
    code3, untracked = run_cmd_stream(
        ["git", "ls-files", "--others", "--exclude-standard", "--"] + included_paths,
        cwd=bug_dir, timeout=60
    )

    content_parts = []
    if diff2.strip():
        content_parts.append(diff2)
    if diff1.strip():
        content_parts.append(diff1)

    if not content_parts:
        content_parts.append("# No tracked changes detected in src/ or source/\n")

    if untracked.strip():
        content_parts.append("\n# Untracked source files (not included in patch):")
        for line in untracked.strip().splitlines():
            content_parts.append(f"+ {line}")

    patch_path.write_text("\n".join(content_parts), encoding="utf-8")
    return patch_path

def collect_logs():
    """Collect all Claude JSON logs from bug directories."""

    # Setup
    prompts_dir = Path("prompts")
    output_dir = Path("collected-claude-logs")
    session_logs_dir = Path("claude_code_session_logs")
    output_dir.mkdir(exist_ok=True)

    # Find all bug directories
    bug_dirs = sorted(prompts_dir.glob("*_buggy"))

    print(f"Found {len(bug_dirs)} bug directories")

    collected = []
    missing = []

    # Collect logs from each bug directory
    for bug_dir in bug_dirs:
        bug_name = bug_dir.name.replace("_buggy", "")
        claude_logs_dir = bug_dir / "claude-logs"

        # Check claude-logs exists
        if not claude_logs_dir.exists():
            raise RuntimeError(f"ERROR: claude-logs directory not found for {bug_name} at {claude_logs_dir}")

        # Find JSON files in claude-logs
        json_files = list(claude_logs_dir.glob("*.json"))
        if not json_files:
            raise RuntimeError(f"ERROR: No JSON files found in {claude_logs_dir} for {bug_name}")

        # Create bug subdirectory
        bug_output_dir = output_dir / bug_name
        bug_output_dir.mkdir(exist_ok=True)

        # Copy JSON log
        source_file = json_files[0]
        dest_file = bug_output_dir / source_file.name
        shutil.copy2(source_file, dest_file)

        # Generate patch
        patch_file = save_patch(bug_dir, bug_output_dir, None)

        # Copy session log from claude_code_session_logs
        session_log_dir_name = str(bug_dir.absolute()).replace("/", "-").replace("_", "-")
        session_dir = session_logs_dir / session_log_dir_name

        if not session_dir.exists():
            raise RuntimeError(f"ERROR: Session log directory not found for {bug_name}: {session_dir}")

        jsonl_files = list(session_dir.glob("*.jsonl"))
        if not jsonl_files:
            raise RuntimeError(f"ERROR: No JSONL files found in {session_dir} for {bug_name}")

        session_source = jsonl_files[0]
        session_dest = bug_output_dir / session_source.name
        shutil.copy2(session_source, session_dest)

        collected.append({
            "bug": bug_name,
            "log": str(source_file),
            "log_size_kb": source_file.stat().st_size / 1024,
            "patch": str(patch_file),
            "patch_size_kb": patch_file.stat().st_size / 1024 if patch_file.exists() else 0,
            "session_log": str(session_source)
        })

        print(f"✓ {bug_name}")

    # Create summary
    summary = {
        "collection_date": datetime.now().isoformat(),
        "total_bugs": len(bug_dirs),
        "logs_collected": len(collected),
        "logs_missing": len(missing),
        "collected": collected,
        "missing": missing
    }

    summary_file = output_dir / "collection_summary.json"
    summary_file.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    # Print summary
    print(f"\n{'='*50}")
    print(f"Collection complete!")
    print(f"Total bugs: {len(bug_dirs)}")
    print(f"Logs collected: {len(collected)}")
    print(f"Logs missing: {len(missing)}")
    print(f"Output directory: {output_dir}")
    print(f"Summary: {summary_file}")

    if missing:
        print(f"\nMissing logs for: {', '.join(missing[:10])}")
        if len(missing) > 10:
            print(f"... and {len(missing) - 10} more")

    return summary

if __name__ == "__main__":
    collect_logs()
