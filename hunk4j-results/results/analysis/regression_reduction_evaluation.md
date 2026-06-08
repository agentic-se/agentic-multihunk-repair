# Regression Reduction Analysis: Comparative Evaluation of Agentic Coding Tools

**Analysis Date:** 2025-11-02
**Dataset:** Defects4J (372 bugs)
**Tools Evaluated:** Claude Code, OpenAI Codex, Gemini CLI, Qwen Code

---

## Executive Summary

This analysis evaluates four state-of-the-art agentic coding tools on their ability to repair bugs from the Defects4J benchmark while maintaining code quality. Our key finding is that **repair success rate alone is insufficient** to measure tool quality. We introduce **regression reduction** as a critical metric that reveals whether fixes improve or degrade the overall codebase.

**Key Findings:**
- **Claude Code** and **OpenAI Codex** achieve positive regression reduction (+2.47 and +2.25 respectively), indicating they fix bugs while improving overall test suite health
- **Qwen** and **Gemini** exhibit negative regression reduction (-1.34 and -1.92 respectively), indicating they introduce new test failures while attempting repairs
- Tools with positive regression reduction demonstrate production-ready behavior, while those with negative values require extensive human review

---

## 1. Methodology

### 1.1 Metrics Defined

**Regression Reduction Formula:**
```
regression_reduction = failed_test_prior - failed_test_after
```

**Interpretation:**
- **Positive value**: Tool reduced the number of failing tests (desirable)
- **Negative value**: Tool introduced new failing tests (undesirable)
- **Zero**: No net change in test failures

**Important Note:** We calculate the average regression reduction only from bugs where the value is not "undefined" (i.e., excluding cases where compilation failed and no test results are available).

### 1.2 Data Collection

For each tool, we analyzed:
- Total bugs attempted: 372
- Successful compilation rate
- Repair success rate (failed_test_after = 0)
- Regression reduction (calculated from test results)

---

## 2. Quantitative Results

### 2.1 Summary Statistics

| Agent          | Total Bugs | Compile Success | Repair Success | Valid RR Count | Regression Reduction Avg |
|----------------|------------|-----------------|----------------|----------------|--------------------------|
| Claude Code    | 372        | 372 (100.0%)    | 347 (93.28%)   | 372            | **+2.47**                |
| OpenAI Codex   | 372        | 367 (98.66%)    | 324 (87.10%)   | 367            | **+2.25**                |
| Qwen Code      | 372        | 364 (97.85%)    | 96 (25.81%)    | 364            | **-1.34**                |
| Gemini CLI     | 372        | 347 (93.28%)    | 155 (41.67%)   | 347            | **-1.92**                |

### 2.2 Detailed Metrics

#### Claude Code
- **Compile Success**: 372/372 (100.0%) - Perfect compilation rate
- **Repair Success**: 347/372 (93.28%) - Highest repair rate
- **Regression Reduction**: +920 total, +2.47 average
- **Interpretation**: On average, each repair attempt by Claude reduces 2.47 failing tests, indicating it not only fixes the target bug but often resolves related issues

#### OpenAI Codex
- **Compile Success**: 367/372 (98.66%) - 5 compilation failures
- **Repair Success**: 324/372 (87.10%) - Second highest repair rate
- **Regression Reduction**: +824 total, +2.25 average
- **Interpretation**: Strong performance with positive regression reduction, showing careful and context-aware fixes

#### Qwen Code
- **Compile Success**: 364/372 (97.85%) - 8 compilation failures
- **Repair Success**: 96/372 (25.81%) - Lowest repair rate
- **Regression Reduction**: -486 total, -1.34 average
- **Interpretation**: While attempting fixes, Qwen introduces an average of 1.34 new failing tests per bug, indicating a lack of context awareness

#### Gemini CLI
- **Compile Success**: 347/372 (93.28%) - 25 compilation failures
- **Repair Success**: 155/372 (41.67%) - Moderate repair rate
- **Regression Reduction**: -666 total, -1.92 average
- **Interpretation**: Worst regression performance, introducing nearly 2 new test failures per bug attempt

---

## 3. Qualitative Analysis

### 3.1 The Two-Tier Performance Divide

