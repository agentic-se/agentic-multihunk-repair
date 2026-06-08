# Tool Sequence Pattern Visualizations

This directory contains visualizations comparing successful vs unsuccessful tool sequence patterns for Qwen and Gemini agents.

## Generated Visualizations

### 1. Qwen Pass vs Fail Sequences
**File**: `qwen_pass_fail_sequences.png`

Side-by-side comparison of the top 5 most frequent tool sequence patterns (window size = 3) for:
- **Left panel (Green)**: Successful task completions
- **Right panel (Red)**: Unsuccessful task completions

### 2. Gemini Pass vs Fail Sequences
**File**: `gemini_pass_fail_sequences.png`

Side-by-side comparison of the top 5 most frequent tool sequence patterns (window size = 3) for:
- **Left panel (Green)**: Successful task completions
- **Right panel (Red)**: Unsuccessful task completions

## Tool Abbreviations

The visualizations use abbreviated tool names for clarity:
- **SF**: SEARCH_FILES
- **SC**: SEARCH_CONTENT
- **NAV**: NAVIGATE
- **WR**: WRITE
- **BLD**: BUILD
- **RD**: READ
- **TST**: TEST

## Visualization Features

### Design Improvements
- ✅ Pattern text displayed INSIDE bars for maximum space utilization
- ✅ Frequency counts with percentages displayed inside/outside bars depending on space
- ✅ No y-axis labels (patterns shown directly in bars)
- ✅ Professional muted green (#81C784) and red (#E57373) color scheme
- ✅ Tight x-axis limits for compact display
- ✅ Clean borders with visible spines
- ✅ Horizontal bar charts for better readability

### Key Differences: Qwen vs Gemini
- **Qwen**: All text (patterns and frequencies) placed inside bars for ultra-compact layout
- **Gemini**: Top bar frequencies inside, remaining bars' frequencies outside for better readability with smaller bars

## Data Sources

### Qwen Data
- **Pass**: `../qwen_code_results/qwen_results/tools_sequence_qwen/tool_sequence_patterns_window_3_successful.csv`
- **Fail**: `../qwen_code_results/qwen_results/tools_sequence_qwen/tool_sequence_patterns_window_3_unsuccessful.csv`

### Gemini Data
- **Pass**: `../../results/gemini_cli_results/tools_sequence_gemini/tool_sequence_patterns_window_3_successful.csv`
- **Fail**: `../../results/gemini_cli_results/tools_sequence_gemini/tool_sequence_patterns_window_3_unsuccessful.csv`

## Generating Visualizations

To regenerate these visualizations, run:

```bash
cd trajectory-analysis
python visualize_pass_fail_sequences.py
```

The script will:
1. Load tool sequence pattern data for both agents
2. Calculate frequencies and percentages
3. Generate side-by-side pass/fail comparison plots
4. Save high-resolution (300 DPI) PNG files to this directory

## Script Details

**Script**: `../../visualize_pass_fail_sequences.py`

Key parameters:
- **Figure size**: 14x5 inches (wide format for side-by-side comparison)
- **Bar height**: 0.9 (tight spacing)
- **DPI**: 300 (publication quality)
- **Top N patterns**: 5 (most frequent)
- **X-axis multipliers**:
  - Qwen: 1.01 (1% padding)
  - Gemini: 1.015 (1.5% padding for outside labels)

## Usage in Papers

These visualizations are designed for academic paper submission with:
- High resolution (300 DPI)
- Professional color scheme (colorblind-friendly)
- Clear labeling and minimal clutter
- Compact layout for space-constrained publications
