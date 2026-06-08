# Results Directory

This directory contains CSV files with metrics and analysis results from automated program repair experiments using Gemini CLI.

## Table of Contents
- [Repair Results](#repair-results)
- [Localization & Edit Accuracy](#localization--edit-accuracy)
- [Tool Usage Analysis](#tool-usage-analysis)
- [Tool Sequencing Patterns](#tool-sequencing-patterns)
- [Experimental Runs](#experimental-runs)

---

## Repair Results

### `full_gemini_cli_run.csv`
**Description:** Complete results from Gemini CLI repair attempts across all bugs.

**Columns:**
- `bug`: Bug identifier (e.g., Chart-14)
- `pass`: Whether the repair passed all tests (Yes/No)
- `test_fail`: Whether any tests failed (Yes/No)
- `compile_fail`: Whether compilation failed (Yes/No)
- `failed_tests`: List of specific test cases that failed (semicolon-separated)

**Use case:** Primary dataset for evaluating repair success rate.

---

### `gemini_repair_ability.csv`
**Description:** Comprehensive repair metrics combining test results with triggered tests.

**Columns:**
- `bug_id`: Bug identifier (e.g., Chart_2)
- `repair`: 1 if bug was successfully repaired (pass = Yes), 0 otherwise
- `failed_test_prior`: Number of tests that failed before the repair (from triggered_tests)
- `failed_test_after`: Number of tests that failed after the repair attempt
- `compile_fail`: 1 if compilation failed, 0 otherwise

**Source data:**
- Test results from `full_gemini_cli_run.csv`
- Triggered tests from `config/method_multihunk.json`

**Use case:** Analyzing repair success in relation to test complexity.

---

## Localization & Edit Accuracy

### `gemini_localization_ability.csv`
**Description:** Measures whether Gemini correctly localized bugs (found all buggy locations without false positives).

**Columns:**
- `bug_id`: Bug identifier
- `localization_ability`: 1 if correctly localized, 0 otherwise
  - Set to 1 only when: `num_expected == correct_edits AND ote == 0 AND missed_edits == 0`

**Source data:** `ote-summary.csv`

**Use case:** Evaluating fault localization accuracy independent of repair quality.

---

### `ote-summary.csv`
**Description:** Summary of Over-The-Edge (OTE) edits and edit accuracy for each bug.

**Columns:**
- `bug`: Bug identifier
- `num_expected`: Number of expected edits (ground truth)
- `correct_edits`: Number of edits made in correct locations
- `ote`: Number of Over-The-Edge edits (edits outside buggy hunks)
- `missed_edits`: Number of expected edits that were not made

**Use case:** Analyzing edit precision and recall.

---

### `ote-details.csv`
**Description:** Detailed breakdown of each edit location, showing whether it was correct, OTE, or missed.

**Columns:**
- `bug`: Bug identifier
- `file`: File path where edit occurred
- `line_number`: Line number of the edit
- `edit_type`: Classification (correct_edit, ote, missed_edit)
- Additional context about the edit

**Use case:** Fine-grained analysis of edit locations and patterns.

---

### `hunk_divergence.csv`
**Description:** Measures how far edits diverge from buggy hunks (spatial distance).

**Columns:**
- `bug`: Bug identifier
- `file`: File path
- `edit_line`: Line where edit was made
- `nearest_hunk_distance`: Distance to nearest buggy hunk (0 = inside hunk)
- `hunk_type`: Type of nearest hunk (buggy/correct)

**Use case:** Analyzing spatial accuracy of edits relative to ground truth.

---

### `proximity_class.csv`
**Description:** Classifies edits by proximity to buggy locations (inside, adjacent, or distant).

**Columns:**
- `bug`: Bug identifier
- `inside_buggy_hunk`: Number of edits inside buggy hunks
- `adjacent_to_buggy_hunk`: Number of edits within N lines of buggy hunks
- `distant`: Number of edits far from any buggy hunk
- `missed_edits`: Number of expected edits not made

**Use case:** Categorizing edit proximity patterns.

## Tool Usage Analysis

### `token_and_duration_gemini.csv`
**Description:** Detailed log showing input and output token, and time duration for each bug.

**Columns:**
- `bug`: Bug identifier
- `input_token`: Number of input token
- `output_token`: Number of output token
- `time_duration`: Time needed for Gemini-CLI to execute
- `unread_instruction`: Whether or not Gemini-CLI was able to read the instructions markdown file. `0` means instructions read, `1` means instructions unread (BAD).

**Use case:** Granular analysis of tool usage patterns and command-level details.

---

## Tool Usage Analysis

### `tools_count_gemini.csv`
**Description:** Detailed tool usage log showing individual tool invocations with arguments.

**Columns:**
- `bug`: Bug identifier
- `function_name`: Name of the tool called
- `count`: Number of times this specific invocation occurred
- `command`: For `run_shell_command`, the actual command executed; for other tools, specific arguments

**Use case:** Granular analysis of tool usage patterns and command-level details.

---

### `tools_count_all_gemini.csv`
**Description:** Aggregated tool usage statistics per bug with detailed shell command breakdown.

**Columns:**
- `bug`: Bug identifier
- `glob`: Count of glob (file pattern matching) calls
- `google_web_search`: Count of web search calls
- `list_directory`: Count of directory listing calls
- `read_file`: Count of file read operations
- `read_many_files`: Count of batch file read operations
- `replace`: Count of file edit operations
- `run_shell_command`: Total count of shell command executions
- `run_shell_command_defects4j_compile`: Compilation commands
- `run_shell_command_defects4j_test`: Test execution commands
- `run_shell_command_defects4j_other`: Other defects4j commands (export, clean, etc.)
- `run_shell_command_test_scripts`: Custom test scripts (run_bug_exposing_tests.sh, run_all_tests_trace.sh)
- `run_shell_command_git_all`: All git commands (diff, checkout, restore, etc.)
- `run_shell_command_build_and_execution`: Build tools and Java execution (mvn, gradle, ant, java -cp)
- `run_shell_command_file_operations`: File operations (rm, mkdir, chmod, cp, mv)
- `run_shell_command_other`: Other shell commands (curl, custom scripts, etc.)
- `search_file_content`: Count of content search operations
- `web_fetch`: Count of web page fetches
- `write_file`: Count of file write operations

**Use case:** High-level tool usage analysis and comparing repair strategies across bugs.

---

## Tool Sequencing Patterns

### `tool_sequence_patterns.csv`
**Description:** Most common sequences of tool calls (n-grams) with sliding windows of size 3 and 4.

**Columns:**
- `window_size`: Size of the sliding window (3 or 4)
- `tool_sequence`: Sequence of tools separated by " -> "
- `frequency`: Number of times this pattern occurred across all bugs

**Examples:**
- `replace -> run_shell_command_defects4j_compile -> run_shell_command_defects4j_test` (edit-compile-test cycle)
- `replace -> replace -> replace` (multiple consecutive edits)

**Source data:** Tool call logs from `~/Desktop/logs/372_bugs/*_logs.json`

**Use case:** Understanding common repair workflows and debugging patterns.

---

## Experimental Runs

### `test_results_mode_4.csv`
**Description:** Test results from a specific experimental mode/configuration.

**Use case:** Comparing different experimental configurations.

---

### `25_bugs_results.csv`
**Description:** Results from a subset of 25 bugs (possibly a pilot or validation set).

**Use case:** Initial testing or validation experiments.

---

### `current_mcp_run.csv` / `mcp_single_run.csv`
**Description:** Results from runs using MCP (Model Context Protocol) integration.

**Use case:** Comparing vanilla Gemini CLI vs. MCP-enhanced runs.

---

### `mcp_tools_count.csv` / `mcp_tools_count_all.csv`
**Description:** Tool usage statistics for MCP-enhanced runs (similar structure to `tools_count_gemini.csv` and `tools_count_all_gemini.csv`).

**Use case:** Analyzing how MCP integration affects tool usage patterns.

---

### `vanilla_mcp_duration.csv`
**Description:** Duration/timing metrics comparing vanilla Gemini CLI vs. MCP runs.

**Columns:** (Likely includes timing information for each bug in both configurations)

**Use case:** Performance comparison between vanilla and MCP modes.

---

## Data Sources

Most metrics are derived from:
1. **Tool call logs:** `~/Desktop/logs/372_bugs/*_logs.json`
2. **Bug configuration:** `config/method_multihunk.json`
3. **Test execution results:** Output from defects4j test runs

## Analysis Scripts

The Python scripts used to generate these CSVs are located in:
- `metrics/tools_calculation_gemini.py`: Tool usage counting
- `metrics/edit_accuracy_gemini.py`: OTE and edit accuracy
- `metrics/hunk_divergence_proximity_class_gemini.py`: Spatial analysis
- `analyze_tool_sequences.py`: Tool sequencing patterns
- `generate_repair_ability.py`: Repair ability metrics

---

## Quick Reference: Key Metrics

| Metric | File | Column |
|--------|------|--------|
| Repair success rate | `gemini_repair_ability.csv` | `repair` |
| Localization accuracy | `gemini_localization_ability.csv` | `localization_ability` |
| OTE edits | `ote-summary.csv` | `ote` |
| Edit precision | `ote-summary.csv` | `correct_edits / (correct_edits + ote)` |
| Edit recall | `ote-summary.csv` | `correct_edits / num_expected` |
| Tool usage | `tools_count_all_gemini.csv` | All tool columns |
| Common workflows | `tool_sequence_patterns.csv` | `tool_sequence` |

---

Last updated: 2025-10-29
