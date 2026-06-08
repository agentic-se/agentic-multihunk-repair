# Codex Metrics Scripts

This directory contains Python scripts adapted from the Gemini metrics scripts to work with Codex logging format.

## Overview

The scripts have been adapted to parse Codex's JSONL log format instead of Gemini's JSON format. Key differences handled:

### Codex Log Structure
- **Format**: JSONL (one JSON object per line)
- **Location**: `collected-codex-cli-logs/<BugID>/codex-session-*.jsonl`
- **Tool Calls**: Identified by `type: "function_call"` records
- **Tool Names**:
  - `shell` (mapped to `run_shell_command`)
  - `read_file`
  - `write_file`
  - `edit_file`
- **Arguments**: Found in `arguments` field as JSON string
- **Shell Commands**: Stored as arrays like `["bash", "-lc", "actual_command"]`
- **Timestamps**: ISO-8601 format in `timestamp` field

### Gemini Log Structure (Original)
- **Format**: JSON with `attributes` objects
- **Event Markers**: `event.name: "gemini_cli.tool_call"`
- **Tool Names**: In `function_name` field
- **Arguments**: In `function_args` field (stringified JSON)

## Scripts Created

### 1. `tools_calculation_codex.py`
**Purpose**: Count tool invocations from Codex JSONL files

**Usage**:
```bash
python3 tools_calculation_codex.py \
  --input-dir collected-codex-cli-logs \
  --out-long results-codex/tools_count_codex.csv \
  --out-wide results-codex/tools_count_all_codex.csv
```

**Output**:
- `tools_count_codex.csv`: Long format with columns: bug, function_name, count, command
- `tools_count_all_codex.csv`: Wide format with one column per tool

### 2. `analyze_shell_commands_codex.py`
**Purpose**: Analyze and categorize shell commands

**Usage**:
```bash
python3 analyze_shell_commands_codex.py > results-codex/shell_command_analysis.txt
```

**Categories**:
- defects4j_compile
- defects4j_test
- defects4j_other
- test_scripts (run_bug_exposing_tests.sh, run_all_tests_trace.sh)
- git_all
- build_and_execution (mvn, gradle, java)
- file_operations (rm, mkdir, ls, cp, mv)
- other

### 3. `update_tools_count_codex.py`
**Purpose**: Update tools count CSV with categorized shell commands

**Usage**:
```bash
python3 update_tools_count_codex.py
```

**Input**: `results-codex/tools_count_codex.csv`
**Output**: Updated `results-codex/tools_count_all_codex.csv`

### 4. `timestamp_calculation_codex.py`
**Purpose**: Calculate execution duration from log timestamps

**Usage**:
```bash
python3 timestamp_calculation_codex.py \
  --status-csv results-codex/codex_results.csv \
  --logs-dir collected-codex-cli-logs \
  --out results-codex/duration_analysis.csv
```

**Output**: CSV with bug_id, status, duration_seconds

### 5. `edit_accuracy_codex.py`
**Purpose**: Compare edited files in diffs vs buggy_files JSON

**Usage**:
```bash
python3 edit_accuracy_codex.py \
  --bugs-root collected-codex-cli-logs \
  --json config/buggy_files.json \
  --report-summary results-codex/ote-summary.csv \
  --report-details results-codex/ote-details.csv
```

**Output**:
- Summary CSV: bug, num_expected, correct_edits, ote, missed_edits
- Details CSV: bug, status, path

### 6. `analyze_tool_sequences_codex.py`
**Purpose**: Analyze tool usage sequences and patterns

**Usage**:
```bash
python3 analyze_tool_sequences_codex.py
```

**Configuration** (edit script to customize):
- `LOGS_DIR`: Directory with Codex logs
- `RESULTS_CSV`: Path to results CSV
- `OUT_DIR`: Output directory

**Output**: N-gram pattern CSVs for windows 3, 4, 5

### 7. `generate_repair_ability_codex.py`
**Purpose**: Generate repair ability metrics

**Usage**:
```bash
python3 generate_repair_ability_codex.py
```

**Requires**:
- `config/method_multihunk.json`
- `results-codex/codex_results.csv`

**Output**: `results-codex/codex_repair_ability.csv`

### 8. `generate_localization_ability_codex.py`
**Purpose**: Generate localization ability metrics

**Usage**:
```bash
python3 generate_localization_ability_codex.py
```

**Requires**:
- `results-codex/codex_repair_ability.csv`
- `results-codex/ote-summary.csv`

**Output**: `results-codex/codex_localization_ability.csv`

### 9. `hunk_divergence_proximity_class_codex.py`
**Purpose**: Compute average divergence by pass/fail and proximity class counts

**Usage**:
```bash
python3 hunk_divergence_proximity_class_codex.py \
  --results results-codex/codex_results.csv \
  --divergence results-codex/divergence.csv \
  --proximity results-codex/proximity.csv \
  --output results-codex/divergence_analysis.csv
```

## Results Generated

The following results have been generated in `results-codex/`:

1. **tools_count_codex.csv** (28,188 lines)
   - Detailed tool invocations per bug
   - Includes command text for shell commands

2. **tools_count_all_codex.csv** (373 bugs)
   - Wide format: one row per bug
   - Columns for each tool type including categorized shell commands

3. **shell_command_analysis.txt**
   - Statistical analysis of shell command usage
   - Category breakdown
   - Top 20 most common commands
   - Command base analysis

4. **update_tools_output.txt**
   - Summary statistics of categorized shell commands
   - Sample data for verification

## Key Adaptations Made

### 1. Log File Parsing
- Changed from JSON array/object parsing to JSONL line-by-line parsing
- Updated event detection from `event.name` to `type` field
- Modified tool name extraction to use `name` field instead of `function_name`

### 2. Shell Command Extraction
- Updated to handle Codex's array format: `["bash", "-lc", "command"]`
- Extract actual command from 3rd array element
- Handle both array and string command formats

### 3. File Structure
- Changed from single JSON files to directory structure with JSONL files
- Updated bug ID extraction to use directory names
- Modified file discovery to use `glob()` on bug directories

### 4. Tool Name Mapping
- Created mapping from Codex tool names to standardized names:
  - `shell` → `run_shell_command`
  - Preserved: `read_file`, `write_file`, `edit_file`

## Statistics

### Tool Usage Summary (372 bugs analyzed)
- **Total shell commands**: 11,918
- **Total function calls**: 28,188 records
- **Average commands per bug**: ~32 shell commands

### Shell Command Categories
- defects4j_compile: 406 (3.4%)
- defects4j_test: 1,143 (9.6%)
- defects4j_other: 2 (0.02%)
- test_scripts: 865 (7.3%)
- git_all: 15 (0.1%)
- build_and_execution: 102 (0.9%)
- file_operations: 795 (6.7%)
- other: 8,590 (72.1%)

## Dependencies

- Python 3.7+
- Standard library only (no external packages required)

## Notes

- All scripts maintain the same interface as their Gemini counterparts
- Output format is identical to enable comparison between Codex and Gemini runs
- Scripts are standalone and can be run independently
- Timestamps are automatically normalized to UTC for consistency
