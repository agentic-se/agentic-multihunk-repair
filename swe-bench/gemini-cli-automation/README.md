# Gemini CLI Automation (SWE-bench)

Docker-isolated Gemini CLI runner for the 32 SWE-bench Verified multi-hunk bugs.
Each bug is repaired inside its own per-instance container (with the right
Python version, conda env, and pinned dependencies pre-installed) so the agent
sees real test traces from a faithful environment, and the host is never
touched. Final grading is delegated to the **official SWE-bench harness** so
verdicts are bit-identical to the leaderboard.

For step-by-step manual reproduction (audit each step the script performs), see
[`MANUAL_VERIFICATION.md`](MANUAL_VERIFICATION.md).

---

## Architecture overview

For each bug instance, the runner does the following:

```
┌───── HOST ───────────────────────────────────────────────────────────┐
│  1. build_overlay()                                                  │
│        pulls   swebench/sweb.eval.x86_64.<munged-id>:v2              │
│        builds  gemini-eval/<munged-id>:latest (base + Node 20 +      │
│                Gemini CLI 0.10.0)                                    │
│                                                                      │
│  2. DockerContainer.start()                                          │
│        docker run -d -w /testbed                                     │
│           -v <workspace>/<id>/agent_logs:/agent_logs                 │
│           gemini-eval/<id>  sleep <duration>                         │
│                                                                      │
│  3. setup_container()                                                │
│        apply test_patch (commit it as HEAD)                          │
│        write /testbed/AGENT.md, /testbed/.swebench/{problem_         │
│        statement, FAIL_TO_PASS, PASS_TO_PASS, test_cmd, ...}         │
│        install /testbed/run_failing_tests.sh, run_all_tests.sh       │
│                                                                      │
│  4. docker exec gemini --yolo --output-format json                   │
│                       --telemetry-outfile /agent_logs/...            │
│                       -p "Read and execute AGENT.md"                 │
│        agent runs INSIDE the container; tools target /testbed;       │
│        session summary → trajectory.json,                            │
│        ordered tool-call trace → telemetry.json (OTel records)       │
│                                                                      │
│  5. docker exec git diff --binary HEAD   → patch-<ts>.diff           │
│        captures only the agent's bug fix (HEAD = test_patch commit)  │
│                                                                      │
│  6. grade_instance() → swebench.harness.run_evaluation               │
│        SWE-bench builds its OWN container, applies the predicted     │
│        patch, runs the canonical eval.sh, writes report.json.        │
│        We copy report.json + eval.sh + test_output.txt up to logs/.  │
│                                                                      │
│  7. docker rm -f <container>                                         │
└──────────────────────────────────────────────────────────────────────┘
```

Steps 4–5 happen inside the agent's container, so the agent's tools and our
patch capture share an identical environment. Step 6 happens in a fresh
container that the official SWE-bench harness manages itself — that's how we
guarantee leaderboard-comparable verdicts.

---

## How verdicts are computed

We delegate **all** grading to `swebench.harness.run_evaluation`. The harness:

- Builds its own per-instance grading container (cached at `--cache_level instance`).
- Applies our `model_patch` on top of the original `base_commit`.
- Runs the canonical `eval.sh` (which executes `test_cmd` over the test files
  touched by `test_patch`).
- Computes verdicts against `FAIL_TO_PASS` and `PASS_TO_PASS` from the dataset.

No baseline pass needed in our code: the harness handles environmental drift
internally by running the canonical `test_cmd` in a freshly-built image and
comparing only the relevant test names. Whatever we'd hand-roll would either
diverge from the leaderboard or duplicate what the harness already does.

---

## Prerequisites

- **Docker Desktop** running (`docker ps` should succeed).
- ~30 GB free in Docker Desktop's disk image (Settings → Resources). Each
  SWE-bench base image is ~1 GB; 32 bases + overlays + grader caches add up.
  The official DockerHub registry is used because it publishes immutable
  tags (we pin to `:v2`).
- A `.env` file in this directory containing the API key:
  ```
  GEMINI_API_KEY=your-key-here
  ```
  (or `export GEMINI_API_KEY=...` in your shell.)
- The 32-bug bug list at
  `swe-bench/swe_bench_verified/multihunk_bugs_swe_bench_verified_32.json`
  and the SWE-bench Verified records at
  `swe-bench/swe_bench_verified/swe_bench.jsonl` (already in repo).
