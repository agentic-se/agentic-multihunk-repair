import argparse, csv, json, logging, os, re, shlex, signal, subprocess, sys, time, contextlib
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple
import shutil
import subprocess, sys, shlex, os, time
from pathlib import Path
from typing import Optional
from src_code_to_dir_mapping import d4j_path_prefix

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

MCP_SCRIPT = "/Users/danielding/Desktop/progctx-mcp/mcp_server/java_analysis_server.py"
BUGS_ROOT  = Path("/Users/danielding/Desktop/example_dir")

def write_per_bug_gemini_settings(proj: str, bug_num: int):
    bug_root = BUGS_ROOT / f"{proj}_{bug_num}"
    src_prefix = d4j_path_prefix(proj, bug_num)
    java_src = (bug_root / src_prefix).resolve()

    cfg_dir = Path("~/.gemini").expanduser()
    cfg_dir.mkdir(parents=True, exist_ok=True)
    cfg_path = cfg_dir / "settings.json"

    settings = {
        "mcpServers": {
            "java-analysis-server": {
                "command": "python",
                "args": [MCP_SCRIPT],
                "env": {
                    "JAVA_PROJECT_PATH": str(java_src)
                },
                "transport": {"type": "stdio"}
            }
        },
        "security": {
            "auth": {"selectedType": "gemini-api-key"}
        }
    }
    cfg_path.write_text(json.dumps(settings, indent=2), encoding="utf-8")
    return cfg_path

def git_rev_parse_head(bug_dir: Path) -> Optional[str]:
    code, out = run_cmd_stream(["git", "rev-parse", "HEAD"], cwd=bug_dir, timeout=30)
    if code == 0 and out.strip():
        return out.strip().splitlines()[-1]
    return None

def copy_test_scripts(bug_dir: Path):
    scripts = [
        Path("./agentic_ai/run_bug_exposing_tests.sh"),
        Path("./agentic_ai/run_all_tests_trace.sh")
    ]
    for script in scripts:
        if script.is_file():
            shutil.copy(script, bug_dir / script.name)
            logging.info(f"Copied {script} → {bug_dir / script.name}")
        else:
            logging.warning(f"Script not found: {script}")

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



def checkout_repo(project, bug_id, work_dir):
    try:
        subprocess.run(
            ['defects4j', 'checkout', '-p', project, '-v', f'{bug_id}b',
             '-w', f'{work_dir}/{project}_{bug_id}'],
            check=True
        )
        return True
    except subprocess.CalledProcessError as e:
        print(f"Checkout failed for {project}-{bug_id}: {e}")
        return False

def ts() -> str:
    return datetime.now().strftime("%Y-%m-%d-%H%M%S")

def ensure_dir(p: Path) -> Path:
    p.mkdir(parents=True, exist_ok=True); return p

def run_cmd_stream(cmd,
                   cwd: Optional[Path] = None,
                   env: Optional[dict] = None,
                   timeout: Optional[int] = None,
                   tee_path: Optional[Path] = None) -> tuple[int, str]:
    if isinstance(cmd, str):
        cmd_list = shlex.split(cmd)
    else:
        cmd_list = list(cmd)

    proc_env = os.environ.copy()
    if env:
        proc_env.update(env)

    captured = []
    start = time.monotonic()

    with open(tee_path, "w", encoding="utf-8") if tee_path else open(os.devnull, "w") as logf:
        proc = subprocess.Popen(
            cmd_list,
            cwd=str(cwd) if cwd else None,
            env=proc_env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,   # merge stderr into stdout
            text=True,
            bufsize=1,
            universal_newlines=True
        )

        for line in proc.stdout:
            sys.stdout.write(line)      # live stream to terminal
            sys.stdout.flush()
            logf.write(line)            # save to file
            logf.flush()
            captured.append(line)

            if timeout and (time.monotonic() - start) > timeout:
                proc.kill()
                return 124, "".join(captured)

        proc.wait()
        return proc.returncode, "".join(captured)


def parse_failed_tests(d4j_test_output: str) -> list[str]:
    failed = []
    m = re.search(r"Failing tests:\s*(\d+)", d4j_test_output)
    if not m: return failed
    n = int(m.group(1))
    if n == 0: return failed
    lines = d4j_test_output.splitlines()
    capture = False
    for line in lines:
        if re.search(r"Failing tests:\s*\d+", line):
            capture = True; continue
        if capture:
            if line.strip().startswith("- "):
                failed.append(line.strip()[2:].strip())
            elif line.strip() == "":
                break
    return failed

def run_defects4j_compile_and_test(bug_dir: Path) -> tuple[int, int, list[str], float, float]:
    compile_code, _ = run_cmd_stream("defects4j compile", cwd=bug_dir, timeout=1800)

    if compile_code != 0:
        return compile_code, 0, []

    t1 = time.monotonic()
    test_code, test_out = run_cmd_stream("defects4j test", cwd=bug_dir, timeout=3600)

    failed_tests = parse_failed_tests(test_out)
    test_result = 1 if (test_code == 0 and not failed_tests) else 0
    return compile_code, test_result, failed_tests

