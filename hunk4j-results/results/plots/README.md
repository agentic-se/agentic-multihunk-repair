# Plots — Figure-by-Figure Index

Publication-quality PDFs that back the TOSEM paper figures. For end-to-end generation
commands (env setup, full pipeline), see the parent
`hunk4j-results/results/README.md`. This file is the *figure catalog*: what each PDF
shows, which script produces it, and which CSVs feed in.

All figures are computed over the **372-bug Defects4J multi-hunk dataset**, with the
exception of the MCP-comparison artifacts which use the
`mcp_analysis/50_random_bugs_for_mcp_experiments_tosem.json` subset.

## Figures

| File | Shows | Producing script | Primary inputs |
|---|---|---|---|
| `agent_divergence_violin_plot.pdf` | Per-agent distribution of hunk divergence on bugs each agent attempted (lexical / AST / file components rolled up). | `../generate_agent_divergence_violin_plot.py` | `../hunk_divergence.csv` + per-agent repair-ability CSVs |
| `agent_input_token_distribution_violin.pdf` | Per-agent input-token distribution, split pass vs fail. Filters bugs with duration < 30 s. | `../create_token_violin_plots.py` | per-agent `token_and_duration_*.csv` |
| `agent_output_token_distribution_violin.pdf` | Same as above for output tokens. Produced by the same script in a single run. | `../create_token_violin_plots.py` | per-agent `token_and_duration_*.csv` |
| `agent_regression_reduction_violin.pdf` | Distribution of regression reduction across all four agents (probability density, mean/median, zero-change mass). | `../create_regression_violin_plot.py` | per-agent localization + repair CSVs |
| `claude_input_token_distribution_violin.pdf` | Claude-specific input-token breakdown into **new / cache-creation / cache-read** components, split pass vs fail. Reveals the ~96% cache-read share on successful repairs. | `../create_claude_token_violin_plot.py` | `../claude_code_results/claude_results/token_and_duration_claude.csv` |
| `upset_plot_agent_repair_proximity.pdf` | UpSet plot: per-agent repaired-bug set overlaps, faceted by spatial proximity class (Nucleus / Cluster / Orbit / Sprawl / Fragment). | `../generate_upset_plot_agent_repair_proximity.py` | `../fixed_bugs_by_agent.json` + `../proximity_class.csv` |
| `venn_diagram_agent_repair_overlap.pdf` | Four-set Venn of bugs repaired by each agent (Claude, Codex, Gemini, Qwen). Written in **R**, not Python. | `../generate_venn_diagram_agent_repair_overlap.R` | `../fixed_bugs_by_agent.json` |

## `final_trimmed/`

Whitespace-trimmed variants of every PDF above, produced by `trim_whitespace.sh`
(runs ImageMagick `convert -density 300 -trim +repage -quality 100`). These are the
camera-ready figures consumed by the paper LaTeX in `../tosem-paper-wip/`. Regenerate
after editing any plot:

```bash
cd hunk4j-results/results/plots
./trim_whitespace.sh
```

Requires ImageMagick on PATH (`brew install imagemagick`).

## Duplicate copies under `../analysis/figures/`

Four of the violin scripts (`create_regression_violin_plot.py`,
`create_token_violin_plots.py`, `create_claude_token_violin_plot.py`) write their
outputs to `../analysis/figures/` per the docstrings — that's the working
location. The copies in this directory (`plots/`) are the curated set used by the
paper. If you edit a script and want both kept in sync, copy the regenerated PDF from
`../analysis/figures/` over the matching one here, then re-run `trim_whitespace.sh`.

## Related (not in this directory)

- `../trajectory-analysis/diagrams/tool-sequences/{gemini,qwen}_pass_fail_sequences.png` —
  tool-sequence pass/fail diagrams (PNG, not PDF). Indexed by the README in that subdir.
