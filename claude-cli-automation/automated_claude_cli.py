#!/usr/bin/env python3
"""
Automated Claude Code CLI runner
Runs Claude in headless mode, collects JSON logs
"""

import argparse
import csv
import json
import logging
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple, List, Dict

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

def ts() -> str:
    """Timestamp for file names."""
    return datetime.now().strftime("%Y%m%d-%H%M%S")

def ensure_dir(path: Path) -> Path:
    """Ensure directory exists."""
    path.mkdir(parents=True, exist_ok=True)
    return path

def read_base_prompt_and_inject(base_prompt_path: Path, bug_title: str, bug_description: str) -> str:
    """Read base prompt template and inject bug title and description."""
    base = base_prompt_path.read_text(encoding="utf-8")
    return (base
            .replace("{{bug_title}}", bug_title or "title unavailable")
            .replace("{{bug_description}}", (bug_description or "").strip()))

def load_bug_info_from_config(project: str, bug_id: str, config_path: Path) -> Tuple[str, str]:
    """
    Load bug title and description from config/multihunk.json.
    Returns: (bug_title, bug_description)
    """
    if not config_path.exists():
        logging.warning(f"Config file not found: {config_path}")
        return "", ""

    try:
        config_data = json.loads(config_path.read_text(encoding="utf-8"))
        bug_key = f"{project}_{bug_id}"

        if bug_key not in config_data:
            logging.warning(f"Bug {bug_key} not found in config")
            return "", ""

        bug_info = config_data[bug_key]
        bug_report = bug_info.get("bug_report", {})

        title = bug_report.get("title", "")
        description = bug_report.get("bug_description", "")

        return title, description

    except Exception as e:
        logging.error(f"Error loading bug info from config: {e}")
        return "", ""

def run_claude_headless(work_dir: Path, verbose: bool = False) -> Tuple[int, Dict, float]:
    """
    Run Claude CLI in headless mode with JSON output following CLAUDE.md instructions.
    Output is redirected directly to a JSON file to ensure nothing is lost.

    Returns: (exit_code, output_data, duration_seconds)
    """
    # Create logs directory and output file
    logs_dir = ensure_dir(work_dir / "claude-logs")
    output_file = logs_dir / f"claude-output-{ts()}.json"

    cmd = [
        "claude",
        "-p", "Read and execute the instructions listed in CLAUDE.md.",
        "--output-format", "json",
        "--dangerously-skip-permissions"
    ]

    if verbose:
        cmd.append("--verbose")

    logging.info(f"Running Claude CLI...")
    logging.info(f"Working directory: {work_dir}")
    logging.info(f"Command: {' '.join(cmd)}")
    logging.info(f"Output will be saved to: {output_file}")

    start_time = time.time()
    try:
        # Redirect stdout directly to file - this ensures all output is saved
        with open(output_file, 'w', encoding='utf-8') as f:
            result = subprocess.run(
                cmd,
                cwd=str(work_dir),
                stdout=f,
                stderr=subprocess.STDOUT,
                text=True
            )
        duration = time.time() - start_time

        # Read and parse the JSON output from file
        output = {}
        if output_file.exists():
            try:
                output = json.loads(output_file.read_text(encoding='utf-8'))
            except json.JSONDecodeError as e:
                # File is already saved, just log the parsing error
                logging.error(f"Failed to parse JSON from {output_file}: {e}")
                logging.error(f"Raw output is preserved in {output_file}")
                output = {"error": f"JSON parse error: {str(e)}", "output_file": str(output_file)}

        return result.returncode, output, duration

    except Exception as e:
        duration = time.time() - start_time
        logging.error(f"Error: {e}")
        return -1, {"error": str(e)}, duration

def checkout_defects4j_bug(project: str, bug_id: str, prompts_dir: Path) -> Path:
    """
    Checkout a defects4j bug to prompts/<project>_<bug_id>_buggy/ directory.

    Returns: Path to the checked out directory
    """
    bug_dir = prompts_dir / f"{project.lower()}_{bug_id}_buggy"

    try:
        # Remove existing directory if it exists
        if bug_dir.exists():
            import shutil
            shutil.rmtree(bug_dir)

        subprocess.run(
            ["defects4j", "checkout", "-p", project, "-v", f"{bug_id}b", "-w", str(bug_dir)],
            check=True,
            capture_output=True,
            text=True
        )
        logging.info(f"Successfully checked out {project}-{bug_id} to {bug_dir}")
        return bug_dir

    except subprocess.CalledProcessError as e:
        logging.error(f"Defects4J checkout failed for {project}-{bug_id}: {e}")
        if e.stderr:
            logging.error(f"Defects4J error output: {e.stderr}")
        if e.stdout:
            logging.error(f"Defects4J stdout: {e.stdout}")
        raise RuntimeError(f"Failed to checkout {project}-{bug_id}")

