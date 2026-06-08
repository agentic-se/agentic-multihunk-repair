#!/usr/bin/env python3
"""
SWE-bench Bug Checkout Script
Checks out the 32 multi-hunk bugs from SWE-bench Verified into ~/WORK_DIR.

For each bug:
  1. Clones the repo (or reuses existing clone)
  2. Creates a worktree at the base_commit
  3. Applies the test_patch (so failing tests are present)
  4. Writes bug metadata (problem_statement, FAIL_TO_PASS, etc.) into the workspace

Uses git worktrees to avoid cloning the same repo multiple times.
"""

import argparse
import json
import logging
import subprocess
import sys
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
log = logging.getLogger(__name__)

# Paths
SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
MULTIHUNK_JSON = REPO_ROOT / "swe_bench_verified" / "multihunk_bugs_only.json"
SWEBENCH_JSON = REPO_ROOT / "swe_bench_verified" / "swe_bench.json"

DEFAULT_WORK_DIR = Path.home() / "WORK_DIR"


def load_swebench_records(instance_ids: set) -> dict:
    """Load SWE-bench records for the given instance IDs (JSONL format)."""
    records = {}
    with open(SWEBENCH_JSON, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            if record["instance_id"] in instance_ids:
                records[record["instance_id"]] = record
    return records


def run_cmd(cmd: list[str], cwd: Path = None, check: bool = True) -> subprocess.CompletedProcess:
    """Run a shell command, logging it."""
    log.debug(f"Running: {' '.join(cmd)}")
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=check)


def clone_repo(repo: str, bare_dir: Path) -> None:
    """Clone a bare repo if it doesn't exist yet."""
    if bare_dir.exists():
        log.info(f"  Bare repo already exists: {bare_dir.name}")
        return

    url = f"https://github.com/{repo}.git"
    log.info(f"  Cloning {url} (bare) ...")
    run_cmd(["git", "clone", "--bare", url, str(bare_dir)])
    log.info(f"  Clone complete.")


def create_worktree(bare_dir: Path, workspace: Path, commit: str) -> None:
    """Create a git worktree at the given commit."""
    if workspace.exists():
        log.info(f"  Workspace already exists: {workspace.name}")
        return

    # Create a detached worktree at the specific commit
    log.info(f"  Creating worktree at {commit[:10]}...")
    run_cmd(
        ["git", "worktree", "add", "--detach", str(workspace), commit],
        cwd=bare_dir
    )


def apply_test_patch(workspace: Path, test_patch: str) -> bool:
    """Apply the test_patch so failing tests exist in the workspace."""
    if not test_patch or not test_patch.strip():
        log.warning(f"  No test_patch to apply.")
        return False

    patch_file = workspace / ".swebench_test_patch.diff"
    patch_file.write_text(test_patch, encoding="utf-8")

    result = run_cmd(
        ["git", "apply", "--check", str(patch_file)],
        cwd=workspace,
        check=False
    )
    if result.returncode != 0:
        log.warning(f"  Test patch does not apply cleanly: {result.stderr.strip()}")
        return False

    run_cmd(["git", "apply", str(patch_file)], cwd=workspace)
    log.info(f"  Test patch applied.")
    return True


def write_bug_metadata(workspace: Path, record: dict) -> None:
    """Write bug metadata files into the workspace for agent consumption."""
    meta_dir = workspace / ".swebench"
    meta_dir.mkdir(exist_ok=True)

    # Problem statement (the bug report the agent needs to read)
    (meta_dir / "problem_statement.md").write_text(
        record["problem_statement"], encoding="utf-8"
    )

    # Failing tests
    (meta_dir / "FAIL_TO_PASS.json").write_text(
        json.dumps(json.loads(record["FAIL_TO_PASS"])
                   if isinstance(record["FAIL_TO_PASS"], str)
                   else record["FAIL_TO_PASS"],
                   indent=2),
        encoding="utf-8"
    )

    # Full record (for reference)
    sanitized = {k: v for k, v in record.items() if k != "patch"}  # exclude gold patch
    (meta_dir / "instance_metadata.json").write_text(
        json.dumps(sanitized, indent=2), encoding="utf-8"
    )

    # Hints (if any)
    if record.get("hints_text"):
        (meta_dir / "hints.md").write_text(
            record["hints_text"], encoding="utf-8"
        )

    log.info(f"  Metadata written to .swebench/")


