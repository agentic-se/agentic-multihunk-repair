# Qwen Code Metrics Summary

This directory contains all the generated metrics CSV files for the Qwen Code logs analysis.

## Generated Files

### Main Metrics (6 CSV files)

1. **qwen_repair_ability.csv** (8.2K, 373 rows)
   - Bug repair success metrics
   - Columns: bug_id, repair, failed_test_prior, failed_test_after, failure_delta, compile_fail
   - Shows whether Qwen successfully repaired each bug

2. **qwen_localization_ability.csv** (5.1K, 373 rows)
   - Bug localization success metrics
   - Columns: bug_id, localization
   - Localization = 1 when Qwen correctly identified all buggy files
   - Success rate: 142/372 (38.2%)

3. **qwen_edit_accuracy_summary.csv** (7.3K, 373 rows)
   - Summary of edit accuracy per bug
   - Columns: bug, num_expected, correct_edits, ote (other than expected), missed_edits

4. **qwen_edit_accuracy_details.csv** (43K, 611 rows)
   - Detailed list of all file edits
   - Columns: bug, status (match/ote), path

5. **qwen_tools_wide.csv** (19K, 373 rows)
   - Aggregated tool usage counts per bug
   - Columns: bug, edit, exit_plan_mode, glob, list_directory, read_file, run_shell_command (with subcategories), search_file_content, task, todo_write, web_fetch, write_file
   - Shell command breakdowns: defects4j_compile, defects4j_test, defects4j_other, test_scripts, git_all, build_and_execution, file_operations, other

6. **qwen_tools_long.csv** (584K, 4,963 rows)
   - Detailed tool usage with individual commands/queries
   - Columns: bug, function_name, count, command
   - One row per unique command/query per bug

### Tool Sequences Analysis (9 CSV files in tool_sequences/)

Generated for window sizes 3, 4, and 5, with three variants each:
- **all**: Patterns across all bugs
- **successful**: Patterns in bugs that were successfully repaired
- **unsuccessful**: Patterns in bugs that were not successfully repaired

Files:
- tool_sequence_patterns_window_3_all.csv (65K)
- tool_sequence_patterns_window_3_successful.csv (32K)
- tool_sequence_patterns_window_3_unsuccessful.csv (60K)
- tool_sequence_patterns_window_4_all.csv (218K)
- tool_sequence_patterns_window_4_successful.csv (85K)
- tool_sequence_patterns_window_4_unsuccessful.csv (192K)
- tool_sequence_patterns_window_5_all.csv (466K)
- tool_sequence_patterns_window_5_successful.csv (157K)
- tool_sequence_patterns_window_5_unsuccessful.csv (394K)

### Analysis Reports (1 text file)

**qwen_shell_commands_analysis.txt** (9.2K)
- Detailed analysis of shell command usage
- Command category breakdown with percentages
- Top 20 individual commands
- Command base analysis

## Key Statistics

### Shell Commands (from qwen_shell_commands_analysis.txt)
- Total shell command invocations: 4,827
- Unique shell commands: 2,489

Command categories:
- other: 2,404 (49.8%)
- defects4j_test: 944 (19.6%)
- test_scripts: 617 (12.8%)
- defects4j_compile: 456 (9.4%)
- search: 158 (3.3%)
- file_operations: 67 (1.4%)
- git_inspection: 51 (1.1%)

### Tool Sequences
- Total bugs with sequences: 339
- Window sizes analyzed: 3, 4, 5

## Scripts Used

The following Qwen-specific scripts were created and executed:

1. `tools_calculation_qwen.py` - Adapted to handle Qwen's NDJSON format and nested attributes
2. `edit_accuracy_qwen.py` - Modified to find diff files in bug directories
3. `update_tools_count_qwen.py` - Categorizes shell commands
4. `analyze_shell_commands_qwen.py` - Analyzes shell command patterns
5. `analyze_tool_sequences_qwen.py` - Extracts and analyzes tool usage sequences
6. `generate_localization_ability_qwen.py` - Computes localization success metrics
7. `generate_repair_ability_qwen.py` - Already existed, computes repair success metrics

## Data Sources

- **Input logs**: `collected-qwen-code-logs/` (372 bug directories)
- **Bug results**: `qwen_code_results/results-hunk4j-qwen-code.csv`
- **Bug metadata**: `~/Desktop/birch/oak/config/method_multihunk.json`

## Total Output

- **16 files** generated (6 main CSVs + 9 tool sequence CSVs + 1 analysis report)
- **24,770 total lines** across all CSV files
