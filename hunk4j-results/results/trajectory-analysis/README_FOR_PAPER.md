# Tool Category Analysis for TOSEM Paper

## Generated Files

### Main Analysis Files:
1. **command_categorization_latex.txt** - LaTeX subsection explaining the categorization methodology
2. **tool_category_pass_fail_table.txt** - LaTeX table with Pass/Fail breakdown by category (Table 5)
3. **unique_commands_table.txt** - LaTeX table showing unique command counts per agent
4. **unique_commands_explanation_latex.txt** - LaTeX text explaining the unique commands table

### Python Scripts (can regenerate):
5. **analyze_tool_categories.py** - Generates the Pass/Fail category breakdown table
6. **generate_unique_commands_table.py** - Generates the unique commands per agent table

## What to Add to the Paper

### Step 1: Add Command Diversity Analysis (NEW)

Add the content from `unique_commands_explanation_latex.txt` at the beginning of **Section: Understanding agentic actions**.

Then insert the table from `unique_commands_table.txt`:
```latex
\begin{table}[t]
\centering
\caption{Unique Command Diversity Across Coding Agents}
\label{tab:unique_commands_per_agent}
...
\end{tabular}
\end{table}
```

This explains:
- Native tools vs Bash commands
- How agents differ in their tool usage (Codex: 100% bash, Gemini: more balanced)
- Command diversity (38-96 unique commands per agent)

### Step 2: Add the Categorization Methodology Subsection

Insert the content from `command_categorization_latex.txt` after the command diversity section.

This subsection explains:
- How commands are categorized (native tools vs bash commands)
- The 16 high-level functional categories
- The 4 major operational phases
- How the categorization enables comparison of Pass vs Fail repairs

### Step 3: Replace the OLD Table 5

**REMOVE this old table:**
```latex
\begin{table*}[htbp]
...
Other (\textit{Bash}) & 24.2 & 25.5 & 25.3 & 22.6 & 19.7 & 20.4 ...
Testing (\textit{Bash}) & 21.4 & 19.8 & 20.2 & 40.0 & 35.4 & 36.5 ...
File Operations & 25.6 & 23.7 & 24.1 & 16.8 & 16.4 & 16.5 ...
...
\end{table*}
```

**REPLACE with the NEW table** from `tool_category_pass_fail_table.txt`

The new table has:
- Clean, meaningful category names (WRITE, READ, TEST, BUILD, etc.)
- Data for ALL 4 agents (Qwen, Gemini, Codex, Claude)
- 16 functional categories based on SE lifecycle phases
- 100% of commands categorized (including parsing artifacts in OTHER)

## Key Improvements Over Old Table

### Old Categories (BAD):
- "Other (Bash)" - unclear what this means
- "Testing (Bash)" - mixing implementation with functionality
- "File Operations" vs "File Ops (Bash)" - inconsistent
- "Text Processing (Bash)" - vague
- Only 12 categories, many unclear

### New Categories (GOOD):
- **WRITE**: Code editing/modification (sed, edit, write_file)
- **READ**: File content viewing (cat, head, read_file)
- **TEST**: Test execution (defects4j test, mvn test)
- **BUILD**: Compilation (defects4j compile, javac)
- **SEARCH_CONTENT**: Content search (grep, search_file_content)
- **SEARCH_FILES**: File system queries (ls, find, glob)
- **VCS**: Version control (git diff, git show)
- Plus 9 more clear, functional categories
- 16 total categories covering SE lifecycle

## Unique Commands Summary

**Key Finding**: Agents use different numbers of unique commands:
- **OpenAI Codex**: 96 unique commands (100% bash, 0% native)
- **Qwen Code**: 91 unique commands (89% bash, 11% native)
- **Claude Code**: 66 unique commands (91% bash, 9% native)
- **Gemini CLI**: 38 unique commands (71% bash, 29% native)

**Insight**: Codex uses the most diverse toolset but relies entirely on bash. Gemini uses the smallest toolset but has the most native tool integration.

## Total Commands Executed Summary

### Total Commands Analyzed by Agent:
- **Qwen Code**: 15,074 commands
- **Gemini CLI**: 13,149 commands
- **OpenAI Codex**: 17,068 commands
- **Claude Code**: 19,089 commands
- **TOTAL**: 64,380 command executions

### Unique Commands: 167

### Top Categories Across All Agents:
1. **WRITE** - 29.08% (code editing)
2. **READ** - 18.62% (file reading)
3. **TEST** - 15.88% (test execution)
4. **BUILD** - 10.43% (compilation)
5. **SEARCH_CONTENT** - 7.67% (grep, search)

## Interesting Findings from the Table

### Gemini CLI:
- **Failed repairs use 41.7% WRITE** vs 25.6% for successful repairs
- Suggests unsuccessful attempts involve more aggressive editing

### OpenAI Codex:
- **44.6% WRITE operations** (highest across all agents)
- Heavy reliance on code modification
- Only 5.6% READ (much lower than others)

### Claude Code:
- **Most balanced** distribution across categories
- High SEARCH_FILES usage (11.0%) - thorough codebase exploration
- Similar Pass/Fail distributions (less variation than others)

### Qwen Code:
- **High NAVIGATE usage** (15.9%) - lots of directory changes
- Lower WRITE usage (14.9%) compared to other agents
- This correlates with its lower repair accuracy (25.81%)

## Next Steps

1. ✅ Copy `command_categorization_latex.txt` content into the paper subsection
2. ✅ Replace old Table 5 with content from `tool_category_pass_fail_table.txt`
3. ✅ Add interpretation/discussion of the results in the paper text
4. Consider: Create visualization figures showing category distributions
5. Consider: Add statistical tests comparing Pass vs Fail distributions

## Files Location

All generated files are in:
```
/Users/nashid/repos/birch-fourth-workspace/birch/oak/results/trajectory-analysis/
```

## Regenerating the Analysis

If you need to update the data:
```bash
cd /Users/nashid/repos/birch-fourth-workspace/birch/oak/results/trajectory-analysis
python analyze_tool_categories.py
```

This will regenerate both the table and the summary statistics.