def run_defects4j_tests(bug_dir: Path) -> Tuple[bool, bool, List[str]]:
    """
    Run defects4j compile and test.
    Returns: (compiled_ok, tests_pass, failed_test_list)
    """
    # Compile
    logging.info("Running defects4j compile...")
    try:
        result = subprocess.run(
            ["defects4j", "compile"],
            cwd=bug_dir,
            capture_output=True,
            text=True,
            timeout=600
        )
        if result.returncode != 0:
            logging.error(f"Compilation failed with exit code {result.returncode}")
            if result.stderr:
                logging.error(f"Compile stderr: {result.stderr}")
            if result.stdout:
                logging.error(f"Compile stdout: {result.stdout}")
            return False, False, ["COMPILE_ERROR"]
        else:
            logging.info("Compilation successful")
    except Exception as e:
        logging.error(f"Compile error: {e}")
        return False, False, ["COMPILE_ERROR"]
    
    # Test
    logging.info("Running defects4j test...")
    try:
        result = subprocess.run(
            ["defects4j", "test"],
            cwd=bug_dir,
            capture_output=True,
            text=True,
            timeout=1800
        )

        # Parse test output for failures
        failed_tests = []
        for line in result.stdout.splitlines():
            if line.strip().startswith("- "):
                failed_tests.append(line.strip()[2:])

        tests_pass = result.returncode == 0 and len(failed_tests) == 0

        if tests_pass:
            logging.info("All tests passed!")
        else:
            logging.warning(f"Tests failed. Exit code: {result.returncode}")
            if failed_tests:
                logging.warning(f"Failed tests: {', '.join(failed_tests)}")
            if result.stderr:
                logging.warning(f"Test stderr: {result.stderr}")

        return True, tests_pass, failed_tests

    except Exception as e:
        logging.error(f"Test execution error: {e}")
        return True, False, [str(e)]


def create_status_file(project: str, bug_id: str, results_dir: Path) -> Path:
    """Create status file to track in-progress bug processing."""
    status_file = results_dir / f".processing-{project}-{bug_id}.json"
    status_data = {
        "project": project,
        "bug_id": bug_id,
        "start_time": datetime.now().isoformat()
    }
    status_file.write_text(json.dumps(status_data, indent=2), encoding="utf-8")
    logging.info(f"Created status file: {status_file}")
    return status_file

def delete_status_file(project: str, bug_id: str, results_dir: Path):
    """Delete status file after successful completion."""
    status_file = results_dir / f".processing-{project}-{bug_id}.json"
    if status_file.exists():
        status_file.unlink()
        logging.info(f"Deleted status file: {status_file}")

def save_results_csv(results_file: Path, project: str, bug_id: str,
                     compiled: bool, tests_pass: bool, failed_tests: List[str],
                     claude_exit: int, duration: float):
    """Append results to CSV file."""
    file_exists = results_file.exists()

    with open(results_file, 'a', newline='') as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow([
                'bug', 'compiled', 'tests_pass', 'failed_tests_count',
                'claude_exit_code', 'duration_s'
            ])

        writer.writerow([
            f"{project}-{bug_id}",
            'Yes' if compiled else 'No',
            'Yes' if tests_pass else 'No',
            len(failed_tests),
            claude_exit,
            f"{duration:.1f}"
        ])

