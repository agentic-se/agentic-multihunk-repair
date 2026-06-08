# progctx-mcp-swe-bench

Python / SWE-bench counterpart to `progctx-mcp-d4j`. The search core in `context/search/` indexes a Python repository and exposes search methods; the `mcp_server/` directory wraps those methods as FastMCP tools so an agentic CLI (Claude Code, Codex, Qwen Code, Gemini CLI) can ground its repair decisions in indexed project context rather than ad-hoc `grep` / `cat`.

## Layout

```
progctx-mcp-swe-bench/
├── README.md
├── test_python_search_manager.py          (pytest suite covering all 9 APIs)
├── resources/
│   └── sample_repo/                       (test fixture indexed by the suite)
│       ├── utils.py
│       └── animals/
│           ├── mammals.py
│           └── birds.py
├── context/
│   ├── __init__.py
│   └── search/
│       ├── __init__.py
│       ├── python_search_manager.py
│       └── python_search_utils.py
└── mcp_server/
    ├── __init__.py
    ├── python_analysis_server.py          (STDIO transport)
    └── python_analysis_server_sse.py      (SSE transport on port 9900)
```

## File inventory

| File | Role |
|---|---|
| `context/search/python_search_manager.py` | `PythonSearchManager` class — indexes a Python project and exposes search methods |
| `context/search/python_search_utils.py` | `SearchResult` dataclass and AST/file helpers used by `PythonSearchManager` |
| `mcp_server/python_analysis_server.py` | FastMCP-based MCP server (STDIO transport) that wraps `PythonSearchManager` as `maple_*` tools |
| `mcp_server/python_analysis_server_sse.py` | Same MCP server over SSE transport (port 9900) |
| `test_python_search_manager.py` | Pytest suite covering all 9 search APIs against the sample-repo fixture |
| `resources/sample_repo/` | Small Python project (3 classes, 8 methods, 2 top-level functions) used as the test fixture |
| `context/__init__.py`, `context/search/__init__.py`, `mcp_server/__init__.py` | Empty package markers |

## Runtime requirement

Python 3.10+ is required because the canonical type hints use PEP 604 union syntax (e.g. `tuple[str | None, str | None]`). The MCP server additionally requires the `mcp[fastmcp]` package in the runtime env.

---

## `mcp_server/` — MCP layer

Mirrors `progctx-mcp-d4j/mcp_server/`. Two transports.

### STDIO

```bash
PYTHON_PROJECT_PATH=/path/to/python/project \
  python3.11 -m progctx_mcp_swe_bench.mcp_server.python_analysis_server
```

The STDIO server initializes `PythonSearchManager` at import time, so `PYTHON_PROJECT_PATH` must be set before the module is loaded.

### SSE

```bash
python3.11 progctx-mcp-swe-bench/mcp_server/python_analysis_server_sse.py \
  --project-path /path/to/python/project
```

The SSE server listens on `http://localhost:9900/sse` and initializes `PythonSearchManager` lazily on the first tool call.

**Port collision:** d4j's SSE server also hardcodes port 9900. Running both simultaneously requires editing one of them to use a different port.

### Tools exposed (9, identical names to `progctx-mcp-d4j`)

| Tool | Wraps |
|---|---|
| `maple_find_class(class_name)` | `PythonSearchManager.search_class` |
| `maple_find_class_in_file(class_name, file_name)` | `search_class_in_file` |
| `maple_find_method(method_name)` | `search_method` |
| `maple_find_method_in_class(method_name, class_name)` | `search_method_in_class` |
| `maple_find_method_in_file(method_name, file_name)` | `search_method_in_file` |
| `maple_find_code(code_snippet)` | `search_code` |
| `maple_find_code_in_file(code_snippet, file_name)` | `search_code_in_file` |
| `maple_extract_class_skeleton(file_name)` | `extract_class_skeleton` |
| `maple_repo_structure(max_depth=100)` | `get_repo_structure` |

Each tool function wraps the underlying `PythonSearchManager` method with FastMCP `@mcp.tool()` decoration, request/response logging, and a try/except that returns a `FAILED` status string on any exception so the server never crashes from a bad tool call.

