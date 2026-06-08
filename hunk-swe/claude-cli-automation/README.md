# Claude Code CLI Automation (SWE-bench)

Docker-isolated Claude Code CLI runner for the 32 SWE-bench Verified
multi-hunk bugs. Mirrors the gemini-cli and qwen-code automations; each bug is
repaired inside its own per-instance container (correct Python version, conda
env, pinned dependencies pre-installed) so the agent sees real test traces from
a faithful environment, and the host is never touched. Final grading is
delegated to the **official SWE-bench harness** so verdicts are bit-identical
to the leaderboard.

The three automation directories share `hunk-swe/swe_bench_utils/` for the
overlay builder, container plumbing, prompt/record loaders, and the harness
grader. Only the agent CLI (npm package, binary, prompt file convention)
differs.

---

## Architecture overview

For each bug instance, the runner does the following:

```
┌───── HOST ───────────────────────────────────────────────────────────┐
│  1. build_overlay()                                                  │
│        pulls   swebench/sweb.eval.x86_64.<munged-id>:v2              │
│        builds  claude-eval/<munged-id>:latest (base + Node 20 +      │
│                @anthropic-ai/claude-code 2.0.13)                     │
│                                                                      │
│  2. DockerContainer.start()                                          │
│        docker run -d -w /testbed                                     │
│           -v <workspace>/<id>/agent_logs:/agent_logs                 │
│           claude-eval/<id>  sleep <duration>                         │
│                                                                      │
│  3. setup_container() with agent_md_path=/testbed/CLAUDE.md          │
│        apply test_patch (commit it as HEAD)                          │
│        write /testbed/CLAUDE.md  (Claude Code auto-loads this file   │
│        from the working directory), /testbed/.swebench/{problem_     │
│        statement, FAIL_TO_PASS, PASS_TO_PASS, test_cmd, ...}         │
│        install /testbed/run_failing_tests.sh, run_all_tests.sh       │
│                                                                      │
│  4. docker exec -e CLAUDE_CODE_OAUTH_TOKEN=... (or ANTHROPIC_API_KEY) │
│                 -e CLAUDE_HOME=/agent_logs/claude_home               │
│                 -e IS_SANDBOX=1                                      │
│        claude -p "Read and execute the instructions listed in        │
│             CLAUDE.md." --output-format stream-json --verbose        │
│             --dangerously-skip-permissions                           │
│             > /agent_logs/claude-trajectory-<ts>.jsonl               │
│        NDJSON stream events    → trajectory (tool calls, turns)      │
│        Full session JSONL log → CLAUDE_HOME/projects/<cwd>/<id>.jsonl│
│                                                                      │
│  5. docker exec git diff --binary HEAD   → patch-<ts>.diff           │
│                                                                      │
│  6. grade_instance() → swebench.harness.run_evaluation               │
│        Builds its own grader container, applies the patch, runs the  │
│        canonical eval.sh, writes report.json. We translate that into │
│        the per-bug CSV row.                                          │
│                                                                      │
│  7. docker rm -f <container>                                         │
└──────────────────────────────────────────────────────────────────────┘
```

---

## Model + API

| Field | Default |
|-------|---------|
| Agent CLI | `@anthropic-ai/claude-code` 2.0.13 (npm) |
| Underlying model | `claude-sonnet-4-5-20250929` (passed explicitly so the manifest records it) |
| API endpoint | Anthropic's standard `https://api.anthropic.com` |
| Auth env vars | `CLAUDE_CODE_OAUTH_TOKEN` (OAuth token, preferred) or `ANTHROPIC_API_KEY` (API key) |
| Inside-container env | `CLAUDE_CODE_OAUTH_TOKEN` or `ANTHROPIC_API_KEY`, `CLAUDE_HOME=/agent_logs/claude_home`, `IS_SANDBOX=1` |

Claude Code CLI supports two authentication methods:
- **OAuth token** (Max subscription): `CLAUDE_CODE_OAUTH_TOKEN=sk-ant-oat01-...` - preferred to avoid billing API credits
- **API key** (pay-per-token): `ANTHROPIC_API_KEY=sk-ant-...`

OAuth takes precedence if both are set.

