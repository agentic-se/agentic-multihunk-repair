# MCP Analysis for TOSEM Paper

This directory contains analysis scripts and results for evaluating the impact of Model Context Protocol (MCP) on bug repair for Qwen Code and Gemini CLI agents.

## Experiment Setup

- **Total bugs**: 50 randomly selected bugs from Defects4J
- **Bug list**: `50_random_bugs_for_mcp_experiments_tosem.json`
- **Agents tested**: Qwen Code and Gemini CLI
- **Configurations**: With MCP and Without MCP

## Analysis Scripts

### Repair Ability Analysis

#### Qwen Code
- **With MCP**: `qwen_mcp_repair_ability_analysis.py`
  - Input: `../qwen_code_results/qwen_results/mcp-qwen-code/qwen_repair_ability.csv`
  - Output: `qwen_mcp_repair_ability_analysis.json`

- **Without MCP**: `qwen_no_mcp_repair_ability_analysis.py`
  - Input: `../qwen_code_results/qwen_results/qwen_repair_ability.csv` (filtered to 50 bugs)
  - Output: `qwen_no_mcp_repair_ability_analysis.json`

#### Gemini CLI
- **With MCP**: `gemini_mcp_repair_ability_analysis.py`
  - Input: `../gemini_cli_results/mcp-gemini/gemini_repair_ability_mcp.csv`
  - Output: `gemini_mcp_repair_ability_analysis.json`

- **Without MCP**: `gemini_no_mcp_repair_ability_analysis.py`
  - Input: `../gemini_cli_results/gemini_repair_ability.csv` (filtered to 50 bugs)
  - Output: `gemini_no_mcp_repair_ability_analysis.json`

### Localization Success Analysis

- **Combined Script**: `calculate_no_mcp_localization_success.py`
  - Calculates localization success for both Qwen Code and Gemini CLI (without MCP) on 50 bugs
  - Output: `no_mcp_localization_success.json`

## Results Summary

### Repair Success (Accuracy)

| Agent | Without MCP | With MCP | Improvement |
|-------|-------------|----------|-------------|
| **Qwen Code** | 11/50 (22.0%) | 12/50 (24.0%) | +1 (+2%) |
| **Gemini CLI** | 20/50 (40.0%) | 26/50 (52.0%) | +6 (+12%) |

### Compile Success

| Agent | Without MCP | With MCP | Change |
|-------|-------------|----------|--------|
| **Qwen Code** | 49/50 (98.0%) | 48/50 (96.0%) | -1 (-2%) |
| **Gemini CLI** | 49/50 (98.0%) | 45/50 (90.0%) | -4 (-8%) |

### Localization Success (Without MCP only)

| Agent | Successful Localizations | Success Rate |
|-------|-------------------------|--------------|
| **Gemini CLI** | 16/50 | 32.0% |
| **Qwen Code** | 13/50 | 26.0% |

### Regression Reduction (Average)

| Agent | Without MCP | With MCP |
|-------|-------------|----------|
| **Qwen Code** | 0.31 | -1.0 |
| **Gemini CLI** | 1.0 | -70.27 |

## Key Findings

1. **MCP Impact on Repair Success**:
   - **Gemini CLI**: MCP provides significant improvement (+12%, from 40% to 52%)
   - **Qwen Code**: MCP provides marginal improvement (+2%, from 22% to 24%)

2. **MCP Trade-offs**:
   - Both agents show slight decrease in compile success with MCP
   - MCP changes WHICH bugs get fixed rather than uniformly improving success

3. **Agent Comparison**:
   - Gemini CLI outperforms Qwen Code in both configurations
   - With MCP: Gemini (52%) vs Qwen (24%)
   - Without MCP: Gemini (40%) vs Qwen (22%)

## Running the Analysis

To regenerate all results:

```bash
# Navigate to mcp_analysis directory
cd results/mcp_analysis

# Qwen analysis
python3 qwen_mcp_repair_ability_analysis.py
python3 qwen_no_mcp_repair_ability_analysis.py

# Gemini analysis
python3 gemini_mcp_repair_ability_analysis.py
python3 gemini_no_mcp_repair_ability_analysis.py

# Localization analysis (both agents)
python3 calculate_no_mcp_localization_success.py
```

## Data Files

### Input Files
- `50_random_bugs_for_mcp_experiments_tosem.json` - List of 50 bugs for MCP experiments
- `results_qwen_code_mcp.csv` - Qwen MCP results (pass/fail format)

### Output Files (JSON)
- `qwen_mcp_repair_ability_analysis.json`
- `qwen_no_mcp_repair_ability_analysis.json`
- `gemini_mcp_repair_ability_analysis.json`
- `gemini_no_mcp_repair_ability_analysis.json`
- `no_mcp_localization_success.json`

## Notes

- All metrics are calculated with 2 decimal point precision
- Regression reduction is calculated as: `failed_test_prior - failed_test_after`
  - Positive values indicate improvement (fewer failures after)
  - Negative values indicate regression (more failures after)
- Compile success: `compile_fail = 0` (for CSV format) or `compile_fail = 'No'` (for pass/fail format)
- Repair success: `repair = 1` (for CSV format) or `pass = 'Yes'` (for pass/fail format)
