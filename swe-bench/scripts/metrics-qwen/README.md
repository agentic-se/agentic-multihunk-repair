# Qwen Metrics Calculation Scripts

This directory contains all the Python scripts that were executed to generate the Qwen Code metrics.

## Execution Order and Dependencies

### 1. **generate_repair_ability_qwen.py**
**Executed first** (already existed, was run early)

**What it does:**
- Reads the Qwen results CSV and bug metadata JSON
- Calculates repair success metrics for each bug
- Determines if tests pass, compilation succeeds, etc.

**Inputs:**
- `qwen_code_results/results-hunk4j-qwen-code.csv`
- `~/Desktop/birch/oak/config/method_multihunk.json`

**Outputs:**
- `qwen_code_results/metrics/qwen_repair_ability.csv`

**Run command:**
```bash
python3 generate_repair_ability_qwen.py
```

---

### 2. **tools_calculation_qwen.py**
**Executed second**

**What it does:**
- Parses all Qwen JSON log files (handles NDJSON format)
- Extracts tool call events (reads, edits, shell commands, etc.)
- Counts tool usage per bug
- Generates both long (detailed) and wide (aggregated) formats

**Inputs:**
- `collected-qwen-code-logs/*/qwen*.json` (372 log files)

**Outputs:**
- `qwen_code_results/metrics/qwen_tools_long.csv` (4,963 rows)
- `qwen_code_results/metrics/qwen_tools_wide.csv` (373 rows)

**Run command:**
```bash
python3 tools_calculation_qwen.py \
  --input-dir collected-qwen-code-logs \
  --pattern "*/qwen*.json" \
  --out-long qwen_code_results/metrics/qwen_tools_long.csv \
  --out-wide qwen_code_results/metrics/qwen_tools_wide.csv
```

**Key adaptations:**
- Handles NDJSON (newline-delimited JSON) format
- Extracts attributes from nested object structure
- Recognizes "qwen-code.tool_call" event names
- Extracts bug ID from parent directory name

---

### 3. **update_tools_count_qwen.py**
**Executed third** (depends on tools_calculation_qwen.py)

**What it does:**
- Reads the tools_long.csv
- Categorizes shell commands into meaningful groups
- Updates tools_wide.csv with shell command subcategories

**Inputs:**
- `qwen_code_results/metrics/qwen_tools_long.csv`
- `qwen_code_results/metrics/qwen_tools_wide.csv`

**Outputs:**
- Updates `qwen_code_results/metrics/qwen_tools_wide.csv` (adds 8 new columns)

**Run command:**
```bash
python3 update_tools_count_qwen.py
```

**Shell command categories:**
- defects4j_compile
- defects4j_test
- defects4j_other
- test_scripts
- git_all
- build_and_execution
- file_operations
- other

---

### 4. **edit_accuracy_qwen.py**
**Executed fourth**

**What it does:**
- Analyzes diff/patch files to see which files were edited
- Compares edited files against expected buggy files from JSON
- Calculates edit accuracy metrics (correct edits, missed edits, other edits)

**Inputs:**
- `collected-qwen-code-logs/*/patch-*.diff` (372 diff files)
- `~/Desktop/birch/oak/config/method_multihunk.json`

**Outputs:**
- `qwen_code_results/metrics/qwen_edit_accuracy_summary.csv` (373 rows)
- `qwen_code_results/metrics/qwen_edit_accuracy_details.csv` (611 rows)

**Run command:**
```bash
python3 edit_accuracy_qwen.py \
  --bugs-root collected-qwen-code-logs \
  --json ~/Desktop/birch/oak/config/method_multihunk.json \
  --report-summary qwen_code_results/metrics/qwen_edit_accuracy_summary.csv \
  --report-details qwen_code_results/metrics/qwen_edit_accuracy_details.csv
```

**Key adaptations:**
- Finds diff files directly in bug directories (not in a logs/ subdirectory)
- Handles Qwen's directory structure

---

### 5. **analyze_shell_commands_qwen.py**
**Executed fifth** (depends on tools_calculation_qwen.py)

**What it does:**
- Analyzes all shell commands used across all bugs
- Categorizes commands and generates statistics
- Creates a detailed text report with command patterns

**Inputs:**
- `qwen_code_results/metrics/qwen_tools_long.csv`

**Outputs:**
- `qwen_code_results/metrics/qwen_shell_commands_analysis.txt`