`CLAUDE_HOME` is redirected into the bind-mounted `/agent_logs` directory so
Claude's per-session JSONL log is captured automatically (otherwise it would be
written to `/root/.claude/sessions/...` and disappear when the container is
removed).

`IS_SANDBOX=1` tells Claude Code it's running in a sandbox environment, which allows
`--dangerously-skip-permissions` to work even when running as root in Docker containers.
This eliminates permission prompts and enables full tool access (Edit, Bash, Read, Write)
for optimal performance.

---

## Prerequisites

- Docker Desktop running (`docker ps` should succeed).
- ~30 GB free in Docker Desktop's disk image.
- **Authentication** - choose one:
  - **API key** (pay-per-token): `.env` file with `ANTHROPIC_API_KEY=sk-ant-...`
  - **OAuth token** (Max subscription): Generate with `claude setup-token`, then `.env` file with `CLAUDE_CODE_OAUTH_TOKEN=sk-ant-oat01-...`

  OAuth takes precedence if both are set (to avoid accidentally billing API credits).
- The 32-bug bug list at
  `hunk-swe/swe_bench_verified/multihunk_bugs_swe_bench_verified_32.json`
  and the SWE-bench Verified records at
  `hunk-swe/swe_bench_verified/swe_bench.jsonl` (already in repo).
- A Python environment with `swebench` installed:
  ```bash
  conda env create -f hunk-swe/environment.yml
  conda activate swe-bench-eval
  ```
- **Node.js / npm / claude on the host: not required.** Everything the agent
  needs is installed inside the per-instance Docker image.

---

## Running the Full Evaluation (All 32 Bugs)

### Quick Start

To run Claude Code on all 32 multi-hunk bugs:

```bash
# 1. Navigate to the automation directory
cd hunk-swe/claude-cli-automation

# 2. Activate the conda environment
conda activate swe-bench-eval

# 3. Run the automation (uses default 30-minute timeout per bug)
python3 automated_claude_cli.py
```

### Step-by-Step Instructions

**Step 1: Verify Prerequisites**

```bash
# Check Docker is running
docker ps

# Verify conda environment exists
conda env list | grep swe-bench-eval

# Check authentication is configured
cat .env | grep -E "ANTHROPIC_API_KEY|CLAUDE_CODE_OAUTH_TOKEN"
```

**Step 2: Activate Environment**

```bash
conda activate swe-bench-eval
```

**Step 3: Run Automation**

```bash
# Default run (30 min timeout per bug)
python3 automated_claude_cli.py

# Or with custom timeout (e.g., 60 minutes per bug)
python3 automated_claude_cli.py --duration-min 60
```

### What to Expect

**Runtime:**
- **Per bug**: ~2-5 minutes (fast bugs) to 30 minutes (timeout)
- **All 32 bugs**: ~1-3 hours total (depending on bug complexity)
- Uses `IS_SANDBOX=1` for zero permission denials and optimal performance

**Progress Tracking:**
- **Console output**: Live log messages showing current bug, status, and results
- **`config/processed_claude.json`**: Updated after each bug completes
- **`results/test_results_model_claude.csv`**: Appended with each result

**Example console output:**
```
2026-05-07 10:06:35 INFO - Total: 32  Processed: 0  Remaining: 32
2026-05-07 10:06:35 INFO - === astropy__astropy-13033 ===
2026-05-07 10:06:35 INFO - [astropy__astropy-13033] building overlay...
2026-05-07 10:06:37 INFO - [astropy__astropy-13033] launching Claude Code (timeout 30 min)
2026-05-07 10:09:06 INFO - [astropy__astropy-13033] claude exit code 0
2026-05-07 10:09:13 INFO - results: astropy__astropy-13033 resolved=True ftp=True noreg=True
2026-05-07 10:09:13 INFO - === django__django-11138 ===
...
```

### Monitoring Progress

**Real-time:**
```bash
# Watch the processed bugs list
watch -n 5 "cat config/processed_claude.json | jq length"

# Monitor results CSV
tail -f results/test_results_model_claude.csv

# Check Docker containers
docker ps | grep swebench-claude
```