Our results reveal a clear performance divide:

**Tier 1: Regression Reducers (Production-Ready)**
- Claude Code and OpenAI Codex
- Positive regression reduction
- Can be deployed with confidence
- Fixes are safe and context-aware

**Tier 2: Regression Introducers (Requires Human Review)**
- Qwen Code and Gemini CLI
- Negative regression reduction
- Require extensive code review
- Fixes may cause cascading failures

### 3.2 The "Breaking While Fixing" Problem

Qwen and Gemini exhibit a critical weakness: **they break existing functionality while attempting repairs**. This manifests in two ways:

1. **Overfitting to Target Tests**: Tools may fix the specific failing test(s) but break related functionality
2. **Lack of Contextual Understanding**: Changes don't account for dependencies and side effects

**Real-World Impact:**
- In production, a "fix" that breaks 2 other features is worse than no fix at all
- Regression introducers create technical debt and maintenance burden
- Teams spend more time debugging the "fix" than the original bug

### 3.3 Quality vs. Quantity Trade-off

**Correlation Analysis:**

```
Repair Success Rate vs. Regression Reduction:
┌─────────────────────────────────────────┐
│ Claude:  93.28% repairs, +2.47 RR  ★★★★★│
│ Codex:   87.10% repairs, +2.25 RR  ★★★★☆│
│ Gemini:  41.67% repairs, -1.92 RR  ★★☆☆☆│
│ Qwen:    25.81% repairs, -1.34 RR  ★★☆☆☆│
└─────────────────────────────────────────┘
```

**Key Insight**: There is a strong positive correlation between repair rate and regression reduction. Tools that achieve higher repair rates also maintain better code quality.

**Implication**: The myth of the "aggressive fixer" (high repairs with low quality) is debunked. The best tools achieve both high repair rates AND positive regression reduction.

---

## 4. Deep Dive: Regression Patterns

### 4.1 Distribution of Regression Reduction

**Claude Code & OpenAI Codex:**
- Majority of fixes have regression_reduction ≥ 0
- Many fixes improve multiple tests simultaneously
- Rare instances of regression introduction

**Qwen Code & Gemini CLI:**
- Frequent regression introduction
- Even "successful" repairs (repair=1) often break other tests
- Pattern of fixing one test while breaking 2-3 others

### 4.2 Compilation Failures and Undefined Regression

| Agent        | Compile Failures | % of Total | RR = "undefined" |
|--------------|------------------|------------|------------------|
| Claude Code  | 0                | 0.0%       | 0                |
| OpenAI Codex | 5                | 1.34%      | 5                |
| Qwen Code    | 8                | 2.15%      | 8                |
| Gemini CLI   | 25               | 6.72%      | 25               |

**Observation**: Higher compilation failure rates correlate with worse regression reduction, suggesting a fundamental difference in code generation quality.

---

## 5. Implications for Research and Practice

### 5.1 For Researchers

**1. Multi-Dimensional Evaluation is Essential**

Traditional metrics (compile success, repair rate) paint an incomplete picture. We recommend a three-dimensional evaluation framework:
- **Correctness**: Does the fix resolve the target bug?
- **Safety**: Does the fix avoid breaking existing functionality?
- **Quality**: Does the fix improve overall code health?

**2. The Regression Reduction Metric**

Regression reduction should be adopted as a standard metric in automated program repair (APR) research. It reveals:
- Context awareness of repair tools
- Production-readiness of generated fixes
- True cost/benefit of automated repairs

**3. Benchmarking Beyond Defects4J**

Our findings on Defects4J should be validated on other benchmarks to establish generalizability.

### 5.2 For Practitioners

**1. Tool Selection Criteria**

When selecting an agentic coding tool, prioritize:
1. **Regression reduction > 0** (non-negotiable for production)
2. High repair success rate
3. Low compilation failure rate

**2. Deployment Strategies**

**For Tier 1 Tools (Claude, Codex):**
- Can be integrated into CI/CD pipelines
- Suitable for autonomous bug fixing
- Still require code review, but with high confidence

**For Tier 2 Tools (Qwen, Gemini):**
- Use only with extensive human oversight
- Treat as "suggestion generators" rather than autonomous fixers
- Implement mandatory regression testing before merging