- A Python environment with `swebench` installed. From the repo root:
  ```bash
  conda env create -f swe-bench/environment.yml
  conda activate swe-bench-eval
  ```
  Verify: `python3 -c "from swebench.harness.test_spec.python import MAP_REPO_VERSION_TO_SPECS; print('ok')"`
- **Node.js / npm / Gemini CLI on the host: not required.** Everything the
  agent needs is installed inside the per-instance Docker image. Your host
  stays clean.

**Apple Silicon note:** SWE-bench images are `linux/amd64` only and run under
Rosetta on M-series Macs. Docker logs an `InvalidBaseImagePlatform` warning;
it's cosmetic but emulation is slower than native. Plan accordingly when
budgeting `--duration-min`.

---

## Usage

### First-time / single-bug debug run

```bash
cd swe-bench/gemini-cli-automation
python3 automated_gemini_cli.py --only astropy__astropy-13033 --duration-min 30 --keep-container
```

`--keep-container` leaves the container running after the bug finishes so
you can `docker exec -it <name> bash -l` and poke around.

### Full batch (all 32 bugs)

```bash
cd swe-bench/gemini-cli-automation
python3 automated_gemini_cli.py
```

That's the entire command. The script iterates the 32 instance IDs from
`multihunk_bugs_swe_bench_verified_32.json`, builds overlays the first
time it sees each one, and writes everything to `workspace_docker/`,
`results/`, and `image_manifest.json`.

### Useful flags

| Flag | Default | Purpose |
|------|---------|---------|
| `--only <id>...` | all 32 | Process only a subset of instance IDs |
| `--start-from <id>` | first | Resume from a specific instance (inclusive) |
| `--duration-min <n>` | 30 | Per-bug agent timeout in minutes |
| `--model <name>` | `gemini-2.5-flash` | Gemini model |
| `--gemini-version <spec>` | `0.10.0` | npm spec for `@google/gemini-cli` (matches Defects4J runs) |
| `--node-major <n>` | `20` | Node.js major version baked into the overlay |
| `--image-base <repo>` | `swebench/sweb.eval.x86_64` (DockerHub, immutable) | Override the SWE-bench instance image registry |
| `--image-tag <tag>` | `v2` | Tag on the instance image registry |
| `--keep-container` | off | Leave the container running after each bug (debugging) |
| `--no-build` | off | Skip overlay build; require pre-built images |
| `--results-tag <tag>` | `gemini` | Tag the results CSV (`test_results_model_<tag>.csv`) |
| `--run-id-suffix <tag>` | `run1` | Tag passed to swebench's `run_evaluation` as `run_id` |

### Resuming after an interrupted run

The script maintains `config/processed_gemini.json` listing already-completed
instance IDs. Re-running picks up where it left off automatically. To force
re-processing a bug, remove its entry from that file.

---

## Output layout

```
gemini-cli-automation/
├── workspace_docker/<instance_id>/
│   ├── agent_logs/                            # bind-mounted into container
│   │   ├── gemini-trajectory-<ts>.json        # session summary (stats)
│   │   └── gemini-telemetry-<ts>.json         # ordered tool-call trace (OTel)
│   └── logs/
│       ├── run-<ts>.log                       # human-readable Gemini console
│       ├── gemini-trajectory-<ts>.json        # mirror of agent_logs
│       ├── gemini-telemetry-<ts>.json         # mirror of agent_logs
│       ├── patch-<ts>.diff                    # final patch (git diff HEAD)
│       ├── swebench_report.json               # canonical leaderboard verdict
│       ├── swebench_eval.sh                   # exact command swebench ran
│       ├── swebench_test_output.txt           # raw output from grader's run
│       └── swebench_grader/                   # full nested swebench tree
│           └── logs/run_evaluation/.../report.json
├── results/test_results_model_gemini.csv      # per-bug pass/fail results
├── config/processed_gemini.json               # progress tracking
└── image_manifest.json                        # base + overlay digests for reproducibility
```

### Reading the results CSV

| Column | Meaning |
|--------|---------|
| `instance_id` | SWE-bench instance ID |
| `resolved` | `Yes` if SWE-bench's canonical verdict is "bug fixed" (= leaderboard pass) |
| `fail_to_pass_resolved` | `Yes` if all FAIL_TO_PASS tests now pass |
| `no_regressions` | `Yes` if no PASS_TO_PASS tests fail |
| `failed_tests` | Failing FAIL_TO_PASS tests + regressing PASS_TO_PASS tests |
| `duration_s` | Total wall-clock time per bug (overlay + agent + grading) |
| `error` | Set if any step before grading raised |

### Reading the trajectory + telemetry