---

## `PythonSearchManager` (in `context/search/python_search_manager.py`)

```python
PythonSearchManager(project_path: str)
```

Walks `project_path`, parses every `.py` file with `ast`, and builds three indices at construction time:

- `class_index: {class_name -> [(file_path, LineRange)]}`
- `class_func_index: {class_name -> {method_name -> [(file_path, LineRange)]}}`
- `function_index: {func_name -> [(file_path, LineRange)]}`
- `parsed_files: [file_path]`

`LineRange = namedtuple("LineRange", ["start", "end"])`.
`RESULT_SHOW_LIMIT = 3` — when a search returns more than 3 hits, output collapses to a file-level summary.

### Public methods

All `search_*`, `get_repo_structure`, and `extract_class_skeleton` methods return `(tool_output: str, summary: str, found: bool)` — already shaped for tool-style consumption.

| Method | What it does |
|---|---|
| `get_class_full_snippet(class_name)` | Full source of every class with this name (up to 2 shown verbatim). |
| `search_class(class_name)` | Class signature (one line) and file location(s). Collapses to file list when results exceed 3. |
| `search_class_in_file(class_name, file_name)` | `search_class` restricted to files whose path ends with `file_name`. Returns the full class body of each match. |
| `search_method(method_name)` | Finds the function/method across the whole codebase: top-level functions plus methods inside every class. |
| `search_method_in_class(method_name, class_name)` | Function defined as a method of the named class. |
| `search_method_in_file(method_name, file_name)` | Function/method whose enclosing file path ends with `file_name`. |
| `search_code(code_str)` | Literal substring search across all indexed files. Each hit comes back with its enclosing `(class, function)` resolved from the index, plus three lines of context above and below. |
| `search_code_in_file(code_str, file_name)` | `search_code` restricted to a file. Trims a trailing `)` from the query as a legacy heuristic. |
| `retrieve_code_snippet(file_path, start_line, end_line) -> str` | Raw line-range extraction. |
| `file_line_to_class_and_func(file_path, line_no) -> (class_or_None, func_or_None)` | Reverse lookup: given a `(file, line)`, returns the enclosing class/function names. |
| `get_repo_structure(max_depth=100)` | Tree-rendered view of the repository, filtered to directories and `.py` files; excludes `.git`, `build`, `__pycache__`, etc. |
| `extract_class_skeleton(file_name)` | For all top-level classes in `file_name`: emits class signature + each method's `def` line with the body elided to `...`. Top-level imports and class/method decorators are preserved. |

Private helpers (not part of the API): `_build_index`, `_update_indices`, `_build_python_index`, `_search_func_in_class`, `_search_func_in_all_classes`, `_search_top_level_func`, `_search_func_in_code_base`.

---

## `context/search/python_search_utils.py`

### `SearchResult` dataclass

```python
@dataclass
class SearchResult:
    file_path: str   # absolute
    class_name: Optional[str]
    func_name: Optional[str]
    code: str
```

Rendering methods (produce tagged strings using `<file>`, `<class>`, `<func>`, `<code>` markers):

- `to_tagged_upto_file(project_root)`
- `to_tagged_upto_class(project_root)`
- `to_tagged_upto_func(project_root)`
- `to_tagged_str(project_root)` — full result including the code block

Static collapse helpers (used when `len(results) > RESULT_SHOW_LIMIT`):

- `SearchResult.collapse_to_file_level(results, project_root) -> str`
- `SearchResult.collapse_to_method_level(results, project_root) -> str`

### Module-level helpers

