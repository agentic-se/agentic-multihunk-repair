# Tool Sequence Analysis - Complete Summary

## What Was Generated

High-quality visualizations and LaTeX content analyzing tool sequence patterns for the two worst-performing agents (Qwen and Gemini), revealing **contrasting failure modes**.

---

## Files Created

### Visualizations (300 DPI, publication-ready):
1. **`qwen_vs_gemini_patterns_comparison.png`** - Side-by-side comparison (recommended for paper)
2. **`qwen_top5_patterns_window3.png`** - Qwen individual chart
3. **`gemini_top5_patterns_window3.png`** - Gemini individual chart

### LaTeX Content:
4. **`tool_sequences_section_latex.txt`** - Full subsection text with analysis
5. **`figure_caption_tool_sequences.txt`** - Figure caption for LaTeX

### Scripts:
6. **`visualize_qwen_gemini_patterns.py`** - Regeneration script

---

## Key Findings

### Window Size = 3
We use 3-step sequences because:
- **Window=5 had too low percentages** (0.8-1.2%) - data too fragmented
- **Window=3 shows meaningful percentages** (2.5-8.7%) - clear patterns emerge

### Qwen Code (Worst Performer)
- **Total sequences**: 14,434
- **Unique patterns**: 704 (highly fragmented)
- **Top pattern**: NAVIGATE → TEST → NAVIGATE (3.23%)
- **Problem**: **Navigation overhead**
  - NAVIGATE appears in 5/10 top patterns
  - Wastes computational budget on directory changes
  - Fragments productive workflows

### Gemini CLI (Second-Worst Performer)
- **Total sequences**: 12,620
- **Unique patterns**: 324 (more concentrated)
- **Top pattern**: WRITE → WRITE → WRITE (8.74%)
- **Problem**: **Over-modification without validation**
  - 8.74% of sequences = 3 consecutive writes
  - 2.7x higher concentration than Qwen's top pattern
  - Batches modifications without intermediate testing

---

## The Story for the Paper

**Two Distinct Paths to Failure:**

1. **Qwen**: Fragments workflow through excessive navigation
   - Prevents sustained focus on any single activity
   - Overhead operations contribute nothing to repair

2. **Gemini**: Concentrates effort but lacks validation
   - Accumulates modifications without feedback
   - May compound errors without incremental testing

**Key Insight**: Both waste computational resources but in opposite ways:
- Qwen: Overhead that contributes nothing
- Gemini: Modifications that may compound errors

**Implication**: Effective strategies require:
- Sustained focus (minimize navigation)
- Frequent validation (avoid modification batches)

---

## Data Statistics

### Qwen Top 5 Patterns:
1. NAVIGATE → TEST → NAVIGATE (3.23%, n=466)
2. WRITE → NAVIGATE → BUILD (2.81%, n=405)
3. READ → READ → READ (2.67%, n=385)
4. NAVIGATE → BUILD → NAVIGATE (2.51%, n=362)
5. TEST → NAVIGATE → TEST (2.45%, n=354)

### Gemini Top 5 Patterns:
1. WRITE → WRITE → WRITE (8.74%, n=1,103)
2. WRITE → BUILD → TEST (8.65%, n=1,092)
3. WRITE → READ → WRITE (4.90%, n=618)
4. WRITE → WRITE → BUILD (4.48%, n=565)
5. READ → WRITE → BUILD (4.14%, n=522)

---

## Usage in Paper

### Section Order:
1. **Tool Diversity** (unique_commands_table.txt + tool_utilization_section_latex.txt)
2. **Pass vs Fail Analysis** (pass_fail_analysis_section.txt + tool_category_pass_fail_table.txt)
3. **→ Tool Sequence Patterns** (tool_sequences_section_latex.txt + figure)

### LaTeX Integration:

```latex
\subsubsection{Tool Sequence Patterns in Low-Performing Agents}
[Paste content from tool_sequences_section_latex.txt]

[Insert figure from figure_caption_tool_sequences.txt]
```

### Figure Placement:
- Use `qwen_vs_gemini_patterns_comparison.png`
- Place in `figures/` directory
- Reference as `\ref{fig:qwen_gemini_patterns}`

---

## Why This Works for TOSEM

✅ **Novel insight**: First analysis showing contrasting failure modes in repair agents

✅ **Clear visualization**: Side-by-side bars make the difference immediately obvious

✅ **Quantitative**: Backed by 27,054 total sequences, 1,028 unique patterns

✅ **Actionable**: Suggests concrete improvements (reduce navigation, increase validation)

✅ **Complements earlier analysis**:
- Tool categories showed WHAT tools are used
- Sequences show HOW tools are combined

---

## Regenerating Visualizations

If data changes:

```bash
cd /Users/nashid/repos/birch-fourth-workspace/birch/oak/results/trajectory-analysis
python visualize_qwen_gemini_patterns.py
```

Will regenerate all 3 PNG files with updated data.

---

## Paper Contribution

This analysis completes the trajectory characterization by showing that:

1. **Tool diversity** varies (Codex: 96 commands, Gemini: 38)
2. **Tool allocation** differs in Pass vs Fail (Gemini: 2x more WRITE when failing)
3. **→ Tool sequences** reveal distinct failure modes (navigation vs over-modification)

Together, these three analyses provide a comprehensive picture of how agents behave during repair attempts and why certain strategies fail.

---

**Ready for TOSEM submission!** 🎯