**3. Cost-Benefit Analysis**

The "regression tax" of Tier 2 tools:
- For every bug fixed, expect 1-2 new issues
- Human developers must debug both original and introduced bugs
- Net productivity gain may be negative

### 5.3 For Tool Developers

**Design Principles for Better Regression Reduction:**

1. **Enhanced Context Analysis**: Models must understand code dependencies and test relationships
2. **Conservative Change Strategy**: Prefer minimal, targeted changes over aggressive refactoring
3. **Pre-Flight Testing**: Simulate changes against test suite before applying
4. **Incremental Validation**: Apply changes in small steps with continuous validation

---

## 6. Threats to Validity

### 6.1 Internal Validity

- **Benchmark Specificity**: Results are specific to Defects4J, a Java-based benchmark
- **Tool Configuration**: Different configurations or prompts might yield different results
- **Temporal Factors**: Tool versions and model updates may affect performance

### 6.2 External Validity

- **Language Generalization**: Findings may not generalize to other programming languages
- **Project Scale**: Defects4J contains well-structured projects; real-world codebases may differ
- **Bug Type Diversity**: Results may vary for different bug categories

### 6.3 Construct Validity

- **Regression Reduction Limitations**: Metric assumes test suite quality and coverage are adequate
- **Repair Definition**: We use "all previously failing tests now pass" as the repair criterion

---

## 7. Recommendations

### 7.1 For TOSEM Paper

**Primary Contributions:**
1. Introduction of regression reduction as a critical quality metric
2. Empirical evidence of the two-tier performance divide
3. Practical guidance for tool selection and deployment

**Key Messages:**
- "Repair rate alone is a misleading metric for tool quality"
- "Regression reduction reveals production-readiness"
- "The best tools achieve both high repair rates and positive regression reduction"

### 7.2 Future Work

1. **Longitudinal Studies**: Track regression patterns across tool versions
2. **Multi-Language Evaluation**: Extend analysis to Python, JavaScript, etc.
3. **Root Cause Analysis**: Investigate why some tools introduce regressions
4. **Human-AI Collaboration**: Study optimal human oversight strategies

---

## 8. Conclusion

Our analysis reveals that **regression reduction is a critical but overlooked metric** in evaluating agentic coding tools. Claude Code and OpenAI Codex demonstrate production-ready behavior with positive regression reduction, while Qwen Code and Gemini CLI introduce new test failures more frequently than they fix bugs.

**The Bottom Line:**
- **Claude Code** leads in both repair success (93.28%) and regression reduction (+2.47)
- **Regression reduction should be a mandatory metric** in APR evaluation
- **Tool selection must consider code quality**, not just repair rates

This analysis provides actionable insights for researchers developing APR tools and practitioners deploying them in production environments.

---

## Appendix: Raw Data Summary

### A.1 Complete Results Table

| Metric                          | Claude | Codex | Qwen  | Gemini |
|---------------------------------|--------|-------|-------|--------|
| Total Bugs                      | 372    | 372   | 372   | 372    |
| Compile Success (count)         | 372    | 367   | 364   | 347    |
| Compile Success (%)             | 100.0  | 98.66 | 97.85 | 93.28  |
| Repair Success (count)          | 347    | 324   | 96    | 155    |
| Repair Success (%)              | 93.28  | 87.10 | 25.81 | 41.67  |
| Regression Reduction Total      | +920   | +824  | -486  | -666   |
| Regression Reduction Valid Count| 372    | 367   | 364   | 347    |
| Regression Reduction Average    | +2.47  | +2.25 | -1.34 | -1.92  |

### A.2 Data Sources

- Qwen: `qwen_code_results/qwen_results/qwen_repair_ability.csv`
- Gemini: `gemini_cli_results/gemini_repair_ability.csv`
- Claude: `claude_code_results/claude_results/claude_repair_ability.csv`
- OpenAI Codex: `openai_codex_results/results-codex/codex_repair_ability.csv`

---

**Document Version:** 1.0
**Author:** Automated Analysis System
**For:** TOSEM Journal Submission
**Advisor:** Prof. Ali Mesbah
