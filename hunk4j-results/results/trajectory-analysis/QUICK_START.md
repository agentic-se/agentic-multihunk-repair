# Quick Start: Adding Tool Analysis to TOSEM Paper

## ✅ What's Ready

All LaTeX content for the **"Understanding agentic actions"** section is ready to paste.

## 📋 Step-by-Step Instructions

### Your Paper Currently Has:

```latex
\subsubsection{Agentic Tool Utilization}
[Content with Equation~\ref{eq:tool-calls} and Equation~\ref{eq:tool-utilization}]

\subsubsection{Tool Sequencing Pattern}
[Content with Equation~\ref{eq:tool-sequence}]

\nashid{add all the tables and visualization for tools and tool sequences}
```

### Add These 4 Items:

**1. Add new subsection** (after Tool Sequencing Pattern):
```latex
\subsubsection{Tool Diversity and Command Usage}
```
→ Copy from: `tool_utilization_section_latex.txt`

**2. Add Table** (referenced in Step 1):
```latex
\begin{table}[t]
...
\end{table}
```
→ Copy from: `unique_commands_table.txt`

**3. Add categorization subsection**:
```latex
\subsubsection{Command Categorization}
```
→ Copy from: `command_categorization_latex.txt`

**4. Add Pass/Fail table** (REPLACES old Table 5):
```latex
\begin{table*}[htbp]
...
\end{table*}
```
→ Copy from: `tool_category_pass_fail_table.txt`

**5. DELETE the old bad Table 5** with "Other (Bash)", "Testing (Bash)", etc.

## 📁 Files to Use

| File | Purpose | Size |
|------|---------|------|
| `tool_utilization_section_latex.txt` | Subsection text (connects to your metrics) | 3.5 KB |
| `unique_commands_table.txt` | Table: Unique commands per agent | 413 B |
| `command_categorization_latex.txt` | Subsection text (16 categories) | 3.7 KB |
| `tool_category_pass_fail_table.txt` | Table: Pass/Fail breakdown | 2.3 KB |

## 🎯 Key Points

- **Connects to your existing metrics**: References Equation~\ref{eq:tool-calls}
- **Native tools example**: Claude Code's `read_file`, `edit`, `glob`
- **Shell commands**: `cat`, `sed`, `grep`, `defects4j compile`
- **Table shows**: 96 unique commands (Codex) down to 38 (Gemini)
- **16 clean categories**: WRITE, READ, TEST, BUILD, etc. (no more "Other (Bash)")

## ✨ Done!

Just copy-paste those 4 items in order and delete old Table 5. All LaTeX is ready to go!
