# Qwen Code Automation (SWE-bench)

Docker-isolated Qwen Code CLI runner for the 32 SWE-bench Verified multi-hunk
bugs. Mirrors the gemini-cli automation; each bug is repaired inside its own
per-instance container (with the right Python version, conda env, and pinned
dependencies pre-installed) so the agent sees real test traces from a faithful
environment, and the host is never touched. Final grading is delegated to the
**official SWE-bench harness** so verdicts are bit-identical to the leaderboard.

The two automation directories share `swe-bench/swe_bench_utils/` for the
overlay builder, container plumbing, prompt/record loaders, and the harness
grader. Only the agent CLI (npm package, binary, env vars) differs.

---

## Architecture overview

For each bug instance, the runner does the following:

```
┌───── HOST ───────────────────────────────────────────────────────────┐
│  1. build_overlay()                                                  │
│        pulls   swebench/sweb.eval.x86_64.<munged-id>:v2              │
│        builds  qwen-eval/<munged-id>:latest (base + Node 20 +        │
│                @qwen-code/qwen-code 0.0.11)                          │
│                                                                      │
│  2. DockerContainer.start()                                          │
│        docker run -d -w /testbed                                     │
│           -v <workspace>/<id>/agent_logs:/agent_logs                 │
│           qwen-eval/<id>  sleep <duration>                           │
│                                                                      │
│  3. setup_container()                                                │
│        apply test_patch (commit it as HEAD)                          │
│        write /testbed/AGENT.md, /testbed/.swebench/{problem_         │
│        statement, FAIL_TO_PASS, PASS_TO_PASS, test_cmd, ...}         │
│        install /testbed/run_failing_tests.sh, run_all_tests.sh       │
│                                                                      │
│  4. docker exec qwen --yolo --telemetry-outfile /agent_logs/...      │
│                       -p "Read and execute AGENT.md"                 │
│                       > /agent_logs/qwen-trajectory-<ts>.json        │
│        OPENAI_API_KEY / OPENAI_BASE_URL / OPENAI_MODEL injected via  │
│        `docker exec -e`. qwen-code uses the OpenAI-compatible API,   │
│        pointed at OpenRouter for qwen3-coder-flash.                  │
│        Raw stdout → trajectory-<ts>.json (final chat output)         │
│        Tool trace → telemetry-<ts>.json (OTel records)               │
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
| Agent CLI | `@qwen-code/qwen-code` 0.0.11 (npm) |
| Model | `qwen3-coder-flash` |
| API endpoint | `https://openrouter.ai/api/v1` (OpenRouter, OpenAI-compatible) |
| Auth env var | `OPENROUTER_API_KEY` (preferred) or `OPENAI_API_KEY` |
| Inside-container env | `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `OPENAI_MODEL` |

qwen-code is a fork of gemini-cli that targets any OpenAI-compatible endpoint.
We inject the three `OPENAI_*` env vars via `docker exec -e` so no `.env` ever
needs to leak into the container.

---

## Prerequisites

- Docker Desktop running (`docker ps` should succeed).
- ~30 GB free in Docker Desktop's disk image.
- A `.env` file in this directory containing the API key:
  ```
  OPENROUTER_API_KEY=your-openrouter-key
  ```
  (or `export OPENROUTER_API_KEY=...` in your shell.)
- The 32-bug bug list at
  `swe-bench/swe_bench_verified/multihunk_bugs_swe_bench_verified_32.json`
  and the SWE-bench Verified records at
  `swe-bench/swe_bench_verified/swe_bench.jsonl` (already in repo).
- A Python environment with `swebench` installed:
  ```bash
  conda env create -f swe-bench/environment.yml
  conda activate swe-bench-eval
  ```
- **Node.js / npm / qwen-code on the host: not required.** Everything the
  agent needs is installed inside the per-instance Docker image.

---

## Usage

### First-time / single-bug debug run

```bash
cd swe-bench/qwen-cli-automation
python3 automated_qwen_code.py --only astropy__astropy-13033 --duration-min 30 --keep-container
```

`--keep-container` leaves the container running so you can
`docker exec -it <name> bash -l` and poke around.

### Full batch (all 32 bugs)

```bash
cd swe-bench/qwen-cli-automation
python3 automated_qwen_code.py
```

### Useful flags

| Flag | Default | Purpose |
|------|---------|---------|
| `--only <id>...` | all 32 | Process only a subset of instance IDs |
| `--start-from <id>` | first | Resume from a specific instance (inclusive) |
| `--duration-min <n>` | 30 | Per-bug agent timeout in minutes |
| `--model <name>` | `qwen3-coder-flash` | Model name passed to the OpenAI-compatible endpoint |
| `--openai-base-url <url>` | `https://openrouter.ai/api/v1` | Switch endpoints (e.g. local vLLM) |
| `--qwen-version <spec>` | `0.0.11` | npm spec for `@qwen-code/qwen-code` |
| `--node-major <n>` | `20` | Node.js major version baked into the overlay |
| `--image-base <repo>` | `swebench/sweb.eval.x86_64` | DockerHub (immutable `:v2`) |
| `--image-tag <tag>` | `v2` | Tag on the instance image registry |
| `--keep-container` | off | Leave container running after each bug (debugging) |
| `--no-build` | off | Skip overlay build; require pre-built images |
| `--results-tag <tag>` | `qwen` | Tag the results CSV (`test_results_model_<tag>.csv`) |
| `--run-id-suffix <tag>` | `run1` | Tag passed to swebench's `run_evaluation` as `run_id` |