| Function | Returns |
|---|---|
| `find_python_files(dir_path) -> list[str]` | Recursive `.py` glob; excludes `build`, `doc`, `requests/packages`, `tests/regrtest_data`, `tests/input` |
| `parse_python_file(file_path) -> Optional[(classes, class_to_funcs, top_level_funcs)]` | Each entry is `(name, start_line, end_line)` from AST; returns `None` on parse failure |
| `get_code_region_containing_code(file_path, code_str) -> list[(start_line, context)]` | Substring matches with three lines of context above and below |
| `get_func_snippet_with_code_in_file(file_path, code_str) -> list[str]` | Bodies of `FunctionDef` nodes that contain `code_str` |
| `get_code_snippets(file_path, start, end) -> str` | Lines `start..end` joined as a string |
| `extract_func_sig_from_ast(func_ast) -> list[int]` | Signature line numbers of a `FunctionDef` |
| `extract_class_sig_from_ast(class_ast) -> list[int]` | Signature line numbers of a `ClassDef` |
| `get_class_signature(file_path, class_name) -> str` | Signature lines of the named class |
| `extract_class_skeleton(file_path) -> str` | Whole-file skeleton: top-level imports + each class header + each method's `def` line with `...` for the body. Mirrors `progctx-mcp-d4j/context/search/java_search_utils.extract_class_skeleton`, adapted for Python AST. |

---

## Tests

Two pytest suites:

- **`test_python_search_manager.py`** — unit tests that exercise all nine search APIs against the in-repo `resources/sample_repo/` fixture. Each section maps to one of the `maple_*` tools.
- **`test_mcp_e2e.py`** — opt-in end-to-end test that boots the actual MCP server inside the SWE-bench Docker container for `astropy__astropy-13033`, connects an MCP client over STDIO, and verifies the `maple_*` tools work through the real protocol against the real astropy source tree. Auto-skipped when Docker isn't available. Pairs with **`mcp_e2e_runner.py`** — the in-container runner script that the test `cp_in`s and executes inside the container. The runner lives in its own file (not inlined as a string in the test) so it gets normal Python syntax highlighting and IDE support.

### Setup

The tests run in the existing SWE-bench evaluation conda env, `swe-bench-eval`. `pytest` is not currently part of `swe-bench/environment.yml`, so it needs to be pip-installed into the env once. From the repository root:

```bash
# 1) Create swe-bench-eval if you don't already have it
conda env create -f swe-bench/environment.yml

# 2) Activate and add pytest
conda activate swe-bench-eval
pip install pytest
```

The env pins `python=3.10`, which satisfies the package's Python 3.10+ requirement.

### Running the unit tests

```bash
cd progctx-mcp-swe-bench
python -m pytest test_python_search_manager.py -v
```

Expected output: **26 passed in well under a second.** All tests should be green.

### Sample-repo fixture (`resources/sample_repo/`)

A deliberately small Python project shaped to exercise the search core:

```
sample_repo/
├── utils.py            (2 top-level functions: normalize_name, compute_weight_kg)
└── animals/
    ├── mammals.py      (class Mammal + subclass Dog)
    └── birds.py        (class Bird)
```

- 3 classes (`Mammal`, `Dog`, `Bird`)
- `speak` method defined in all 3 classes — exercises overload/cross-class lookup
- `fetch` only in `Dog`, `fly` only in `Bird`, `list_traits` only in `Mammal` — exercises class-scoped and file-scoped filtering
- Distinctive strings (`"warm-blooded"`, `"wingspan"`, `"Woof!"`) for code-search assertions
- Multi-file, multi-directory layout exercises `get_repo_structure` and the path-`endswith` filtering used by all `*_in_file` APIs

### End-to-end test against a SWE-bench Docker container

`test_mcp_e2e.py` boots the actual MCP server **inside the SWE-bench Docker container** for `astropy__astropy-13033`, connects an MCP client over STDIO, and exercises a representative subset of the `maple_*` tools through the real MCP protocol against the real astropy source tree at `/testbed`.

`astropy__astropy-13033` is the first instance in `swe-bench/swe_bench_verified/multihunk_bugs_swe_bench_verified_32.json` and is the canonical example bug used throughout `CLAUDE.md`. The instance image already contains astropy checked out at the bug's `base_commit`, so the test pulls no source code onto the host.

#### Prerequisites

```bash
# Docker Desktop running, with ~5 GB free space for the astropy SWE-bench image.
docker ps  # must succeed

# The swe-bench-eval conda env (it provides DockerContainer + image-name
# helpers via swe_bench_utils, which the test imports).
conda activate swe-bench-eval
pip install pytest   # if not already installed (see Setup above)
```