**Run command:**
```bash
python3 analyze_shell_commands_qwen.py > qwen_code_results/metrics/qwen_shell_commands_analysis.txt
```

**Analysis includes:**
- Command category breakdown with percentages
- Top 20 individual commands
- Command base analysis
- Proposed grouping strategies

---

### 6. **generate_localization_ability_qwen.py**
**Executed sixth** (depends on generate_repair_ability_qwen.py and edit_accuracy_qwen.py)

**What it does:**
- Determines if Qwen successfully localized the bug
- Localization = 1 when all expected buggy files were correctly identified

**Inputs:**
- `qwen_code_results/metrics/qwen_repair_ability.csv`
- `qwen_code_results/metrics/qwen_edit_accuracy_summary.csv`

**Outputs:**
- `qwen_code_results/metrics/qwen_localization_ability.csv` (373 rows)

**Run command:**
```bash
python3 generate_localization_ability_qwen.py
```

**Result:** 142/372 bugs successfully localized (38.2%)

---

### 7. **analyze_tool_sequences_qwen.py**
**Executed seventh**

**What it does:**
- Extracts sequences of tool calls from log files
- Analyzes N-gram patterns (windows of 3, 4, 5 consecutive tool calls)
- Separates patterns by success/failure
- Categorizes shell commands within sequences

**Inputs:**
- `collected-qwen-code-logs/*/qwen*.json` (372 log files)
- `qwen_code_results/results-hunk4j-qwen-code.csv`

**Outputs:**
- 9 CSV files in `qwen_code_results/metrics/tool_sequences/`:
  - `tool_sequence_patterns_window_3_all.csv`
  - `tool_sequence_patterns_window_3_successful.csv`
  - `tool_sequence_patterns_window_3_unsuccessful.csv`
  - `tool_sequence_patterns_window_4_all.csv`
  - `tool_sequence_patterns_window_4_successful.csv`
  - `tool_sequence_patterns_window_4_unsuccessful.csv`
  - `tool_sequence_patterns_window_5_all.csv`
  - `tool_sequence_patterns_window_5_successful.csv`
  - `tool_sequence_patterns_window_5_unsuccessful.csv`

**Run command:**
```bash
python3 analyze_tool_sequences_qwen.py
```

**Result:** Analyzed 339 bugs with complete tool sequences

---

## Complete Execution Script

To run all scripts in order:

```bash
# 1. Generate repair ability
python3 generate_repair_ability_qwen.py

# 2. Calculate tool usage
python3 tools_calculation_qwen.py \
  --input-dir collected-qwen-code-logs \
  --pattern "*/qwen*.json" \
  --out-long qwen_code_results/metrics/qwen_tools_long.csv \
  --out-wide qwen_code_results/metrics/qwen_tools_wide.csv

# 3. Update tools with shell command categories
python3 update_tools_count_qwen.py

# 4. Calculate edit accuracy
python3 edit_accuracy_qwen.py \
  --bugs-root collected-qwen-code-logs \
  --json ~/Desktop/birch/oak/config/method_multihunk.json \
  --report-summary qwen_code_results/metrics/qwen_edit_accuracy_summary.csv \
  --report-details qwen_code_results/metrics/qwen_edit_accuracy_details.csv

# 5. Analyze shell commands
python3 analyze_shell_commands_qwen.py > qwen_code_results/metrics/qwen_shell_commands_analysis.txt

# 6. Generate localization ability
python3 generate_localization_ability_qwen.py

# 7. Analyze tool sequences
python3 analyze_tool_sequences_qwen.py
```

---

## Key Differences from Gemini Scripts

These scripts were adapted from the original Gemini scripts with the following key changes:

1. **NDJSON Parsing**: Qwen logs use newline-delimited JSON instead of JSON arrays
2. **Event Names**: Changed from "gemini_cli.tool_call" to "qwen-code.tool_call"
3. **Nested Attributes**: Qwen logs have attributes nested in obj['attributes']
4. **Directory Structure**: Diff files are directly in bug directories, not in logs/ subdirectory
5. **Bug ID Extraction**: Extract from parent directory name instead of filename

---

## Output Summary

**Total files generated: 16**
- 6 main metric CSVs
- 9 tool sequence CSVs
- 1 shell command analysis report

**Total data: 24,770 lines** across all CSV files