**`gemini-trajectory-<ts>.json`** — one final JSON object emitted by
`gemini --output-format json`. Contains `response` (the agent's final message)
and `stats` (per-tool counts, durations, success/fail tallies). Useful for
session-level summary; **not** ordered.

**`gemini-telemetry-<ts>.json`** — concatenated OpenTelemetry records
(pretty-printed JSON objects, one per event) emitted by
`--telemetry --telemetry-target=local --telemetry-outfile=...`. Each
`gemini_cli.tool_call` event carries `function_name`, `function_args`,
`success`, `duration_ms`, and `event.timestamp` — sufficient to reconstruct
the **ordered** tool-call sequence. This is what the trajectory analysis
(Figures 9–10 in the paper) consumes.

To parse telemetry into an ordered sequence:

```python
import json
buf = open("gemini-telemetry-<ts>.json").read()
d, i, recs = json.JSONDecoder(), 0, []
while i < len(buf):
    while i < len(buf) and buf[i] in " \n\r\t": i += 1
    if i >= len(buf): break
    obj, j = d.raw_decode(buf, i); i = j; recs.append(obj)
calls = [
    (r["attributes"]["event.timestamp"],
     r["attributes"]["function_name"],
     r["attributes"]["function_args"],
     r["attributes"]["success"])
    for r in recs
    if r.get("attributes", {}).get("event.name") == "gemini_cli.tool_call"
]
calls.sort()
```

---

## What runs on the host vs inside the container

| Runs on host | Runs inside the agent container | Runs inside the swebench grader container |
|--------------|--------------------------------|------------------------------------------|
| Reading the bug list / records | `git apply` of test_patch | `git apply` of model_patch |
| Building overlay images | Writing AGENT.md, scripts, .swebench/* | `eval.sh` (canonical test_cmd run) |
| `docker run` / `docker exec` | Gemini CLI agent loop (`gemini --yolo`) | Producing report.json |
| Writing CSVs / patches / logs | All file edits + shell commands the agent issues | |
| Invoking `swebench.harness.run_evaluation` | `git diff HEAD` for the patch | |

The agent never sees the host filesystem. The host never gets Node, npm,
Gemini, or any Python deps installed on it. The grader runs in its own
isolated container that swebench manages.

---

## Troubleshooting

**`pull access denied for gemini-eval/...`** — the overlay image hasn't
been built yet. Re-run; the script builds it automatically. If you also
passed `--platform=linux/amd64` to a manual `docker run`, drop that flag —
the overlay's image manifest may not match.

**`No module named django` / `No module named pytest`** inside the container — the
`testbed` conda env didn't activate. Both `run_failing_tests.sh` and
`run_all_tests.sh` use `#!/bin/bash -l` to source the conda init. If you
invoke any test command manually via `docker exec`, wrap it: `bash -lc '...'`.

**`json.decoder.JSONDecodeError` from `swebench.harness.run_evaluation`** —
`predictions.jsonl` was pretty-printed. Use `jq -nc` (compact mode) — one JSON
object per line.

**Agent quits after only ~2 minutes** — Gemini CLI's `-p` is one-shot mode.
The agent stops as soon as it produces an assistant message with no tool
calls. If grading shows the bug isn't fully fixed, strengthen
`swe_bench_utils/prompt.md` to require a final clean
`./run_all_tests.sh` execution before declaring done.

**`InvalidBaseImagePlatform` warning on Apple Silicon** — cosmetic. SWE-bench
ships `linux/amd64` only; Docker Desktop runs them under Rosetta automatically.

**Gemini telemetry flags rejected** — only `--gemini-version 0.10.0` (the
default) supports the `--telemetry*` family. Versions `0.17+` removed them
in favor of `settings.json` config (PR #11318, Oct 2025). Don't bump the
version pin without updating `_build_gemini_cmd` in
`automated_gemini_cli.py`.

---

## Reproducibility note

`image_manifest.json` records, for every instance run:
- `base_image` + `base_digest` (SWE-bench DockerHub instance image)
- `overlay_image` + `overlay_digest` (our Node + Gemini overlay)
- `node_major`, `gemini_version`

This is the reproducibility receipt for the TOSEM revision (item #1 in the
revision plan: "Model versions/APIs for reproducibility"). Keep this file
checked in alongside the patches so reviewers can verify the exact
artifacts used.

The DockerHub registry is used because it publishes immutable tags
(`:v2`). If you ever switch with `--image-base`, also pin `--image-tag`
to a digest you've recorded in the manifest.