def read_base_prompt_and_inject(base_prompt_path: Path, bug_title: str, bug_description: str) -> str:
    base = base_prompt_path.read_text(encoding="utf-8")
    return (base
            .replace("{{bug_title}}", bug_title or "(title unavailable)")
            .replace("{{bug_description}}", (bug_description or "").strip()))

def load_bug_report(meta_json: Path, bug_id: str) -> Tuple[Optional[str], Optional[str]]:
    data = json.loads(meta_json.read_text(encoding="utf-8"))
    entry = data.get(bug_id, {})
    br = entry.get("bug_report", {})
    print(meta_json)
    return br.get("title"), br.get("bug_description")

def write_bug_specific_prompt(bug_dir: Path, project: str, bug_id: str,
                              rendered_prompt_markdown: str) -> tuple[Path, Path]:
    agentic = ensure_dir(bug_dir)
    bug_id = f"{project}_{bug_id}"
    target_named = agentic / f"prompt_{bug_id}.md"
    target_current = agentic / "AGENT.md"
    target_named.write_text(rendered_prompt_markdown, encoding="utf-8")
    target_current.write_text(rendered_prompt_markdown, encoding="utf-8")
    return target_named, target_current

def copy_env(env_src: Optional[Path], bug_dir: Path) -> Optional[Path]:
    if env_src and env_src.is_file():
        dst = bug_dir / ".env"
        dst.write_bytes(env_src.read_bytes())
        return dst
    return None

# ------------------------- Results CSV API ----------------------------
def write_result_csv(project, bug_id, compile_result, test_result, failed_tests, mode,
                     results_base_path):
    results_file_path = os.path.abspath(os.path.join(results_base_path, f"test_results_mode_{mode}.csv"))
    file_exists = os.path.isfile(results_file_path)
    ensure_dir(Path(results_base_path))
    with open(results_file_path, mode='a', newline='') as file:
        writer = csv.writer(file)
        if not file_exists:
            writer.writerow(['bug', 'pass', 'test_fail', 'compile_fail', 'failed_tests'])
        pass_status = 'Yes' if test_result == 1 and compile_result == 0 else 'No'
        test_fail = 'Yes' if pass_status == 'No' and compile_result == 0 else 'No'
        compile_fail = 'Yes' if compile_result != 0 else 'No'
        writer.writerow([
            f'{project}-{bug_id}',
            pass_status,
            test_fail,
            compile_fail,
            '; '.join(failed_tests),
        ])
    logging.info(f"Results written for {project}-{bug_id}: Pass: {pass_status}, Test Fail: {test_fail}, Compile Fail: {compile_fail}, Failed Tests: {failed_tests}")

# ------------------------------ per-bug --------------------------------
def process_bug(bug_id: str, *,
                model: str,
                workspace: Path,
                meta_path: Path,
                base_prompt_path: Path,
                env_file: Optional[Path],
                gemini_bin: str,
                duration_min: int,
                results_base: Path,
                mode: str,
                debug: bool):
    if "_" not in bug_id:
        logging.warning(f"Skipping malformed key: {bug_id}")
        return
    project, bug_id = bug_id.rsplit("_", 1)
    if not bug_id.isdigit():
        logging.warning(f"Skipping malformed key: {bug_id}")
        return

    bug_dir = workspace / f"{project}_{bug_id}"
    logging.info(f"=== {bug_id}: checkout ===")
    if not checkout_repo(project, bug_id, str(workspace)):
        write_result_csv(project, bug_id, compile_result=1, test_result=0, failed_tests=[],
                         mode=mode, results_base_path=str(results_base))
        return

    # After successful checkout
    base_rev = git_rev_parse_head(bug_dir)
    logging.info(f"{bug_id}: base commit = {base_rev}")

    copy_test_scripts(bug_dir)

    # Render prompt
    title, description = load_bug_report(meta_path, f"{project}_{bug_id}")
    rendered = read_base_prompt_and_inject(base_prompt_path, title or "", description or "")
    named_prompt, current_prompt = write_bug_specific_prompt(bug_dir, project, bug_id, rendered)
    logging.info(f"{bug_id}: wrote prompt → {named_prompt.name} and AGENT.md")

    # Copy .env
    copied_env = copy_env(env_file, bug_dir) if env_file else None
    if env_file:
        logging.info(f"{bug_id}: .env copied → {copied_env}" if copied_env else f"{bug_id}: .env not found")

    # Prepare logs
    logs_dir = ensure_dir(bug_dir / "logs")
    stamp = ts()
    telemetry_json = logs_dir / f"gemini-{stamp}.json"
    console_log = logs_dir / f"run-{stamp}.log"

    write_per_bug_gemini_settings(project, int(bug_id))

    gemini_cmd = [
        gemini_bin,
        "--model", model,
        "--yolo",                                  # let it take actions
        "-p", "Read and execute the instructions listed in AGENT.md.",
        "--telemetry",
        "--telemetry-target=local",
        "--telemetry-otlp-endpoint=",
        "--telemetry-log-prompts",
        f"--telemetry-outfile={str(telemetry_json)}",
    ]
    env = os.environ.copy()
    if debug: env["DEBUG"] = "1"

    logging.info(f"{bug_id}: launching Gemini (timeout {duration_min} min)")
    print(gemini_cmd)
    code, _ = run_cmd_stream(gemini_cmd, cwd=bug_dir, env=env, timeout=duration_min * 60, tee_path=console_log)

    logging.info(f"{bug_id}: Gemini exit code {code}")

    # Verify compile & test
    logging.info(f"{bug_id}: verifying with defects4j compile & test")
    compile_code, test_result, failed_tests = run_defects4j_compile_and_test(bug_dir)

    write_result_csv(project, bug_id, compile_result=compile_code, test_result=test_result,
                     failed_tests=failed_tests, mode=mode, results_base_path=str(results_base),
                     )

    # Save patch/diff
    patch_file = save_patch(bug_dir, logs_dir, base_rev)
    try:
        size = patch_file.stat().st_size
    except Exception:
        size = 0
    logging.info(f"{bug_id}: saved patch → {patch_file} ({size} bytes)")

