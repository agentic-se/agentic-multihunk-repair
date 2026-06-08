# Hunk-SWE

**Hunk-SWE** is the benchmark subset and evaluation harness used to study how
agentic coding CLIs repair *multi-hunk* bugs. It curates the **32 multi-hunk
bugs** from [SWE-bench Verified](https://www.swebench.com/) and runs four
agents against them inside per-instance Docker containers, grading every fix
with the **official SWE-bench harness** so verdicts are bit-identical to the
leaderboard.

A bug is *multi-hunk* when its gold patch edits more than one file, or edits a
single file in multiple disjoint regions (multiple `@@` hunk headers) — the
cases where a fix cannot be localized to one contiguous edit.

## What's here

```
hunk-swe/
├── environment.yml                 conda env `swe-bench-eval` (swebench harness + deps)
│
├── claude-cli-automation/          Claude Code runner
├── codex-cli-automation/           OpenAI Codex runner
├── gemini-cli-automation/          Gemini CLI runner
├── gemini-cli-automation-mcp/        └─ + MCP code-search layer
├── qwen-cli-automation/            Qwen Code runner
├── qwen-cli-automation-mcp/          └─ + MCP code-search layer
│
├── swe_bench_utils/                shared harness: Docker isolation, setup, grader
├── swe_bench_verified/             the 32-bug set, issue labels, classification
├── swe_hunk_divergence/            hunk-divergence metric (ported from Defects4J)
├── swe_proximity_class/            spatial proximity classification (ported from Hunk4J)
└── scripts/                        per-agent metrics, figure data, command analysis
```

## Agent runners

Each runner repairs every bug in **its own per-instance container** (correct
Python version, conda env, and pinned dependencies pre-installed) so the agent
sees real test traces from a faithful environment while the host stays clean.
The runners share `swe_bench_utils/` for the overlay builder, container
plumbing, prompt/record loaders, and the harness grader; only the agent CLI
(npm package, binary, env vars, prompt-file convention) differs.

| Directory | Agent CLI |
|-----------|-----------|
| `claude-cli-automation/` | Claude Code (`@anthropic-ai/claude-code`) |
| `codex-cli-automation/` | OpenAI Codex |
| `gemini-cli-automation/` | Gemini CLI |
| `qwen-cli-automation/` | Qwen Code |

The `*-mcp/` variants add an MCP layer (see `../progctx-mcp-swe-bench/`) that
exposes the nine `maple_*` repository-search tools, giving the agent structured
code search instead of ad-hoc `grep`/`cat`. They use the same bug set, model,
and harness, so results can be A/B-compared against the vanilla runners.

Per-bug lifecycle (driven by each runner):

```
build_overlay()      pull base image, build <agent>-eval/<id>:latest (base + CLI)
container.start()    long-lived container, /testbed cwd, /agent_logs bind mount
setup_container()    apply test_patch (committed as HEAD), AGENT.md, .swebench/*, test runners
docker exec <cli>    agent repairs the bug inside the container; trajectory → /agent_logs
docker exec git diff agent's fix captured as model_patch
grade_instance()     swebench.harness.run_evaluation → report.json → CSV verdict
container.cleanup()
```

## Dataset & analysis

- **`swe_bench_verified/`** — the source dataset, the multi-hunk classifier, the
  curated 32-bug set (`multihunk_bugs_swe_bench_verified_32.json`), and GitHub
  issue labels used to keep only genuine bugs.
- **`swe_hunk_divergence/`** — computes per-bug *hunk divergence*
  (`ln(n) · mean pairwise divergence` over lexical / AST / file distances),
  ported from the Defects4J pipeline to Python's `ast`.
- **`swe_proximity_class/`** — classifies each bug's hunks into spatial
  proximity classes — **Nucleus** (same function), **Cluster** (same file),
  **Orbit** (same module), **Sprawl** / **Fragment** (across modules) — ported
  from the Hunk4J (Java) pipeline.

## Metrics

`scripts/` holds per-agent metric pipelines (`metrics-claude/`, `metrics-codex/`,
`metrics-gemini/`, `metrics-qwen/`): edit accuracy, localization and repair
ability, tool-call sequences, shell-command categorization, token/duration, and
hunk-divergence-vs-proximity breakdowns. `scripts/data/` contains the raw
per-instance JSON underlying the paper's figures.

## Setup

```bash
# from the repository root
conda env create -f hunk-swe/environment.yml
conda activate swe-bench-eval
```

Then see each runner's `README.md` (and the qwen runners' `GETTING_STARTED.md`)
for agent-specific authentication and how to launch a run. Credentials are read
from the environment or a local `.env` at runtime and are never committed.
