# swe_bench_utils

Shared Python utilities for the SWE-bench automation scripts. Provides the
**per-instance Docker isolation** primitives used by the agent runners — so
each bug is repaired inside a container with the right Python version,
conda env, and pinned dependencies, while the host stays clean.

## Modules

| Module | Purpose |
|--------|---------|
| `docker_env.py` | `DockerContainer` (start / exec / cp_in / write_text / cleanup) and image-name helpers (`instance_image_name`, `overlay_image_name`). Uses DockerHub `swebench/sweb.eval.x86_64.<id>:v2` (immutable). Handles SWE-bench's `__` → `_1776_` munging for DockerHub. |
| `Dockerfile.overlay` | Build recipe: `FROM <base>` + Node.js 20 + Gemini CLI `0.10.0`. Lets the agent CLI run *inside* the per-instance container. |
| `build_overlay.py` | Builds (or reuses) the overlay image per instance. Writes `image_manifest.json` capturing base + overlay digests for TOSEM reproducibility. Pinned defaults: `DEFAULT_GEMINI_VERSION = "0.10.0"`, `DEFAULT_NODE_MAJOR = "20"`. |
| `container_setup.py` | Seeds a running container with `test_patch` (committed as HEAD), `AGENT.md`, `/testbed/.swebench/` metadata, and `run_failing_tests.sh` / `run_all_tests.sh`. Resolves the canonical per-project test invocation via `swebench.harness.test_spec.python.MAP_REPO_VERSION_TO_SPECS`. |
| `grader.py` | Wraps `swebench.harness.run_evaluation` as a subprocess. Writes a single-entry `predictions.jsonl`, invokes the official harness, parses `report.json`, and copies key artifacts (`report.json`, `eval.sh`, `test_output.txt`) up to the per-bug `logs/`. Returns a `GradingResult` (resolved / fail_to_pass_resolved / no_regressions / failed_tests). |
| `config.py` | Loads bug metadata from `swe_bench_verified/multihunk_bugs_swe_bench_verified_32.json` and `swe_bench.jsonl`. `render_prompt()` fills the prompt template with `problem_statement`, `hints_text`, and `FAIL_TO_PASS` test lists. |
| `utils.py` | Tiny host-side helpers: `ts()` (timestamp for filenames) and `ensure_dir()`. |
| `prompt.md` | Agent prompt template. Tells the agent it's at `/testbed` with the conda env already active, and points at the two test runner scripts. |
| `scripts/run_failing_tests.sh` | Runs the canonical SWE-bench test command, then post-filters the log to report ONLY the FAIL_TO_PASS subset (`[PASS] / [FAIL] / [MISSING]` summary). `#!/bin/bash -l` activates the `testbed` conda env. |
| `scripts/run_all_tests.sh` | Runs the same canonical command and saves the full log. Used for post-fix regression checking. `#!/bin/bash -l` for conda. |

## Per-bug lifecycle (driven by the agent runner)

```
build_overlay()                 ← pulls base, builds <prefix>/<id>:latest
DockerContainer.start()         ← long-lived sleep loop, /testbed cwd, /agent_logs bind mount
setup_container()               ← test_patch (committed), AGENT.md, .swebench/*, run_*.sh
docker exec gemini ...          ← agent runs INSIDE the container; trajectory + telemetry → /agent_logs
docker exec git diff HEAD       ← capture only the agent's bug fix (HEAD = test_patch commit)
grade_instance()                ← swebench.harness.run_evaluation in its own grading container
DockerContainer.cleanup()
```

## How verdicts are produced

We delegate **all** grading to `swebench.harness.run_evaluation`. The harness
builds its own per-instance grading container (cached at `--cache_level
instance`), applies our `model_patch` on top of the base commit, runs the
canonical `eval.sh`, and writes `report.json`. We parse `report.json` into a
`GradingResult` and translate it into our CSV row. No baseline pass on our
side — the harness handles environmental drift internally, and any handrolled
alternative would either diverge from the leaderboard or duplicate what's
already there.

## Import pattern

Each agent runner adds `swe-bench/` to `sys.path`, then imports:

```python
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from swe_bench_utils.build_overlay import (
    DEFAULT_GEMINI_VERSION, DEFAULT_NODE_MAJOR,
    build_overlay, collect_manifest_entry, write_image_manifest,
)
from swe_bench_utils.config import (
    DEFAULT_PROMPT, get_fail_to_pass, get_pass_to_pass,
    load_multihunk_bugs, load_swebench_records, render_prompt,
)
from swe_bench_utils.container_setup import setup_container
from swe_bench_utils.docker_env import (
    DEFAULT_IMAGE_BASE, DEFAULT_IMAGE_TAG,
    DockerContainer, instance_image_name, overlay_image_name,
)
from swe_bench_utils.grader import grade_instance
from swe_bench_utils.utils import ensure_dir, ts
```

Requires `swebench>=4.1.0` (see `swe-bench/environment.yml`).
