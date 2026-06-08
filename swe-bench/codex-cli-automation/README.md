# Codex CLI Automation (SWE-bench)

Docker-isolated OpenAI Codex CLI runner for the 32 SWE-bench Verified
multi-hunk bugs. Mirrors the gemini-cli and qwen-code automations; each bug is
repaired inside its own per-instance container (correct Python version, conda
env, pinned dependencies pre-installed) so the agent sees real test traces from
a faithful environment, and the host is never touched. Final grading is
delegated to the **official SWE-bench harness** so verdicts are bit-identical
to the leaderboard.

The three automation directories share `swe-bench/swe_bench_utils/` for the
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
│        builds  codex-eval/<munged-id>:latest (base + Node 20 +       │
│                @openai/codex 0.21.0)                                 │
│                                                                      │
│  2. DockerContainer.start()                                          │
│        docker run -d -w /testbed                                     │
│           -v <workspace>/<id>/agent_logs:/agent_logs                 │
│           codex-eval/<id>  sleep <duration>                          │
│                                                                      │
│  3. setup_container() with agent_md_path=/testbed/AGENTS.md          │
│        apply test_patch (commit it as HEAD)                          │
│        write /testbed/AGENTS.md  (codex auto-loads this file as      │
│        an instructions overlay), /testbed/.swebench/{problem_        │
│        statement, FAIL_TO_PASS, PASS_TO_PASS, test_cmd, ...}         │
│        install /testbed/run_failing_tests.sh, run_all_tests.sh       │
│                                                                      │
│  4. docker exec -e OPENAI_API_KEY=... -e CODEX_HOME=/agent_logs/...  │
│        codex exec --dangerously-bypass-approvals-and-sandbox         │
│             --skip-git-repo-check --json                             │
│             --output-last-message /agent_logs/codex-last-message...  │
│             -m gpt-5 -C /testbed                                     │
│             "Read and execute the instructions listed in AGENTS.md." │
│             > /agent_logs/codex-trajectory-<ts>.jsonl                │
│        Stdout JSONL events    → trajectory                           │
│        Final agent message    → last-message file                    │
│        Full session JSONL log → CODEX_HOME/sessions/.../<id>.jsonl   │
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
| Agent CLI | `@openai/codex` 0.21.0 (npm) |
| Underlying model | `gpt-5` (built-in default of codex 0.21.0; we pass it explicitly via `-m gpt-5` so the manifest records it) |
| API endpoint | OpenAI's standard `https://api.openai.com/v1` |
| Auth env var | `OPENAI_API_KEY` |
| Inside-container env | `OPENAI_API_KEY`, `CODEX_HOME=/agent_logs/codex_home` |

Codex 0.21.0 supports two auth paths: API key (via `OPENAI_API_KEY`) and a
ChatGPT-account login that writes to `~/.codex/auth.json`. Our automation uses
the API-key path because it works in fresh, ephemeral containers without an
interactive login step.

`CODEX_HOME` is redirected into the bind-mounted `/agent_logs` directory so
codex's per-session JSONL log is captured automatically (otherwise it would be
written to `/root/.codex/sessions/...` and disappear when the container is
removed).

---

## Prerequisites

- Docker Desktop running (`docker ps` should succeed).
- ~30 GB free in Docker Desktop's disk image.
- A `.env` file in this directory containing the API key:
  ```
  OPENAI_API_KEY=sk-...
  ```
  (or `export OPENAI_API_KEY=...` in your shell.)
- The 32-bug bug list at
  `swe-bench/swe_bench_verified/multihunk_bugs_swe_bench_verified_32.json`
  and the SWE-bench Verified records at
  `swe-bench/swe_bench_verified/swe_bench.jsonl` (already in repo).
- A Python environment with `swebench` installed:
  ```bash
  conda env create -f swe-bench/environment.yml
  conda activate swe-bench-eval
  ```
- **Node.js / npm / codex on the host: not required.** Everything the agent
  needs is installed inside the per-instance Docker image.

---

## Usage

### First-time / single-bug debug run

```bash
cd swe-bench/codex-cli-automation
python3 automated_codex_cli.py --only astropy__astropy-13033 --duration-min 30 --keep-container
```

`--keep-container` leaves the container running so you can
`docker exec -it <name> bash -l` and poke around.

### Full batch (all 32 bugs)

```bash
cd swe-bench/codex-cli-automation
python3 automated_codex_cli.py
```

### Useful flags

| Flag | Default | Purpose |
|------|---------|---------|
| `--only <id>...` | all 32 | Process only a subset of instance IDs |
| `--start-from <id>` | first | Resume from a specific instance (inclusive) |
| `--duration-min <n>` | 30 | Per-bug agent timeout in minutes |
| `--model <name>` | `gpt-5` | Underlying LLM (passed via `-m`); change only if you want to override codex's default |
| `--codex-version <spec>` | `0.21.0` | npm spec for `@openai/codex` |
| `--node-major <n>` | `20` | Node.js major version baked into the overlay |
| `--image-base <repo>` | `swebench/sweb.eval.x86_64` | DockerHub (immutable `:v2`) |
| `--image-tag <tag>` | `v2` | Tag on the instance image registry |
| `--keep-container` | off | Leave container running after each bug (debugging) |
| `--no-build` | off | Skip overlay build; require pre-built images |
| `--results-tag <tag>` | `codex` | Tag the results CSV (`test_results_model_<tag>.csv`) |
| `--run-id-suffix <tag>` | `run1` | Tag passed to swebench's `run_evaluation` as `run_id` |

