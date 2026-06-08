# Spatial Proximity Classification for SWE-bench

This directory contains scripts for classifying multi-hunk bugs from SWE-bench Verified into **spatial proximity classes**, adapted from the original Hunk4J (Java) classification pipeline to work with Python repositories.

## Background

Multi-hunk bugs require changes across multiple locations in the source code. The spatial proximity classification categorizes each bug based on how its hunks are distributed across the codebase:

| Class | Definition |
|-------|-----------|
| **Nucleus** | All hunks in the same file and same function/method |
| **Cluster** | All hunks in the same file but across different functions/methods |
| **Orbit** | Hunks span multiple files but within the same Python module (package) |
| **Sprawl** | Hunks span multiple modules, with shared module path length greater than the threshold. |
| **Fragment** | Hunks span multiple modules, with shared module path length lesser or equal the threshold. |

**Threshold**:  We compute the median module depth across these 32 bugs, and take the half of that value as the threshold.

The cutoff for distinguishing Sprawl from Fragment is computed as `floor(median_module_depth / 2)` across all hunks, unless overridden via `--threshold`.

## Pipeline

The classification is a single-step process. The enclosing function/class context for each hunk is extracted directly from the `@@` header line in the unified diff (the text after the second `@@`), removing the need for AST parsing or checked-out repositories.

### Classify Bugs

```bash
python proximity_class.py ../swe_bench_verified/multihunk_bugs_only.json proximity_class.csv
```

Reads `multihunk_bugs_only.json` (or any JSON with the same `buggy_hunks` schema), extracts the method/class context from each hunk's `@@` header, and classifies each bug into a proximity class. Outputs a CSV with columns `bug_id` and `proximity_class`.

**How method context is resolved from `@@` headers:**
- `@@ -76,9 +83,10 @@ def _check_required_columns(self):` -> `_check_required_columns`
- `@@ -55,6 +55,13 @@ class BaseTimeSeries(QTable):` -> `BaseTimeSeries`
- `@@ -17,9 +17,9 @@` (no context) -> `<module>`

**Optional flag:**
- `--threshold N` — Override the automatically computed LCP cutoff for Sprawl vs Fragment

## Checking Out SWE-bench Bugs

```bash
python checkout_swebench.py [--work-dir ~/WORK_DIR] [--only instance_id ...]
```

Clones repositories (as bare repos) and creates git worktrees at each bug's `base_commit`. Applies the `test_patch` so failing tests are present. Bug metadata (problem statement, failing tests) is written to `.swebench/` in each workspace.

**Flags:**
- `--work-dir` — Root directory for workspaces (default: `~/WORK_DIR`)
- `--only` — Checkout specific instance IDs only
- `--skip-test-patch` — Don't apply the test patch
- `--debug` — Enable debug logging

## Files

| File | Description |
|------|-------------|
| `checkout_swebench.py` | Checks out SWE-bench bug workspaces from GitHub |
| `proximity_class.py` | Classifies bugs into spatial proximity classes using `@@` header context |
| `proximity_class.csv` | Classification results (generated) |
| `test_proximity_class.py` | Pytest suite covering header parsing, predicates, classification, and CLI |
| `resources/` | One real SWE-bench bug per proximity class, used as test fixtures |

## Tests

```bash
# From this directory
python -m pytest test_proximity_class.py -v
```

The `resources/` folder contains five JSON fixtures, each holding the `buggy_hunks` of one real SWE-bench multi-hunk bug — one bug per spatial proximity class:

| Class | Fixture | Bug |
|-------|---------|-----|
| Nucleus | `resources/nucleus.json` | `django__django-11740` |
| Cluster | `resources/cluster.json` | `astropy__astropy-13033` |
| Orbit | `resources/orbit.json` | `astropy__astropy-14369` |
| Sprawl | `resources/sprawl.json` | `django__django-11138` |
| Fragment | `resources/fragment.json` | `django__django-11400` |

`TestResourceFixtures` runs each fixture both in-memory (calling `classify` directly) and via the CLI (`python proximity_class.py <fixture> <out.csv> --threshold 1`), asserting the expected class. The cutoff `1` matches the `floor(median_module_depth / 2)` value computed across the full 32-bug subset.

## Results (32 SWE-bench Multi-Hunk Bugs)

```
Nucleus:   6
Cluster:  16
Orbit:     5
Fragment:  4
Sprawl:    1
```