**Check specific bug logs:**
```bash
# Latest trajectory for a bug
ls -lt workspace_docker/astropy__astropy-13033/logs/claude-trajectory-*.jsonl | head -1

# Latest patch
ls -lt workspace_docker/astropy__astropy-13033/logs/patch-*.diff | head -1

# Console output
cat workspace_docker/astropy__astropy-13033/logs/run-*.log | tail -50
```

### Resuming After Interruption

If the automation is interrupted (Ctrl+C, system crash, etc.), simply **re-run the same command**:

```bash
python3 automated_claude_cli.py
```

**How resume works:**
1. Script reads `config/processed_claude.json` to see which bugs completed
2. Automatically skips completed bugs
3. Continues from where it left off

**Force re-run a specific bug:**
```bash
# Edit the processed list to remove the bug
nano config/processed_claude.json  # Remove "bug-id" from the array

# Or re-run just that bug
python3 automated_claude_cli.py --only astropy__astropy-13033
```

### Expected Costs

**With OAuth token (Max subscription):**
- **Per bug**: $0.30-$0.70 (varies by complexity)
- **All 32 bugs**: ~$15-25 total
- May hit daily spending caps; run will pause if cap reached

**With API key (pay-per-token):**
- Same cost structure, but billed directly
- No spending cap limitations

### After Completion

**Review results:**
```bash
# Summary statistics
cat results/test_results_model_claude.csv | tail -n +2 | awk -F',' '{print $2}' | sort | uniq -c

# Count resolved bugs
grep ",Yes," results/test_results_model_claude.csv | wc -l

# List failed bugs
grep ",No," results/test_results_model_claude.csv | cut -d',' -f1
```

**Generate manifest:**
```bash
# Check reproducibility manifest
cat image_manifest.json | jq '.[] | {instance_id, cli_version, model}'
```

**Collect patches:**
```bash
# All patches are in workspace_docker/<instance_id>/logs/patch-*.diff
find workspace_docker -name "patch-*.diff" -type f
```

---

## Usage

### First-time / single-bug debug run

```bash
cd hunk-swe/claude-cli-automation
python3 automated_claude_cli.py --only astropy__astropy-13033 --duration-min 30 --keep-container
```

`--keep-container` leaves the container running so you can
`docker exec -it <name> bash -l` and poke around.

### Full batch (all 32 bugs)

```bash
cd hunk-swe/claude-cli-automation
python3 automated_claude_cli.py
```

### Useful flags

| Flag | Default | Purpose |
|------|---------|---------|
| `--only <id>...` | all 32 | Process only a subset of instance IDs |
| `--start-from <id>` | first | Resume from a specific instance (inclusive) |
| `--duration-min <n>` | 30 | Per-bug agent timeout in minutes |
| `--model <name>` | `claude-sonnet-4-5-20250929` | Underlying LLM; change only if you want to override the default |
| `--claude-version <spec>` | `2.0.13` | npm spec for `@anthropic-ai/claude-code` |
| `--node-major <n>` | `20` | Node.js major version baked into the overlay |
| `--image-base <repo>` | `swebench/sweb.eval.x86_64` | DockerHub (immutable `:v2`) |
| `--image-tag <tag>` | `v2` | Tag on the instance image registry |
| `--keep-container` | off | Leave container running after each bug (debugging) |
| `--no-build` | off | Skip overlay build; require pre-built images |
| `--results-tag <tag>` | `claude` | Tag the results CSV (`test_results_model_<tag>.csv`) |
| `--run-id-suffix <tag>` | `run1` | Tag passed to swebench's `run_evaluation` as `run_id` |

### Resuming after an interrupted run

`config/processed_claude.json` lists already-completed instance IDs. Re-running
picks up where it left off. To force re-processing a bug, remove its entry.

---

## Output layout