def write_summary(work_dir: Path, results: list[dict]) -> None:
    """Write a checkout summary JSON."""
    summary_path = work_dir / "checkout_summary.json"
    summary_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    log.info(f"Summary written to {summary_path}")


def checkout_bug(
    instance_id: str,
    record: dict,
    work_dir: Path,
    bare_repos_dir: Path,
    skip_test_patch: bool = False,
) -> dict:
    """Checkout a single SWE-bench bug. Returns status dict."""
    repo = record["repo"]                         # e.g. "astropy/astropy"
    base_commit = record["base_commit"]
    repo_slug = repo.replace("/", "__")            # e.g. "astropy__astropy"

    log.info(f"[{instance_id}] repo={repo} commit={base_commit[:10]}")

    result = {
        "instance_id": instance_id,
        "repo": repo,
        "base_commit": base_commit,
        "version": record.get("version", ""),
        "status": "success",
        "error": None,
    }

    try:
        # Step 1: Clone bare repo (shared across bugs from same repo)
        bare_dir = bare_repos_dir / f"{repo_slug}.git"
        clone_repo(repo, bare_dir)

        # Step 2: Fetch the specific commit (bare clone may not have it)
        fetch_result = run_cmd(
            ["git", "cat-file", "-t", base_commit],
            cwd=bare_dir, check=False
        )
        if fetch_result.returncode != 0:
            log.info(f"  Fetching commit {base_commit[:10]} from origin...")
            run_cmd(["git", "fetch", "origin", base_commit], cwd=bare_dir, check=False)

        # Step 3: Create worktree
        workspace = work_dir / instance_id
        create_worktree(bare_dir, workspace, base_commit)

        # Step 4: Apply test patch
        if not skip_test_patch:
            apply_test_patch(workspace, record.get("test_patch", ""))

        # Step 5: Write metadata
        write_bug_metadata(workspace, record)

    except Exception as e:
        log.error(f"  FAILED: {e}")
        result["status"] = "error"
        result["error"] = str(e)

    return result


def main():
    parser = argparse.ArgumentParser(
        description="Checkout SWE-bench multi-hunk bugs into workspaces."
    )
    parser.add_argument(
        "--work-dir", type=Path, default=DEFAULT_WORK_DIR,
        help=f"Root directory for bug workspaces (default: {DEFAULT_WORK_DIR})"
    )
    parser.add_argument(
        "--only", nargs="+",
        help="Only checkout specific instance IDs (e.g., django__django-10554)"
    )
    parser.add_argument(
        "--skip-test-patch", action="store_true",
        help="Don't apply the test patch (agent won't have failing tests)"
    )
    parser.add_argument(
        "--debug", action="store_true",
        help="Enable debug logging"
    )
    args = parser.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    # Load bug list
    with open(MULTIHUNK_JSON, "r") as f:
        multihunk_bugs = json.load(f)

    instance_ids = set(multihunk_bugs.keys())
    if args.only:
        instance_ids = instance_ids & set(args.only)
        if not instance_ids:
            log.error(f"None of {args.only} found in multihunk_bugs_only.json")
            sys.exit(1)

    # Load SWE-bench records
    records = load_swebench_records(instance_ids)
    missing = instance_ids - set(records.keys())
    if missing:
        log.error(f"Missing from swe_bench.json: {missing}")
        sys.exit(1)

    # Setup directories
    work_dir = args.work_dir.resolve()
    work_dir.mkdir(parents=True, exist_ok=True)
    bare_repos_dir = work_dir / ".bare_repos"
    bare_repos_dir.mkdir(parents=True, exist_ok=True)

    log.info(f"Work dir: {work_dir}")
    log.info(f"Checking out {len(instance_ids)} bugs...")
    log.info("")

    # Checkout each bug
    results = []
    for instance_id in sorted(instance_ids):
        record = records[instance_id]
        result = checkout_bug(
            instance_id, record, work_dir, bare_repos_dir,
            skip_test_patch=args.skip_test_patch,
        )
        results.append(result)
        log.info("")

    # Summary
    write_summary(work_dir, results)

    successes = sum(1 for r in results if r["status"] == "success")
    failures = sum(1 for r in results if r["status"] != "success")
    log.info(f"Done: {successes} succeeded, {failures} failed out of {len(results)} bugs.")

    if failures:
        for r in results:
            if r["status"] != "success":
                log.error(f"  FAILED: {r['instance_id']}: {r['error']}")
        sys.exit(1)


if __name__ == "__main__":
    main()