### Resuming after an interrupted run

`config/processed_codex.json` lists already-completed instance IDs. Re-running
picks up where it left off. To force re-processing a bug, remove its entry.

---

## Output layout

```
codex-cli-automation/
├── workspace_docker/<instance_id>/
│   ├── agent_logs/                                  # bind-mounted into container
│   │   ├── codex-trajectory-<ts>.jsonl              # JSONL event stream from `codex --json`
│   │   ├── codex-last-message-<ts>.txt              # final agent message
│   │   └── codex_home/                              # CODEX_HOME redirect
│   │       └── sessions/<date>/<id>.jsonl           # full codex session log
│   └── logs/
│       ├── run-<ts>.log                             # human-readable Codex console
│       ├── codex-trajectory-<ts>.jsonl              # mirror of agent_logs
│       ├── codex-last-message-<ts>.txt              # mirror of agent_logs
│       ├── codex-session-<id>.jsonl                 # mirror of CODEX_HOME session log
│       ├── patch-<ts>.diff                          # final patch (git diff HEAD)
│       ├── swebench_report.json                     # canonical leaderboard verdict
│       ├── swebench_eval.sh                         # exact command swebench ran
│       ├── swebench_test_output.txt                 # raw output from grader's run
│       └── swebench_grader/                         # full nested swebench tree
├── results/test_results_model_codex.csv             # per-bug pass/fail results
├── config/processed_codex.json                      # progress tracking
└── image_manifest.json                              # base + overlay digests + model
```

### Reading the trajectory + session log

**`codex-trajectory-<ts>.jsonl`** — JSONL events emitted by `codex exec --json`
to stdout, one JSON object per line. Each event has a `type` (e.g.
`agent_message`, `tool_call`, `patch_applied`, `task_complete`). This is the
ordered behavioral trace used by the trajectory analysis (Figures 9–10 in the
paper).

**`codex-session-<id>.jsonl`** — codex's full internal session log written
under `CODEX_HOME/sessions/<date>/<id>.jsonl`. Includes everything the
trajectory has, plus internal reasoning records and the resolved system
prompt. Useful for debugging.

**`codex-last-message-<ts>.txt`** — the final assistant message at the end of
the session.

To parse the trajectory into an ordered sequence:

```python
import json
with open("codex-trajectory-<ts>.jsonl") as f:
    events = [json.loads(line) for line in f if line.strip()]
tool_calls = [e for e in events if e.get("type") == "tool_call"]
```

---

## What runs on the host vs inside the container

| Runs on host | Runs inside the agent container | Runs inside the swebench grader container |
|--------------|--------------------------------|------------------------------------------|
| Reading the bug list / records | `git apply` of test_patch | `git apply` of model_patch |
| Building overlay images | Writing AGENTS.md, scripts, .swebench/* | `eval.sh` (canonical test_cmd run) |
| `docker run` / `docker exec` | Codex CLI agent loop (`codex exec`) | Producing report.json |
| Writing CSVs / patches / logs | All file edits + shell commands the agent issues | |
| Invoking `swebench.harness.run_evaluation` | `git diff HEAD` for the patch | |

---

## Troubleshooting

**`401 Unauthorized` from OpenAI** — `OPENAI_API_KEY` not picked up. Confirm
the key is in `.env` next to this README, or `export OPENAI_API_KEY=...`
before running.

**`pull access denied for codex-eval/...`** — the overlay image hasn't been
built yet. Re-run; the script builds it automatically.

**`No module named django` / `No module named pytest`** inside the container —
the `testbed` conda env didn't activate. Both runner scripts use `#!/bin/bash
-l` to source the conda init. If invoking manually, wrap with `bash -lc '...'`.

**Codex says it's not in a git repo** — `--skip-git-repo-check` is already
passed, but if you build a custom overlay without `git init`, codex will warn.
The default SWE-bench base images all ship a populated `/testbed` git repo.

**`InvalidBaseImagePlatform` warning on Apple Silicon** — cosmetic. SWE-bench
ships `linux/amd64` only; Docker Desktop runs them under Rosetta automatically.

**Codex hangs / interactive prompt** — `--dangerously-bypass-approvals-and-sandbox`
should suppress every confirmation dialog; if codex still pauses, run with
`--debug` (forwarded inside the container via `env`) and inspect the session
JSONL for the unanswered prompt.

---

## Reproducibility note

`image_manifest.json` records, for every instance run:
- `base_image` + `base_digest` (SWE-bench DockerHub instance image)
- `overlay_image` + `overlay_digest` (our Node + codex overlay)
- `node_major`, `cli_npm_package`, `cli_version`
- `model` (the `-m` value passed to `codex exec` — defaults to `gpt-5`,
  matching codex 0.21.0's built-in default)

Keep this file checked in alongside the patches so reviewers can verify the
exact artifacts used.
