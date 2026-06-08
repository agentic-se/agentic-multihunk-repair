# Qwen Code Automation — MCP variant (SWE-bench)

**MCP-enabled fork** of `swe-bench/qwen-cli-automation/`. Same Docker-isolated runner for the 32 SWE-bench Verified multi-hunk bugs, *plus* an MCP layer that exposes the nine `maple_*` repository-search tools to the agent through `progctx-mcp-swe-bench/mcp_server/python_analysis_server.py`. After this directory's per-bug setup runs, qwen has structured access to find classes, methods, code patterns, class skeletons, and repo structure — instead of having to fall back to ad-hoc `grep`/`cat`.

Use this directory to A/B-compare against the vanilla `qwen-cli-automation/`: same bug set, same model, same harness; the only differences are the MCP-aware prompt (`prompt_mcp.md`) and the in-container MCP server. Results land in `test_results_model_qwen_mcp.csv` so the two runs don't collide.

The three automation directories (vanilla `qwen-cli-automation/`, this MCP variant, and `gemini-cli-automation/`) share `swe-bench/swe_bench_utils/` for the overlay builder, container plumbing, prompt/record loaders, and the harness grader. Only the agent CLI (npm package, binary, env vars) and — for this variant — the MCP setup differ.

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
│        write /testbed/AGENT.md (rendered from prompt_mcp.md so the   │
│              agent gets the MAPLE tool-list section)                 │
│        write /testbed/.swebench/{problem_statement, FAIL_TO_PASS,    │
│              PASS_TO_PASS, test_cmd, ...}                            │
│        install /testbed/run_failing_tests.sh, run_all_tests.sh       │
│                                                                      │
│  3b. _setup_mcp_in_container()  ── only in this MCP variant ──       │
│        mkdir -p /opt/progctx-mcp-swe-bench                           │
│        cp_in progctx-mcp-swe-bench/{context, mcp_server}             │
│        conda create -y -n mcp-e2e python=3.11                        │
│        conda run -n mcp-e2e pip install 'mcp[fastmcp]' fastmcp       │
│        write /root/.qwen/settings.json — STDIO config that spawns    │
│              python_analysis_server.py against /testbed              │
│                                                                      │
│  4. docker exec qwen --yolo --telemetry-outfile /agent_logs/...      │
│                       -p "Read and execute AGENT.md"                 │
│                       > /agent_logs/qwen-trajectory-<ts>.json        │
│        qwen reads ~/.qwen/settings.json → spawns the MCP server      │
│        subprocess → the maple_* tools become available alongside     │
│        qwen's built-in tools                                         │
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

## MCP tool names look weird — here's why

The nine MAPLE tools appear in qwen's registry as

```
mcp__python-analysis-server__maple_find_class
mcp__python-analysis-server__maple_find_class_in_file
... etc.
```

…and `prompt_mcp.md` calls them by those exact names. The mangling is **not ours** — it's qwen-code's MCP-import convention. Here's the data flow:

| Layer | Tool name |
|---|---|
| MCP server (`progctx-mcp-swe-bench/mcp_server/python_analysis_server.py`) declares | `maple_find_class` (the `@mcp.tool()` decorator name) |
| `_setup_mcp_in_container` writes the server entry to `/root/.qwen/settings.json` with key | `"python-analysis-server"` |
| qwen-code 0.0.11 imports MCP tools into its registry, prefixing each with `mcp__<server-key>__` to avoid collisions with native tools (`list_directory`, `edit`, …) | `mcp__python-analysis-server__maple_find_class` |
| Function definitions sent to the model use the prefixed names; the model calls them back by those exact names. | same |

So if `prompt_mcp.md` lists the tools as bare `maple_find_class`, the model dutifully emits `maple_find_class` as the function name — and qwen-code's native-tool handler fails to find it with

```
Tool "maple_find_class" not found in registry.
Did you mean one of: "list_directory", "grep_search", "todo_write"?
```

We discovered this empirically when the first qwen-MCP run on `astropy__astropy-13033` produced **0 successful `maple_*` calls** despite a working MCP server. Fix: name the tools in `prompt_mcp.md` exactly as qwen registers them. We're stuck with the `mcp__python-analysis-server__` prefix unless we either (a) rename the server key in `_setup_mcp_in_container`, (b) drop the `maple_` prefix from the `@mcp.tool()` decorator names in `python_analysis_server.py`, or (c) patch qwen-code to skip the namespacing. (a) and (b) are the cleanest follow-ups; (c) is a deep hack.

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
cd swe-bench/qwen-cli-automation-mcp
python3 automated_qwen_code.py --only astropy__astropy-13033 --duration-min 30 --keep-container
```

`--keep-container` leaves the container running so you can
`docker exec -it <name> bash -l` and poke around.

### Full batch (all 32 bugs)

```bash
cd swe-bench/qwen-cli-automation-mcp
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
| `--base-prompt <path>` | `./prompt_mcp.md` | Path to the prompt template. The MCP variant defaults to the local MCP-aware prompt; override to test a different prompt. |
| `--results-tag <tag>` | `qwen_mcp` | Tag the results CSV (`test_results_model_<tag>.csv`). MCP variant defaults to `qwen_mcp` so it doesn't collide with vanilla's `qwen`. |
| `--processed-json <path>` | `./config/processed_qwen_mcp.json` | Progress-tracking file. Separate from vanilla's `processed_qwen.json` for the same reason. |
| `--run-id-suffix <tag>` | `run1` | Tag passed to swebench's `run_evaluation` as `run_id` |

### Resuming after an interrupted run

`config/processed_qwen_mcp.json` lists already-completed instance IDs for this
variant. Re-running picks up where it left off. To force re-processing a bug,
remove its entry. The file is independent of the vanilla
`qwen-cli-automation/config/processed_qwen.json`, so the two variants don't
shadow each other.

