# Artifact Reference

This document describes the purpose of each JSON file and Python script in this directory.

---

## Python Scripts

### `parque_reader.py`
Utility script for reading the raw SWE-bench Verified dataset from its Parquet format (stored under `data/`). Used to inspect or re-export the source data.

### `analyze_multihunk.py`
Main analysis script. Reads `swe_bench.jsonl` and classifies all 500 SWE-bench Verified instances as single-hunk or multi-hunk based on their gold patch. A bug is considered multi-hunk if its patch edits more than one file, or if a single file contains multiple disjoint edit regions (multiple `@@` hunk headers). Outputs `multihunk_analysis.json` and prints a summary to stdout.

### `classify_instances.py`
Classifies all 500 instances along two dimensions: hunk type (single-hunk vs multi-hunk) and issue type (Bug, Regression, Feature/Enhancement, Unlabeled). Issue labels from GitHub are normalised — e.g. `"bug"`, `"type: bug"`, `"Bug :beetle:"` all map to Bug. Outputs `swe_bench_classified.json`.

---

## Classification Summary

### By Hunk Type

| Hunk Type | Count | % |
|---|---|---|
| single-hunk | 280 | 56.0% |
| multi-hunk | 220 | 44.0% |

### By Issue Type

| Issue Type | Count | % |
|---|---|---|
| Bug | 122 | 24.4% |
| Regression | 9 | 1.8% |
| Feature/Enhancement | 30 | 6.0% |
| Unlabeled | 339 | 67.8% |

### Cross-tabulation (Hunk Type x Issue Type)

| | single-hunk | multi-hunk |
|---|---|---|
| Bug | 75 | 47 |
| Regression | 3 | 6 |
| Feature/Enhancement | 11 | 19 |
| Unlabeled | 191 | 148 |

---

## JSON Files

### `swe_bench.jsonl`
Source dataset. Contains all 500 SWE-bench Verified instances in JSONL format (one JSON object per line). Each entry includes the `instance_id`, `repo`, gold `patch`, `test_patch`, `problem_statement`, and associated metadata. This is the primary input to the analysis pipeline.

### `swe-bench_issue_labels.json`
GitHub issue label data for SWE-bench instances. Keyed by `instance_id`, with each value being a list of label strings (e.g. `"Bug"`, `"Feature Request"`, `"Docs"`). Used to filter instances by issue type.

### `multihunk_verified.json`
Output of `analyze_multihunk.py`. Contains all 220 multi-hunk bugs from SWE-bench Verified, excluding single-hunk instances. Keyed by `instance_id`. Each entry contains a `buggy_hunks` dict, where hunks are numbered from `"0"` and each hunk records the `file` it belongs to, its `start_line` and `end_line` in the original (pre-fix) file, and the `code` of the buggy region.

### `multihunk_bugs_only.json`
Filtered subset of `multihunk_analysis.json`. Contains the 32 instances that are both multi-hunk and labeled `"Bug"` in `swe-bench_issue_labels.json`. Instances labeled exclusively as feature requests, documentation changes, or other non-bug categories are excluded. Same schema as `multihunk_analysis.json`.