### Resuming after an interrupted run

`config/processed_qwen.json` lists already-completed instance IDs. Re-running
picks up where it left off. To force re-processing a bug, remove its entry.

---

## Output layout

```
qwen-cli-automation/
├── workspace_docker/<instance_id>/
│   ├── agent_logs/                            # bind-mounted into container
│   │   ├── qwen-trajectory-<ts>.json          # raw chat output
│   │   └── qwen-telemetry-<ts>.json           # ordered tool-call trace (OTel)
│   └── logs/
│       ├── run-<ts>.log                       # human-readable Qwen console
│       ├── qwen-trajectory-<ts>.json          # mirror of agent_logs
│       ├── qwen-telemetry-<ts>.json           # mirror of agent_logs
│       ├── patch-<ts>.diff                    # final patch (git diff HEAD)
│       ├── swebench_report.json               # canonical leaderboard verdict
│       ├── swebench_eval.sh                   # exact command swebench ran
│       ├── swebench_test_output.txt           # raw output from grader's run
│       └── swebench_grader/                   # full nested swebench tree
├── results/test_results_model_qwen.csv        # per-bug pass/fail results
├── config/processed_qwen.json                 # progress tracking
└── image_manifest.json                        # base + overlay digests
```

### Reading the trajectory + telemetry

**`qwen-trajectory-<ts>.json`** — raw stdout from the qwen CLI session
(captured via `> /agent_logs/<file>`). qwen-code 0.0.11 does not implement
gemini-cli's `--output-format json`, so this file is plain chat text rather
than a structured `{response, stats}` object. Useful for the agent's final
message; for the ordered tool-call sequence, parse the telemetry file.

**`qwen-telemetry-<ts>.json`** — concatenated OpenTelemetry records, one
per event, emitted by `--telemetry --telemetry-target=local
--telemetry-outfile=...`. Each `qwen_code.tool_call` (or `gemini_cli.tool_call`
on older builds) event carries `function_name`, `function_args`, `success`,
`duration_ms`, and `event.timestamp`. This is the structured ordered
tool-call sequence used by the trajectory analysis (Figures 9–10).

---

## What runs on the host vs inside the container

| Runs on host | Runs inside the agent container | Runs inside the swebench grader container |
|--------------|--------------------------------|------------------------------------------|
| Reading the bug list / records | `git apply` of test_patch | `git apply` of model_patch |
| Building overlay images | Writing AGENT.md, scripts, .swebench/* | `eval.sh` (canonical test_cmd run) |
| `docker run` / `docker exec` | Qwen Code agent loop (`qwen --yolo`) | Producing report.json |
| Writing CSVs / patches / logs | All file edits + shell commands the agent issues | |
| Invoking `swebench.harness.run_evaluation` | `git diff HEAD` for the patch | |

---

## Troubleshooting

**`401 Unauthorized` from OpenRouter** — `OPENROUTER_API_KEY` not picked up.
Confirm the key is in `.env` next to this README, or `export
OPENROUTER_API_KEY=...` before running. The script also accepts
`OPENAI_API_KEY`.

**`pull access denied for qwen-eval/...`** — the overlay image hasn't been
built yet. Re-run; the script builds it automatically.

**`No module named django` / `No module named pytest`** inside the container —
the `testbed` conda env didn't activate. Both runner scripts use `#!/bin/bash
-l` to source the conda init. If invoking manually, wrap with `bash -lc '...'`.

**Agent quits after only ~2 minutes** — qwen `-p` is one-shot mode like
gemini-cli. Strengthen `swe_bench_utils/prompt.md` to require a final clean
`./run_all_tests.sh` execution before declaring done.

**`InvalidBaseImagePlatform` warning on Apple Silicon** — cosmetic. SWE-bench
ships `linux/amd64` only; Docker Desktop runs them under Rosetta automatically.

**Telemetry flags rejected** — `--qwen-version 0.0.11` (the default) supports
the `--telemetry*` family inherited from gemini-cli 0.10.x. Bumping to a
qwen-code release that has dropped these flags requires updating
`_build_qwen_cmd` in `automated_qwen_code.py`.

---

## Reproducibility note

`image_manifest.json` records, for every instance run:
- `base_image` + `base_digest` (SWE-bench DockerHub instance image)
- `overlay_image` + `overlay_digest` (our Node + qwen-code overlay)
- `node_major`, `cli_npm_package`, `cli_version`

Keep this file checked in alongside the patches so reviewers can verify the
exact artifacts used.