---

## Output layout

```
qwen-cli-automation-mcp/
├── prompt_mcp.md                              # MCP-aware prompt (vanilla + MAPLE block)
├── workspace_docker/<instance_id>/
│   ├── agent_logs/                            # bind-mounted into container
│   │   ├── qwen-trajectory-<ts>.json          # raw chat output
│   │   └── qwen-telemetry-<ts>.json           # ordered tool-call trace (OTel)
│   └── logs/
│       ├── run-<ts>.log                       # human-readable Qwen console
│       ├── qwen-trajectory-<ts>.json          # mirror of agent_logs
│       ├── qwen-telemetry-<ts>.json           # mirror of agent_logs (look here for maple_* calls)
│       ├── patch-<ts>.diff                    # final patch (git diff HEAD)
│       ├── swebench_report.json               # canonical leaderboard verdict
│       ├── swebench_eval.sh                   # exact command swebench ran
│       ├── swebench_test_output.txt           # raw output from grader's run
│       └── swebench_grader/                   # full nested swebench tree
├── results/test_results_model_qwen_mcp.csv    # per-bug pass/fail results (separate from vanilla)
├── config/processed_qwen_mcp.json             # progress tracking (separate from vanilla)
└── image_manifest.json                        # base + overlay digests
```

Inside each running container, the MCP variant additionally creates:

```
/opt/progctx-mcp-swe-bench/{context, mcp_server}    # cp_in'd from this repo
/opt/miniconda3/envs/mcp-e2e/                       # Python 3.11 + mcp[fastmcp] + fastmcp
/root/.qwen/settings.json                           # STDIO MCP config pointing at the server
```

These are inside the container — they live and die with the container, not on the host.

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

**Spotting MCP usage:** `maple_*` tool calls (e.g. `maple_find_class`,
`maple_repo_structure`) appear in the telemetry as `qwen_code.tool_call`
events with `function_name` starting with `maple_`. If the agent never
invoked any `maple_*` tool, either the MCP server failed to start (check the
console log for `MCP setup:` errors) or the agent didn't reach for the new
tools (a prompt-tuning question, not a wiring question).

---

## What runs on the host vs inside the container

| Runs on host | Runs inside the agent container | Runs inside the swebench grader container |
|--------------|--------------------------------|------------------------------------------|
| Reading the bug list / records | `git apply` of test_patch | `git apply` of model_patch |
| Building overlay images | Writing AGENT.md (from `prompt_mcp.md`), scripts, .swebench/* | `eval.sh` (canonical test_cmd run) |
| `docker run` / `docker exec` | Qwen Code agent loop (`qwen --yolo`) | Producing report.json |
| Writing CSVs / patches / logs | `_setup_mcp_in_container` plumbing (this variant only): conda env, pip install `mcp[fastmcp]`, write `~/.qwen/settings.json` | |
| Invoking `swebench.harness.run_evaluation` | The MCP server itself (`python_analysis_server.py`, spawned by qwen via STDIO) | |
|  | All file edits + shell commands the agent issues + `maple_*` tool calls | |
|  | `git diff HEAD` for the patch | |

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

**Console log shows `MCP setup: conda create … failed` (or `pip install … failed`)**
— the `_setup_mcp_in_container` helper raises with the tail of the offending
command's output. Most common causes: testbed image's miniconda is too old to
create a 3.11 env, or the container had no network access at install time.
Re-run; if it keeps failing, run `--keep-container` and inspect from inside
(`conda env list`, `conda run -n mcp-e2e pip list`).

**Agent never calls any `maple_*` tool** — three possibilities, in order of likelihood:
1. *Prompt names don't match registered names.* qwen-code prefixes every MCP tool
   with `mcp__<server-key>__`. The telemetry will show
   `event.name=qwen-code.tool_call, function_name=maple_find_class, success=False,
   error="Tool ... not found in registry", tool_type=native`. Make sure
   `prompt_mcp.md` uses the prefixed names. See the
   "MCP tool names look weird" section above for the full mechanism.
2. *Server didn't start.* `docker exec <name> cat /root/.qwen/settings.json` should
   show the STDIO config, and `docker exec <name> conda run -n mcp-e2e python -c "import mcp.server.fastmcp"`
   should succeed. If either fails, the in-container MCP setup is broken. Also
   check `qwen-code.config` in the telemetry — `mcp_servers_count` should be 1 and
   `mcp_tools_count` should be 9.
3. *Server started but agent ignored the tools.* Look at the trajectory: did the
   agent reason about the MAPLE section in the prompt at all? If not, the
   prompt may need to be stronger ("you must use Maple tools before grep"
   rather than "use Maple proactively"). This is a prompt-tuning concern, not
   a wiring concern.

---

## Reproducibility note

`image_manifest.json` records, for every instance run:
- `base_image` + `base_digest` (SWE-bench DockerHub instance image)
- `overlay_image` + `overlay_digest` (our Node + qwen-code overlay)
- `node_major`, `cli_npm_package`, `cli_version`

**MCP-specific caveat:** `_setup_mcp_in_container` currently does
`pip install --quiet 'mcp[fastmcp]' fastmcp` *without version pins*, so two
runs a month apart could install different MCP SDK versions and produce
slightly different agent behavior. If you need bit-reproducible MCP code
across runs (e.g. for a paper-grade replication), pin the versions in
`automated_qwen_code.py` — e.g. `'mcp[fastmcp]==1.6.0' 'fastmcp==2.3.5'` —
and record those versions alongside the manifest.

Keep `image_manifest.json` checked in alongside the patches so reviewers can
verify the exact artifacts used.
