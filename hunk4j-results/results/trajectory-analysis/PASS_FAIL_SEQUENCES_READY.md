# ✅ Tool Sequence Analysis: Pass vs Fail - COMPLETE

## Files Generated

### Visualizations (300 DPI):
1. **`qwen_pass_fail_sequences.png`** - Qwen Successful vs Unsuccessful
2. **`gemini_pass_fail_sequences.png`** - Gemini Successful vs Unsuccessful

### LaTeX Content:
3. **`tool_sequences_pass_fail_latex.tex`** - Complete subsection text with analysis
4. **`figure_captions_pass_fail.tex`** - Both figure captions

### Script:
5. **`visualize_pass_fail_sequences.py`** - Regeneration script

---

## Key Findings

### Qwen Code: Structural Failure
- **Successful**: NAVIGATE → TEST → NAVIGATE (4.13%)
- **Unsuccessful**: NAVIGATE → TEST → NAVIGATE (2.93%)
- **Insight**: Navigation overhead in BOTH outcomes
- **Conclusion**: Structural constraint, not behavioral adaptation

### Gemini CLI: Behavioral Failure
- **Successful**: WRITE → BUILD → TEST (9.09%) - proper cycle!
- **Unsuccessful**: WRITE → WRITE → WRITE (10.37%) - batching!
- **Difference**: +5.75% more consecutive writes when failing (2.24x increase)
- **Conclusion**: Adapts poorly under difficulty

---

## The Story

**Two Distinct Failure Modes:**

1. **Qwen** = **Structural Constraint**
   - Navigation overhead regardless of outcome
   - Cannot succeed without this inefficiency
   - Low accuracy due to consistent fragmentation

2. **Gemini** = **Behavioral Adaptation**
   - Changes strategy when struggling
   - Shifts from WRITE→BUILD→TEST to WRITE→WRITE→WRITE
   - Adaptation is counterproductive (batches errors)

**Implication**: Different agents need different fixes
- Qwen: Architectural changes to reduce navigation
- Gemini: Behavioral reinforcement to prevent batching

---

## LaTeX Integration

### Add to paper after Pass/Fail tool category analysis:

```latex
\subsubsection{Tool Sequence Patterns in Successful vs Unsuccessful Repairs}
[Paste from tool_sequences_pass_fail_latex.tex]

[Insert Figure: qwen_pass_fail_sequences.png]
[Insert Figure: gemini_pass_fail_sequences.png]
```

### Figure placement:
- Copy PNGs to `figures/` directory
- Use captions from `figure_captions_pass_fail.tex`

---

## Data Statistics

### Qwen Successful (n=3,557):
1. NAVIGATE → TEST → NAVIGATE (4.13%)
2. TEST → NAVIGATE → TEST (3.43%)
3. READ → READ → READ (3.32%)
4. WRITE → NAVIGATE → BUILD (2.64%)
5. READ → SEARCH_CONTENT → READ (2.59%)

### Qwen Unsuccessful (n=10,877):
1. NAVIGATE → TEST → NAVIGATE (2.93%)
2. WRITE → NAVIGATE → BUILD (2.86%)
3. NAVIGATE → BUILD → NAVIGATE (2.51%)
4. READ → READ → READ (2.45%)
5. TEST → NAVIGATE → TEST (2.13%)

### Gemini Successful (n=3,587):
1. WRITE → BUILD → TEST (9.09%)
2. READ → WRITE → BUILD (4.74%)
3. BUILD → TEST → READ (4.71%)
4. WRITE → WRITE → WRITE (4.63%)
5. WRITE → WRITE → BUILD (4.52%)

### Gemini Unsuccessful (n=9,033):
1. WRITE → WRITE → WRITE (10.37%) ⚠️
2. WRITE → BUILD → TEST (8.48%)
3. WRITE → READ → WRITE (6.06%)
4. WRITE → WRITE → BUILD (4.46%)
5. READ → WRITE → READ (4.27%)

---

## Why This is Better Than "Total"

Showing **Pass vs Fail** reveals:

✅ **Qwen**: Same patterns regardless → structural problem
✅ **Gemini**: Dramatic shift → behavioral problem
✅ **Actionable insights**: Different interventions needed
✅ **Novel finding**: 2.24x increase in batching when Gemini fails

Showing "Total" would just show average patterns and miss these insights!

---

## TOSEM Contribution

This completes the trajectory characterization:

1. **Tool diversity** (Section 1): What tools agents have
2. **Tool allocation** (Section 2): How much of each category (Pass vs Fail)
3. **→ Tool sequences** (Section 3): How tools are combined (Pass vs Fail)

Together = comprehensive picture of agent behavior and failure modes.

---

**Ready for TOSEM!** 🎯