def process_single_bug(
    project: str,
    bug_id: str,
    prompts_dir: Path,
    results_csv: Path,
    verbose: bool = False
) -> bool:
    """Process a single bug."""
    # Create status file to track progress
    create_status_file(project, bug_id, results_csv.parent)

    # Step 1: Checkout
    logging.info(f"=== Processing {project}-{bug_id} ===")
    try:
        bug_dir = checkout_defects4j_bug(project, bug_id, prompts_dir)
    except RuntimeError:
        save_results_csv(results_csv, project, bug_id, False, False,
                        ["CHECKOUT_FAILED"], -1, 0)
        delete_status_file(project, bug_id, results_csv.parent)
        return False

    # Step 2: Load bug info and inject into prompt template
    prompt_source = prompts_dir / "prompt.md"
    claude_md = bug_dir / "CLAUDE.md"

    if prompt_source.exists():
        logging.info(f"Loading prompt template from {prompt_source}")

        # Load bug info from config
        config_path = prompts_dir.parent / "config" / "multihunk.json"
        bug_title, bug_description = load_bug_info_from_config(project, bug_id, config_path)

        # Inject bug info into template
        prompt_content = read_base_prompt_and_inject(prompt_source, bug_title, bug_description)
        claude_md.write_text(prompt_content, encoding="utf-8")
        logging.info(f"Prompt injected with bug info and written to {claude_md}")

        # Copy required shell scripts
        import shutil
        for script_name in ["run_all_tests_trace.sh", "run_bug_exposing_tests.sh"]:
            script_source = prompts_dir / script_name
            if not script_source.exists():
                logging.error(f"Required script not found: {script_source}")
                raise FileNotFoundError(f"Required script not found: {script_source}")

            script_dest = bug_dir / script_name
            shutil.copy2(script_source, script_dest)
            # Make script executable
            script_dest.chmod(0o755)
            logging.info(f"Copied script: {script_name}")
    else:
        # Fallback prompt if source doesn't exist
        logging.warning(f"Prompt template not found at {prompt_source}, creating fallback prompt")
        prompt = f"""Fix the bug in this defects4j repository.
Project: {project}
Bug ID: {bug_id}

Analyze the failing tests, identify the bug, and apply the fix.
Use 'defects4j test' to verify your fix works."""
        claude_md.write_text(prompt, encoding="utf-8")
        logging.info(f"Fallback prompt created at {claude_md}")

    # Step 3: Run Claude
    logging.info(f"Starting Claude CLI execution in {bug_dir}")
    exit_code, output, duration = run_claude_headless(
        work_dir=bug_dir,
        verbose=verbose
    )

    logging.info(f"Claude CLI finished. Exit code: {exit_code}, Duration: {duration:.2f}s")

    # Step 4: Test the fix
    logging.info("Starting post-execution testing...")
    compiled, tests_pass, failed_tests = run_defects4j_tests(bug_dir)

    # Step 5: Save results
    logging.info(f"Saving results to {results_csv}")
    save_results_csv(results_csv, project, bug_id, compiled, tests_pass,
                    failed_tests, exit_code, duration)

    # Delete status file after successful completion
    delete_status_file(project, bug_id, results_csv.parent)

    status = "PASS" if tests_pass else "FAIL"
    logging.info(f"Final result for {project}-{bug_id}: {status}")

    return tests_pass

def main():
    parser = argparse.ArgumentParser(
        description="Run Claude Code CLI in automated mode for defects4j bugs"
    )

    # Required arguments
    parser.add_argument("bugs", nargs="+", help="Bug IDs to process (e.g., Chart_1 Lang_2)")

    # Optional arguments
    parser.add_argument("--prompts-dir", default="./prompts", help="Prompts directory")
    parser.add_argument("--results", default="./results.csv", help="Results CSV file")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--silent", "-s", action="store_true", help="Minimal output")

    args = parser.parse_args()

    # Configure logging
    if args.silent:
        logging.getLogger().setLevel(logging.WARNING)
    elif args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Setup
    prompts_dir = Path(args.prompts_dir).resolve()
    results_csv = Path(args.results).resolve()
    ensure_dir(prompts_dir)
    ensure_dir(results_csv.parent)

    # Process bugs
    success_count = 0
    total_count = len(args.bugs)

    for bug_str in args.bugs:
        try:
            # Parse bug ID (e.g., "Chart_1" or "Chart-1")
            bug_str = bug_str.replace("-", "_")
            if "_" not in bug_str:
                logging.error(f"Invalid bug ID format: {bug_str}")
                continue

            project, bug_id = bug_str.rsplit("_", 1)

            # Process the bug
            success = process_single_bug(
                project=project,
                bug_id=bug_id,
                prompts_dir=prompts_dir,
                results_csv=results_csv,
                verbose=args.verbose
            )

            if success:
                success_count += 1

        except KeyboardInterrupt:
            logging.info("\nInterrupted by user")
            break
        except Exception as e:
            logging.error(f"Error processing {bug_str}: {e}")

    # Summary
    print(f"\n{'='*50}")
    print(f"Completed: {success_count}/{total_count} bugs fixed successfully")
    print(f"Results saved to: {results_csv}")

    return 0 if success_count == total_count else 1

if __name__ == "__main__":
    sys.exit(main())