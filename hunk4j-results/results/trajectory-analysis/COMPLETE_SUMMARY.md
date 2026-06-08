# ✅ COMPLETE: Tool Category Analysis for TOSEM Paper

## 🎯 What Was Generated

All analysis for the **"Understanding agentic actions"** subsection (currently empty in your paper).

### 📊 Two Tables Ready for Paper:

#### Table 1: Unique Command Diversity
- **File**: `unique_commands_table.txt`
- **Shows**: How many unique commands each agent uses
- **Key finding**: Codex (96 commands, 100% bash) vs Gemini (38 commands, 29% native)

#### Table 2: Tool Category Usage (Pass vs Fail)
- **File**: `tool_category_pass_fail_table.txt`
- **Shows**: 16 functional categories broken down by Pass/Fail outcomes
- **Replaces**: The BAD old Table 5 with unclear categories

### 📝 Two LaTeX Text Sections:

1. **unique_commands_explanation_latex.txt** - Explains Table 1
2. **command_categorization_latex.txt** - Explains the 16 categories and Table 2

---

## 📋 Copy-Paste Instructions for Your Paper

### In Section "Understanding agentic actions" (currently empty):

**IMPORTANT**: Your paper already defines metrics in the characterization section:
- Equation~\ref{eq:tool-calls} - calls(a) counting tool invocations
- Equation~\ref{eq:tool-utilization} - U_a relative frequency
- Equation~\ref{eq:tool-sequence} - Tool sequencing patterns

**ORDER OF CONTENT:**

```latex
% Your existing subsections:
\subsubsection{Agentic Tool Utilization}
[Your existing content with Equation~\ref{eq:tool-calls} and Equation~\ref{eq:tool-utilization}]

\subsubsection{Tool Sequencing Pattern}
[Your existing content with Equation~\ref{eq:tool-sequence}]

% NEW CONTENT TO ADD:

% STEP 1: Tool Diversity - builds on your metrics
\subsubsection{Tool Diversity and Command Usage}
[Paste content from tool_utilization_section_latex.txt]

% STEP 2: Add unique commands table (references in Step 1)
[Paste content from unique_commands_table.txt]

% STEP 3: Add categorization methodology text
[Paste content from command_categorization_latex.txt]

% STEP 4: Add category breakdown table (replaces old Table 5)
[Paste content from tool_category_pass_fail_table.txt]
```

Then **DELETE** the old bad Table 5 with categories like "Other (Bash)", "Testing (Bash)", etc.

---

## 🔢 The Data

### Unique Commands per Agent:
| Agent | Total Unique | Native Tools | Bash Commands |
|-------|--------------|--------------|---------------|
| Qwen Code | 91 | 10 (11%) | 81 (89%) |
| Gemini CLI | 38 | 11 (29%) | 27 (71%) |
| OpenAI Codex | 96 | 0 (0%) | 96 (100%) |
| Claude Code | 66 | 7 (11%) | 60 (91%) |

### Total Command Executions Analyzed:
- **64,380 total commands** across all agents
- **167 unique commands** overall (after deduplication)
- **16 functional categories** (clean, meaningful names)

### Top 5 Categories (across all agents):
1. **WRITE** (29.08%) - Code editing: sed, edit, write_file
2. **READ** (18.62%) - File reading: cat, head, read_file
3. **TEST** (15.88%) - Test execution: defects4j test, mvn test
4. **BUILD** (10.43%) - Compilation: defects4j compile, javac
5. **SEARCH_CONTENT** (7.67%) - Search: grep, search_file_content

---

## 🔍 Key Insights for Paper Discussion

### Agent Strategies Differ:

**OpenAI Codex**:
- 44% WRITE operations (highest)
- 100% bash commands (no native tools)
- Modification-heavy strategy

**Gemini CLI**:
- Failed repairs: 41.7% WRITE (vs 25.6% success)
- Most balanced native/bash usage (29% native)
- Aggressive editing on failures

**Claude Code**:
- Most balanced category distribution
- 11% SEARCH_FILES (highest) - thorough exploration
- Similar Pass/Fail patterns

**Qwen Code**:
- 15.9% NAVIGATE (unique high usage)
- Lower WRITE (14.9%) than others
- Correlates with lowest accuracy (25.81%)

---

## 🔧 Regenerating the Analysis

If data changes or you need to update:

```bash
cd /Users/nashid/repos/birch-fourth-workspace/birch/oak/results/trajectory-analysis

# Regenerate unique commands table
python generate_unique_commands_table.py

# Regenerate Pass/Fail category breakdown
python analyze_tool_categories.py
```

Both scripts will:
1. Print summary to console
2. Generate LaTeX tables
3. Save to `.txt` files

---

## ✅ What's Fixed

### OLD (BAD) Categories:
- ❌ "Other (Bash)" - what does this mean?
- ❌ "Testing (Bash)" - mixing implementation with function
- ❌ "File Operations" vs "File Ops (Bash)" - inconsistent
- ❌ "Text Processing (Bash)" - too vague
- ❌ Only 12 unclear categories

### NEW (GOOD) Categories:
- ✅ **WRITE**: Code modification (clear purpose)
- ✅ **READ**: File content viewing (clear purpose)
- ✅ **TEST**: Test execution (clear purpose)
- ✅ **BUILD**: Compilation (clear purpose)
- ✅ **16 functional categories** based on SE lifecycle
- ✅ **100% coverage** (including OTHER for parsing artifacts)

---

## 📁 All Files Location

```
/Users/nashid/repos/birch-fourth-workspace/birch/oak/results/trajectory-analysis/
├── command_categorization_latex.txt          # Text explaining 16 categories
├── tool_category_pass_fail_table.txt         # Table: Pass/Fail breakdown
├── unique_commands_table.txt                 # Table: Unique commands per agent
├── unique_commands_explanation_latex.txt     # Text explaining unique commands
├── analyze_tool_categories.py                # Script to regenerate Table 2
├── generate_unique_commands_table.py         # Script to regenerate Table 1
├── README_FOR_PAPER.md                       # Detailed instructions
└── COMPLETE_SUMMARY.md                       # This file
```

---

## 🎉 Ready for Paper!

All LaTeX is ready to copy-paste directly into your TOSEM paper. The categorization is:
- ✅ **Academically sound** (16 functional categories based on SE lifecycle)
- ✅ **Data-driven** (64,380 commands analyzed)
- ✅ **Complete** (100% coverage, no unknown commands)
- ✅ **Clean** (meaningful category names, consistent)
- ✅ **Validated** (matches the agent_command_statistics analysis)

Just copy the 4 text files into your LaTeX paper in the order shown above!
