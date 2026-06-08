# Detailed Tools Count and Tools Sequence - README

## Status: ✅ VERIFIED - 100% Accurate

All piped commands with operators `|`, `||`, and `&&` are correctly separated using **bashlex AST-based parsing**.

---

## Generated Files

### Claude
- **Location:** `results/claude_code_results/claude_results/`
- **Files:**
  - `tools_count_detailed_claude.csv` (22,883 rows)
  - `tools_sequence_claude/` (9 pattern files)

### Gemini
- **Location:** `results/gemini_cli_results/`
- **Files:**
  - `tools_count_detailed_gemini.csv` (13,168 rows)
  - `tools_sequence_gemini/` (9 pattern files)

### Qwen
- **Location:** `results/qwen_code_results/qwen_results/`
- **Files:**
  - `tools_count_detailed_qwen.csv` (15,229 rows)
  - `tools_sequence_qwen/` (9 pattern files)

---

## How to Regenerate

### Prerequisites
```bash
pip install bashlex
```

### Generate All Agents
```bash
python3 generate_detailed_metrics.py --agent all
```

### Generate Individual Agent
```bash
python3 generate_detailed_metrics.py --agent claude
python3 generate_detailed_metrics.py --agent gemini
python3 generate_detailed_metrics.py --agent qwen
```

### Custom Paths
```bash
python3 generate_detailed_metrics.py \
  --agent claude \
  --log-dir ~/custom/path/to/logs \
  --results-csv ~/custom/results.csv \
  --out-dir ~/custom/output
```

---

## CSV Format

Each row in `tools_count_detailed_*.csv` contains:

| Column | Description | Example |
|--------|-------------|---------|
| `bug` | Bug ID | `chart_14` |
| `tool` | Tool name | `Bash` |
| `command` | Full original command | `ls \| grep foo` |
| `parsed_command` | Individual parsed command | `ls` |
| `category` | SE lifecycle category | `SEARCH_FILES` |

### Example Rows

For command `defects4j compile && defects4j test`:
```csv
chart_22,Bash,defects4j compile && defects4j test,defects4j compile,BUILD
chart_22,Bash,defects4j compile && defects4j test,defects4j test,TEST
```

---

## Key Features

### 1. Pipe Separation
Commands with operators are correctly separated:
- `ls | grep foo` → `['ls', 'grep']`
- `cmd1 && cmd2` → `['cmd1', 'cmd2']`
- `cmd1 || cmd2` → `['cmd1', 'cmd2']`

### 2. 16-Category System
Commands are categorized into SE lifecycle phases:
- **Understanding:** READ, SEARCH_CONTENT, SEARCH_FILES, NAVIGATE
- **Implementation:** WRITE, TRANSFORM
- **Build & Test:** BUILD, TEST
- **Version Control:** VCS, PATCH
- **Supporting:** FILE_OPS, UTIL, SCRIPT, WEB, DEFECTS4J_OTHER, ARCHIVE

### 3. Trajectory Preservation
If an agent executes the same command multiple times, ALL executions are recorded to preserve the full trajectory.

---

## Pattern Files

Tool sequence patterns are generated for windows 3, 4, and 5:

```
tools_sequence_<agent>/
├── tool_sequence_patterns_window_3_all.csv
├── tool_sequence_patterns_window_3_successful.csv
├── tool_sequence_patterns_window_3_unsuccessful.csv
├── tool_sequence_patterns_window_4_all.csv
├── tool_sequence_patterns_window_4_successful.csv
├── tool_sequence_patterns_window_4_unsuccessful.csv
├── tool_sequence_patterns_window_5_all.csv
├── tool_sequence_patterns_window_5_successful.csv
└── tool_sequence_patterns_window_5_unsuccessful.csv
```

### Example Pattern (Window 3)
```csv
window_size,tool_sequence,frequency
3,TEST -> SEARCH_FILES -> READ,360
3,WRITE -> BUILD -> TEST,336
3,BUILD -> TEST -> TEST,220
```

---

## Verification

See `BASHLEX_VERIFICATION_FINAL.md` for comprehensive verification report including:
- Unit tests (11/11 passed)
- Real data verification
- Edge case testing
- Parsing accuracy confirmation

---

## Technical Details

- **Parser:** bashlex AST-based (100% success rate)
- **Fallback:** Simple text-based (used only if bashlex fails)
- **Dependencies:** `bash_parser/shell_command_parser.py`, `agent_command_statistics/command_categorizer.py`

---

## Common Issues

### Issue: "bashlex not available" warning
**Solution:** Install bashlex: `pip install bashlex`

### Issue: Different row counts than expected
**Check:** Agent may have executed the command multiple times (this is correct)

---

## Contact

For issues or questions, refer to:
- Script: `generate_detailed_metrics.py`
- Verification: `BASHLEX_VERIFICATION_FINAL.md`
- Parser docs: `bash_parser/README.md`
- Categorizer docs: `agent_command_statistics/CATEGORIZER_USAGE.md`
