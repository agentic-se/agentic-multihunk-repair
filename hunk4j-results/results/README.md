# Results Analysis

## Setup

```bash
conda env create -f environment.yml
conda activate hunk-result-analysis
```

## Qwen Repair Ability Analysis

```bash
python3 qwen_repair_ability_analysis.py
```

Generates `qwen_code_result_analysis/qwen_repair_ability_analysis.json` with compile success, repair success, and regression metrics.

## Gemini CLI Repair Ability Analysis

```bash
python3 gemini_repair_ability_analysis.py
```

Generates `gemini_cli_result_analysis/gemini_repair_ability_analysis.json` with compile success, repair success, and regression metrics.

## Claude Code Repair Ability Analysis

```bash
python3 claude_repair_ability_analysis.py
```

Generates `claude_code_result_analysis/claude_repair_ability_analysis.json` with compile success, repair success, and regression metrics.

## OpenAI Codex Repair Ability Analysis

```bash
python3 openai_codex_repair_ability_analysis.py
```

Generates `openai_codex_result_analysis/codex_repair_ability_analysis.json` with compile success, repair success, and regression metrics.

## Regression Reduction Violin Plot

```bash
python3 create_regression_violin_plot.py
```

Generates `analysis/figures/agent_regression_reduction_violin.pdf` showing the distribution of regression reduction across all four coding agents. The violin plot visualizes:
- Probability density of regression reduction outcomes
- Mean (red line) and median (blue line) values
- Variance and tail risk across agents
- Zero-change outcome frequency

Output includes statistical analysis printed to console and publication-quality PDF figure for the TOSEM paper.

## Token Consumption Violin Plots

### Cross-Agent Token Distribution

```bash
python3 create_token_violin_plots.py
```

Generates violin plots showing input and output token distributions across all four coding agents, separated by pass/fail outcomes. The script:
- Filters out bugs with duration < 30 seconds (incomplete processing)
- Creates two figures with 4 subplots each (one per agent)
- Each subplot has independent y-axis scaling for clear visualization
- Green violins represent successful repairs (pass)
- Red violins represent failed repairs (fail)

**Output files:**
- `analysis/figures/agent_input_token_distribution_violin.pdf` - Input token distributions
- `analysis/figures/agent_output_token_distribution_violin.pdf` - Output token distributions

**Console output:** Detailed statistics for each agent including sample sizes, means, and medians for both pass and fail outcomes.

**Key finding:** Failed repairs tend to consume more tokens than successful repairs across all agents, suggesting increased complexity or multiple retry attempts.

### Claude Code Cache Token Breakdown

```bash
python3 create_claude_token_violin_plot.py
```

Generates a dedicated violin plot showing Claude Code's prompt caching breakdown with three input token components:
- **New input tokens**: Uncached content unique to each request (bug-specific information)
- **Cache creation tokens**: Content written to cache for reuse (project source code, dependencies)
- **Cache read tokens**: Previously cached content retrieved in subsequent calls

The plot shows three subplots side-by-side, separated by pass/fail outcomes. This visualization reveals that cache read tokens dominate at 96% of total input volume for successful repairs.

**Output file:**
- `analysis/figures/claude_input_token_distribution_violin.pdf` - Claude cache token breakdown

## Fixed Bugs by Agent

```bash
python3 generate_fixed_bugs_by_agent.py
```

Generates `fixed_bugs_by_agent.json` with lists of bugs successfully fixed by each agent for Venn diagram analysis.

## Venn Diagram - Repair Overlap

```bash
Rscript generate_venn_diagram_agent_repair_overlap.R
```

Generates `plots/venn_diagram_agent_repair_overlap.pdf` showing overlap of bugs fixed by all four agents.

## Localization Success Analysis

```bash
python3 calculate_all_agents_localization_success.py
```

Generates `agents_localization_success.json` with localization success statistics for all coding agents:
- Qwen Code: 142 (38.17%)
- Gemini CLI: 173 (46.51%)
- OpenAI Codex: 279 (75.00%)
- Claude Code: 238 (63.98%)