No `mcp[fastmcp]` installation on the host: the test installs it **inside a dedicated `mcp-e2e` conda env it creates inside the container**, so it works regardless of the bug's testbed Python version.

#### Running the end-to-end test

```bash
cd progctx-mcp-swe-bench
python -m pytest test_mcp_e2e.py -v -s
```

The `-s` flag is recommended so the per-step progress log streams live to the terminal during the multi-minute run.

What the test does, in order, with a labelled progress marker for every phase:

1. Explicitly `docker pull` the SWE-bench instance image (timeout 1200 s; surfaces network/registry errors locally rather than at container start).
2. Start a fresh container with `/testbed` as the workdir.
3. Verify miniconda is present (`conda --version`).
4. Create a fresh conda env `mcp-e2e` with Python 3.11 inside the container. This is what makes the test independent of the bug's testbed Python (which may be 3.7-3.9 for older bugs and would fail PythonSearchManager's PEP 604 type hints).
5. Verify the new env's `python --version` reports 3.11.
6. `pip install --quiet 'mcp[fastmcp]' fastmcp` inside the env (covers both the official `mcp` SDK and the standalone `fastmcp` package, matching the d4j setup defensively).
7. Smoke-import `mcp`, `mcp.server.fastmcp`, `mcp.client.stdio` to confirm the install resolved.
8. `cp_in` `progctx-mcp-swe-bench/context/` and `mcp_server/` into `/opt/progctx-mcp-swe-bench/` inside the container; verify the copy with `ls`.
9. Drop the in-container runner script into `/tmp/run_mcp_e2e.py`.
10. Execute the runner via `conda run -n mcp-e2e python /tmp/run_mcp_e2e.py`. The runner spawns `python_analysis_server.py` (STDIO transport) as a subprocess, connects with `mcp.client.stdio` + `ClientSession`, runs `initialize`, then `list_tools` (asserts all nine `maple_*` are registered), then calls `maple_find_class("Quantity")`, `maple_repo_structure(max_depth=1)`, and `maple_extract_class_skeleton("quantity.py")`. Prints `ALL_PASSED` on success.
11. Tear the container down in the `finally` block.

Expected output: **1 passed** in roughly 3–12 minutes on first run (dominated by the SWE-bench image pull, the conda env creation, and the astropy index build), ~2–3 min on subsequent runs once the image is cached.

#### Skip behavior

The test auto-skips with a clear message at module load when:

- `docker` isn't on `PATH` or `docker ps` fails — "Start Docker Desktop and try again."
- `swe_bench_utils` isn't importable — "Activate the swe-bench-eval conda env first."

(The Python 3.10+ check that the previous revision did is no longer needed — we always create a Python 3.11 env inside the container.)

#### Debugging a failure

The test is built for post-mortem inspection:

- **Progress markers** at every phase (`========` separators in the log) — you can see exactly which step crashed.
- **Per-step diagnostics on failure**: when any `docker exec` returns a non-zero code or the runner doesn't reach `ALL_PASSED`, the test dumps `conda env list`, the relevant env's `pip list`, and the trailing 2 000 chars of the failing command's combined stdout+stderr.
- **Distinct runner exit codes**: 2 = bad in-container setup, 3 = `list_tools` failed, 4 = `find_class` failed, 5 = `repo_structure` failed, 6 = `extract_class_skeleton` failed.
- **The runner writes progress to stderr**, not stdout (which is the MCP protocol channel), so its trace can't accidentally corrupt the MCP framing.
- **Keep the container alive after failure** by setting `MCP_E2E_KEEP_CONTAINER=1`:

  ```bash
  MCP_E2E_KEEP_CONTAINER=1 python -m pytest test_mcp_e2e.py -v -s
  # On failure, the test logs the container name and the commands to inspect it:
  docker exec -it swebench-mcp-e2e-<pid> bash
  docker exec -it swebench-mcp-e2e-<pid> cat /tmp/run_mcp_e2e.py
  docker rm -f swebench-mcp-e2e-<pid>   # clean up when you're done
  ```