# ------------------------------- main ---------------------------------
def main():
    ap = argparse.ArgumentParser(description="Batch-run Gemini CLI APR for all bugs in method_multihunk.json")
    ap.add_argument("--model", default="gemini-2.5-flash", help="Model name")
    ap.add_argument("--workspace", default="~/Desktop/example_dir", help="Where to checkout bugs")
    ap.add_argument("--env-file", default="./.env", help="Path to .env with GEMINI_API_KEY")
    ap.add_argument("--meta-json", default="./config/50_random_bugs_final_tosem.json", help="Path to method_multihunk.json")
    ap.add_argument("--base-prompt", default="./agentic_ai/prompt_mcp.md", help="Path to base prompt.md with {{bug_title}} and {{bug_description}}")
    ap.add_argument("--gemini-bin", default="gemini", help="Gemini CLI binary")
    ap.add_argument("--duration-min", type=int, default=30, help="Per-bug hard timeout")
    ap.add_argument("--results-base", default="./results", help="Folder to store CSV results")
    ap.add_argument("--mode", default="4", help="Tag for results CSV filename")
    ap.add_argument("--only", nargs="*", default=None, help="Optional subset of bug keys to run, e.g. Chart_2 Lang_5")
    ap.add_argument("--start-from", default=None, help="Optional bug key to start from (inclusive)")
    ap.add_argument("--processed-json", default="./config/processed_gemini.json", help="File storing already processed bugs")
    ap.add_argument("--debug", action="store_true")
    args = ap.parse_args()

    workspace = Path(os.path.expanduser(args.workspace)).resolve(); ensure_dir(workspace)
    results_base = Path(os.path.expanduser(args.results_base)).resolve(); ensure_dir(results_base)
    meta_path = Path(os.path.expanduser(args.meta_json)).resolve()
    base_prompt_path = Path(os.path.expanduser(args.base_prompt)).resolve()
    env_file = Path(os.path.expanduser(args.env_file)).resolve() if args.env_file else None
    processed_path = Path(os.path.expanduser(args.processed_json)).resolve()

    data = json.loads(meta_path.read_text(encoding="utf-8"))
    all_keys = list(data.keys())

    if processed_path.exists():
        processed = set(json.loads(processed_path.read_text(encoding="utf-8")))
    else:
        processed = set()

    if args.only:
        wanted = set(args.only)
        all_keys = [k for k in all_keys if k in wanted]
    if args.start_from and args.start_from in all_keys:
        idx = all_keys.index(args.start_from)
        all_keys = all_keys[idx:]

    to_run = [k for k in all_keys if k not in processed]

    logging.info(f"Total bugs to process: {len(all_keys)}")
    logging.info(f"Skipping {len(processed)} already processed bugs")
    logging.info(f"Remaining to run: {len(to_run)}")

    for bug_id in to_run:
        try:
            process_bug(
                bug_id,
                model=args.model,
                workspace=workspace,
                meta_path=meta_path,
                base_prompt_path=base_prompt_path,
                env_file=env_file,
                gemini_bin=args.gemini_bin,
                duration_min=args.duration_min,
                results_base=results_base,
                mode=args.mode,
                debug=args.debug
            )
            processed.add(bug_id)
            processed_path.write_text(json.dumps(sorted(processed), indent=2), encoding="utf-8")

        except Exception as e:
            logging.exception(f"{bug_id}: error {e}")
            if "_" in bug_id:
                project, bug_num = bug_id.rsplit("_", 1)
                write_result_csv(project, bug_num, compile_result=1, test_result=0, failed_tests=[],
                                 mode=args.mode, results_base_path=str(results_base))

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[!] Interrupted by user", file=sys.stderr)
        sys.exit(130)