```
claude-cli-automation/
├── workspace_docker/<instance_id>/
│   ├── agent_logs/                                  # bind-mounted into container
│   │   ├── claude-trajectory-<ts>.jsonl             # NDJSON stream from `--output-format stream-json --verbose`
│   │   ├── claude-last-message-<ts>.txt             # final agent message
│   │   └── claude_home/                             # CLAUDE_HOME redirect
│   │       └── projects/<encoded-cwd>/<id>.jsonl    # full claude session log
│   └── logs/
│       ├── run-<ts>.log                             # human-readable Claude console (empty - stdout redirected)
│       ├── claude-trajectory-<ts>.jsonl             # mirror of agent_logs
│       ├── claude-last-message-<ts>.txt             # mirror of agent_logs
│       ├── claude-session-<id>.jsonl                # mirror of CLAUDE_HOME session log
│       ├── patch-<ts>.diff                          # final patch (git diff HEAD)
│       ├── swebench_report.json                     # canonical leaderboard verdict
│       ├── swebench_eval.sh                         # exact command swebench ran
│       ├── swebench_test_output.txt                 # raw output from grader's run
│       └── swebench_grader/                         # full nested swebench tree
├── results/test_results_model_claude.csv            # per-bug pass/fail results
├── config/processed_claude.json                     # progress tracking
└── image_manifest.json                              # base + overlay digests + model
```

### Reading the trajectory + session log

**`claude-trajectory-<ts>.jsonl`** — NDJSON stream emitted by `claude --output-format stream-json --verbose`
to stdout, one JSON object per line. Each event has a `type` (e.g.
`agent_message`, `tool_call`, `tool_result`, `turn_complete`). With `--verbose`,
includes all tool calls, tool results, and assistant messages. This is the
ordered behavioral trace used by the trajectory analysis (Figures 9–10 in the
paper).

**`claude-session-<id>.jsonl`** — Claude's full internal session log written
under `CLAUDE_HOME/projects/<encoded-cwd>/<id>.jsonl`. Includes everything the
trajectory has, plus internal reasoning blocks, retries, and the resolved system
prompt. Useful for debugging.

**`claude-last-message-<ts>.txt`** — the final assistant message at the end of
the session.

To parse the trajectory into an ordered sequence:

```python
import json
with open("claude-trajectory-<ts>.jsonl") as f:
    events = [json.loads(line) for line in f if line.strip()]
tool_calls = [e for e in events if e.get("type") == "tool_call"]
```

---

## What runs on the host vs inside the container

| Runs on host | Runs inside the agent container | Runs inside the swebench grader container |
|--------------|--------------------------------|------------------------------------------|
| Reading the bug list / records | `git apply` of test_patch | `git apply` of model_patch |
| Building overlay images | Writing CLAUDE.md, scripts, .swebench/* | `eval.sh` (canonical test_cmd run) |
| `docker run` / `docker exec` | Claude Code CLI agent loop (`claude`) | Producing report.json |
| Writing CSVs / patches / logs | All file edits + shell commands the agent issues | |
| Invoking `swebench.harness.run_evaluation` | `git diff HEAD` for the patch | |

---

## Troubleshooting

**`401 Unauthorized` from Anthropic** — `ANTHROPIC_API_KEY` not picked up. Confirm
the key is in `.env` next to this README, or `export ANTHROPIC_API_KEY=...`
before running.

**`pull access denied for claude-eval/...`** — the overlay image hasn't been
built yet. Re-run; the script builds it automatically.

**`No module named django` / `No module named pytest`** inside the container —
the `testbed` conda env didn't activate. Both runner scripts use `#!/bin/bash
-l` to source the conda init. If invoking manually, wrap with `bash -lc '...'`.

**Claude Code says it's not in a git repo** — the default SWE-bench base images
all ship a populated `/testbed` git repo.

**`InvalidBaseImagePlatform` warning on Apple Silicon** — cosmetic. SWE-bench
ships `linux/amd64` only; Docker Desktop runs them under Rosetta automatically.

**Claude Code hangs / interactive prompt** — `--dangerously-skip-permissions`
should suppress every confirmation dialog; if Claude still pauses, run with
`--debug` and inspect the session JSONL for the unanswered prompt.

---

## Reproducibility note

`image_manifest.json` records, for every instance run:
- `base_image` + `base_digest` (SWE-bench DockerHub instance image)
- `overlay_image` + `overlay_digest` (our Node + Claude Code overlay)
- `node_major`, `cli_npm_package`, `cli_version`
- `model` (the model value passed — defaults to `claude-sonnet-4-5-20250929`)

Keep this file checked in alongside the patches so reviewers can verify the
exact artifacts used.
