# Hunk Poly

Figure pipeline for the **merged PolyHunk dataset** —
**404 multi-hunk instances** = 372 Defects4J (Hunk4J) + 32 SWE-bench Verified
(HunkSWE). The four figure scripts here are byte-identical copies of the Hunk4J
analysis code (see `../hunk4j-results/`); they consume seven input files with
fixed filenames and column schemas, so refreshing the inputs and re-running
`./generate_all_plots.sh` regenerates every figure with no script edits.

The seven input files shipped here already cover all 404 instances. They are the
output of `../build_hunkpoly_files.py`, which projects per-bug rows out of the
unified `../hunkDS.csv` dataset (built by `../build_hunkds.py` from the per-agent
Hunk4J + HunkSWE results).

```
build_hunkds.py  ──►  hunkDS.csv  ──►  build_hunkpoly_files.py  ──►  hunk-poly/{7 inputs}
                                                                            │
                                                                            ▼
                                                                  generate_all_plots.sh
                                                                            │
                                                                            ▼
                                                                       plots/*.pdf
```

## Inputs (404-instance schema)

Each row is keyed by `bug_id`. Defects4J IDs look like `Chart_14`, SWE-bench IDs
look like `django__django-15128`. Every input contains all 404 rows; agents that
weren't run on a given instance show up as `0` / empty repair flags.

| Input file | Schema | Consumed by |
|---|---|---|
| `fixed_bugs_by_agent.json` | `{agent: [bug_id, ...]}` over `gemini_cli`, `qwen_code`, `claude_code`, `openai_codex` | Venn diagram, Fig. 3 (UpSet), Fig. 4 (divergence) |
| `proximity_class.csv` | `bug_id, proximity_class` (Nucleus / Cluster / Orbit / Sprawl / Fragment) | Fig. 3 (UpSet) |
| `hunk_divergence.csv` | `bug_id, hunk_count, divergence` (lexical + AST + file distance) | Fig. 4 (divergence) |
| `qwen_code_results/qwen_results/qwen_repair_ability.csv` | `bug_id, repair, failed_test_prior, failed_test_after, regression_reduction, compile_fail` | Fig. 5 (regression reduction) |
| `gemini_cli_results/gemini_repair_ability.csv` | same schema | Fig. 5 (regression reduction) |
| `openai_codex_results/results-codex/codex_repair_ability.csv` | same schema | Fig. 5 (regression reduction) |
| `claude_code_results/claude_results/claude_repair_ability.csv` | same schema | Fig. 5 (regression reduction) |

To refresh the inputs (e.g. after a new evaluation run), regenerate `hunkDS.csv`
upstream and re-run `python3 ../build_hunkpoly_files.py` from the repo root —
filenames, headers, and directory layout must stay byte-identical because the
figure scripts hard-code these paths.

`polyhunk_bugs.json` is the hunk-poly bug-list metadata (the dataset itself); it
is **not** an input to the figure scripts.

### Known data gaps

`qwen_code_results/qwen_results/qwen_repair_ability.csv` has empty
`regression_reduction` and `compile_fail` fields for 4 SWE-bench instances
(`astropy__astropy-14598`, `astropy__astropy-8707`, `django__django-12406`,
`django__django-15572`) because the **vanilla** Qwen SWE-bench run is missing
`workspace_docker/<instance>/` directories for them — `build_hunkpoly_files.py`
can't derive the two fields without `swebench_report.json`. The MCP variant of
Qwen ran all four. Fig. 5 skips these 4 rows (treating empty == legacy
`"undefined"`), dropping Qwen's regression-violin sample from 404 to 392 (a
further −8 already came from compile-fail `"undefined"` rows).

Tracked in issue [#131](https://github.com/nashid/agentic-multihunk-repair/issues/131).

## Contents

| File | Purpose |
|---|---|
| `generate_venn_diagram_agent_repair_overlap.R` | Venn diagram of 4-agent fixed-bug overlap |
| `generate_upset_plot_agent_repair_proximity.py` | **Fig. 3** — UpSet plot of agent intersections × spatial proximity class |
| `generate_agent_divergence_violin_plot.py` | **Fig. 4** — faceted violins of hunk divergence, Pass vs Fail per agent |
| `create_regression_violin_plot.py` | **Fig. 5** — regression-reduction distribution per agent |
| `create_token_violin_plots.py` | **Figs. 6 & 7** — input / output token-consumption violins per agent (Pass vs Fail). Byte-identical copy from `oak/results/`. |
| `create_claude_token_violin_plot.py` | **Fig. 8** — Claude-only New Input / Cache Creation / Cache Read token distributions (Pass vs Fail). Byte-identical copy from `oak/results/`. |
| `trajectory-analysis/visualize_pass_fail_sequences.py` | **Figs. 9 & 10** — Pass vs Fail bar charts of top-5 tool-sequence patterns for Qwen and Gemini at window-3. Byte-identical copy from `oak/results/trajectory-analysis/`. |
| `trajectory-analysis/generate_sequence_plots.py` | Wrapper that imports the unchanged plot function above and renders any combination of `--windows {3,4,5}` × `--agents {qwen,gemini,claude,codex}` |
| `generate_all_plots.sh` | One-shot driver that runs all four figure scripts in sequence |
| `verify_violin_stats.py` | Read-only verification of the divergence (Fig. 4) violin data + §4.6 prose against Table 4 anchors |
| `verify_regression_stats.py` | Read-only verification of the regression-reduction (Fig. 5) violin data + §4.7 prose against Table 3 anchors |
| `generate_proximity_class_table.py` | Regenerate LaTeX for `tab:proximity_class:hunk-poly` (per-class counts + mean hunk divergence × Hunk4J / HunkSWE / PolyHunk) from `proximity_class.csv` + `hunk_divergence.csv` |
| `trim_plots.sh` | Lossless `pdfcrop` pass over `plots/*.pdf` — writes tight-bbox copies to `plots/trimmed/` |
| Input CSVs/JSON | See the *Inputs* table above |
| `plots/*.pdf` | Pre-generated figure PDFs for the 404-instance dataset — see *Pre-generated PDFs* below |
| `plots/trimmed/*.pdf` | Same figures with whitespace margins trimmed (vector, lossless) for paper inclusion |
| `polyhunk_bugs.json` | hunk-poly bug-list metadata (dataset, not a script input) |
| `<agent>_*/token_and_duration_<agent>.csv` | 404-row merged token + duration CSVs per agent — inputs for Figs. 6/7/8 |
| `<agent>_*/tools_sequence_<agent>/tool_sequence_patterns_window_{3,4,5}_{all,successful,unsuccessful}.csv` | 36 merged tool-sequence pattern CSVs (4 agents × 3 windows × 3 buckets) — inputs for Figs. 9/10 |

## Prerequisites

- **Python 3.8+** with `pandas`, `numpy`, `matplotlib`, `seaborn` (used by Figs. 3, 4, 5).
- **R 4.0+** with `VennDiagram` and `jsonlite` (used by the Venn diagram). Install once:

  ```bash
  Rscript -e 'install.packages(c("VennDiagram","jsonlite"), repos="https://cloud.r-project.org")'
  ```
- **`pdfcrop`** (optional — only needed for `trim_plots.sh`). Ships with TeX Live / MacTeX:

  ```bash
  # macOS:
  brew install --cask mactex-no-gui
  # Linux:
  sudo apt-get install texlive-extra-utils
  ```

## How to run

All four scripts assume the working directory is `hunk-poly/` and write their PDFs
to `plots/`. The simplest way to (re)generate every figure is the one-shot driver:

```bash
cd hunk-poly
./generate_all_plots.sh
```

`generate_all_plots.sh` `cd`s into `hunk-poly/` itself, creates `plots/`, runs the
four scripts in order (Venn → Fig. 3 → Fig. 4 → Fig. 5), exits non-zero on the first
failure (`set -euo pipefail`), and forces `MPLBACKEND=Agg` for the regression-
reduction script so it works on headless systems.

To re-run an individual figure:

```bash
cd hunk-poly
mkdir -p plots

# Venn — 4-agent fixed-bug overlap
Rscript generate_venn_diagram_agent_repair_overlap.R

# Fig. 3 — UpSet × proximity class
python3 generate_upset_plot_agent_repair_proximity.py

# Fig. 4 — divergence violins, Pass vs Fail
python3 generate_agent_divergence_violin_plot.py

# Fig. 5 — regression reduction (use MPLBACKEND=Agg on headless systems —
# the script calls plt.show())
MPLBACKEND=Agg python3 create_regression_violin_plot.py
```

Each script prints summary statistics to stdout so you can sanity-check that the
inputs were picked up correctly.

## Figs. 6, 7, 8 — token consumption violins

These three figures are produced by two **unmodified** scripts copied from
`oak/results/`. The inputs are merged 404-row `token_and_duration_<agent>.csv`
files built once by `../build_polyhunk_token_csvs.py` (which combines the d4j
372-row per-agent CSVs with the 32 HunkSWE per-bug values, preserving each
agent's exact d4j schema and unit convention so the plot scripts run as-is).

```bash
# 1. (Re)build merged token+duration CSVs (one per agent, 404 rows each)
cd /path/to/agentic-multihunk-repair
python3 build_polyhunk_token_csvs.py

# 2. Plot Figs. 6 & 7 (input-token + output-token violins, 4 panels each)
cd hunk-poly
python3 create_token_violin_plots.py

# 3. Plot Fig. 8 (Claude New Input / Cache Creation / Cache Read, 3 panels)
python3 create_claude_token_violin_plot.py
```

PDFs land in `hunk-poly/analysis/figures/`:

- `agent_input_token_distribution_violin.pdf` (Fig. 6)
- `agent_output_token_distribution_violin.pdf` (Fig. 7)
- `claude_input_token_distribution_violin.pdf` (Fig. 8)

The same `<30 s` lower duration filter the paper's analysis uses is applied
verbatim — no modifications to the plot scripts.

## Figs. 9, 10 — tool sequence patterns (window-configurable)

Top-5 n-gram patterns of categorized actions, separated by Pass / Fail. The
paper uses window-3; window-4 and window-5 are available for comparison.

```bash
# 1. (Re)build merged tool-sequence pattern CSVs for windows 3, 4, 5
cd /path/to/agentic-multihunk-repair
python3 build_polyhunk_tool_sequences.py                # all of 3, 4, 5
python3 build_polyhunk_tool_sequences.py --window 4     # just window 4
python3 build_polyhunk_tool_sequences.py --windows 3 5  # selected windows

# 2. Render plots (Qwen + Gemini × all three windows by default)
cd hunk-poly/trajectory-analysis
python3 generate_sequence_plots.py                      # 6 PNGs (qwen+gemini × w3,w4,w5)
python3 generate_sequence_plots.py --window 3           # only paper Figs. 9 & 10
python3 generate_sequence_plots.py --window 5 --agents qwen gemini
python3 generate_sequence_plots.py --windows 3 4 --agents claude codex
```

PNGs land in `hunk-poly/trajectory-analysis/diagrams/tool-sequences/` and are
named `<agent>_pass_fail_sequences_w<N>.png` (e.g. `qwen_pass_fail_sequences_w3.png`
for the paper's current Fig. 9 — see *Figs. 9 & 10* below for picking the right
window).

`generate_sequence_plots.py` is a thin wrapper that **imports**
`create_pass_fail_comparison` from the unmodified `visualize_pass_fail_sequences.py`
and varies the input CSV path + output filename per (agent, window) combination.
The plotting logic itself is untouched.

### Picking a window

| Window | Pros | Cons |
|---|---|---|
| 3 (paper default) | Cleanest visuals; highest top-pattern frequencies; matches paper narrative | Shorter sequences hide longer behavioural patterns |
| 4 | Sequences slightly stronger Fail-vs-Pass divergence | Bar text may overlap for narrow plots; Qwen w4 has rendering jitter |
| 5 | Strongest "over-modification" signal — Gemini Fail's `WR→WR→WR→WR→WR` at 7.40% is the most dramatic single-pattern stat | Sample sparsity rises sharply (5,811 unique sequences for Claude vs 813 at w3) |

## Verifying violin numbers against Table 3 and Table 4

Two read-only verification scripts pin the figure data + paper prose to
explicit anchors. Both scripts only read inputs the plot scripts read,
compute descriptive statistics, and print PASS/FAIL for each anchor — they
do not regenerate any figure and do not modify any file.

```bash
cd hunk-poly
python3 verify_violin_stats.py        # Fig 4 / §4.6 (divergence)
python3 verify_regression_stats.py    # Fig 5 / §4.7 (regression reduction)
```

Each script prints a sequence of Markdown tables and ends with a single
`VERIFICATION: PASS` or `VERIFICATION: FAIL (N discrepancies)` line. Exit
code is `0` on pass, `1` on any check failure — usable directly in CI.

### `verify_violin_stats.py` (Fig 4 / §4.6)

- **Checks A–D** — Table 4 anchors (n-sum, Pass medians, Fail medians, Pass/Fail maxes).
- **Check E** — every scalar/integer claim in the §4.6 prose paragraph
  *"Hunk Divergence as a Predictor of Agentic Repair Success"* mapped to an
  explicit anchor. 25 anchors covering L521 (overall range), L522 (Qwen),
  L523 (Gemini), L524 (Codex), L525 (Claude including mean, median, Q1, Q3,
  IQR, max, and the `n=29` count).
- **Check F** — every qualitative / comparative §4.6 claim recomputed as a
  Boolean predicate: "Pass<Fail across all agents" (L521), "Codex Fail IQR
  narrowest" (L524), "Codex repair higher than Qwen + Gemini" (L524),
  "Claude largest mean-divergence gap" (L525), "Claude Fail IQR > Pass IQR"
  (L525), "Claude Fail std widest" (L526), "Claude majority repair on
  low-divergence bugs" (L526), "Claude high-div repair < low-div repair"
  (L526), and "low-div more likely repaired for every agent" (L529). The
  side-table immediately below prints the underlying values so a human can
  re-verify each Boolean.

- **Check P (paper-vs-data)** — parses the §4.6 paragraph directly out of
  `../paper-agentic-multihunk-repair/evaluation.tex` (overridable via
  `PAPER_TEX` env var) using regexes anchored on stable phrase fragments,
  then asserts every captured number agrees with the data within tolerance.
  Catches drift in either direction: a paper edit that diverges from the
  data, OR a data refresh that the paper hasn't caught up with. 25 prose
  claims are extracted; missing-anchor warnings flag if the paragraph is
  reworded in a way that breaks a regex (parser stays strict so silent
  regressions can't slip through).

Anchor module constants: `TABLE4_FIXED_MEDIAN`, `TABLE4_UNFIXED_MEDIAN`,
`TABLE4_PASS_MAX`, `TABLE4_FAIL_MAX`, `PROSE_4_6`, `PROSE_4_6_QUAL`,
`PAPER_4_6_REGEXES`. Tolerance defaults: `±0.005` for divergence scalars;
integer anchors (`L525_claude_fail_n`) require exact match.

### `verify_regression_stats.py` (Fig 5 / §4.7)

- **Check RR-A** — sample size sanity (`n + excluded = 404`) per agent.
- **Check RR-B** — Table 3 PolyHunk regression-reduction column (`-1.50`,
  `-2.09`, `+2.16`, `+2.16`) vs computed per-agent means.
- **Check RR-C** — every scalar / percent / integer / std anchor from the
  §4.7 "Variability in Regression Reduction" paragraph: per-agent pos%,
  zero%, neg% (and the cited counts for Claude and Qwen — the only two
  agents the prose cites with an `(N of Total)` count), σ, and min.
- **Check RR-D** — three qualitative §4.7 claims: Claude + Codex both
  produce positive RR; Qwen + Gemini both produce negative RR; the
  Claude+Codex pair are narrower (lower σ) than the Qwen+Gemini pair.

- **Check RR-P (paper-vs-data)** — parses the §4.7 paragraphs directly out
  of `../paper-agentic-multihunk-repair/evaluation.tex` (overridable via
  `PAPER_TEX` env var) and asserts each captured number matches the data
  within tolerance. Handles two paragraph layouts: the "Claude and Codex
  share the highest regression reduction of +X" sentence (Block 1, with
  the shared-value claim verified against BOTH agents' means), and the
  "Variability in Regression Reduction" paragraph after Fig 5 (per-agent
  pos/zero/neg percentages + counts, σ, and min).

Anchor module constants: `TABLE3_RR_MEAN`, `PROSE_4_7`, `PROSE_4_7_QUAL`,
`PAPER_4_7_REGEXES`. Tolerance defaults: `±0.01` for regression-reduction
means (the published table rounds at 2 dp); `±0.5` percentage-points for
the pos/zero/neg splits; `±0.10` for σ; integer anchors (counts and
minimums) require exact match.

### Methodological notes

- Divergence stats use the same NaN filter and the same Pass/Fail definition
  as `generate_agent_divergence_violin_plot.py` (Pass iff the bug is in the
  agent's entry in `fixed_bugs_by_agent.json`, else Fail; all 404 bugs are
  included for every agent).
- Regression-reduction stats use the same
  `regression_reduction ∈ {"undefined", ""}` exclusion as
  `create_regression_violin_plot.py`. The Qwen `n=396` rather than `n=392`
  reflects the 4-bug HunkSWE coverage gap documented under *Known data gaps*
  above.

## Regenerating `tab:proximity_class:hunk-poly`

`tab:proximity_class:hunk-poly` in `../paper-agentic-multihunk-repair/evaluation.tex`
reports per-class counts and mean hunk divergence for Hunk4J (372), HunkSWE (32),
and the merged PolyHunk (404). Regenerate the LaTeX from the same CSVs the figure
scripts consume:

```bash
cd hunk-poly
python3 generate_proximity_class_table.py             # prints to stdout
python3 generate_proximity_class_table.py > /tmp/tab.tex   # capture to a file
```

The script reads `proximity_class.csv` and `hunk_divergence.csv`, derives the
Java / Python split from bug-id format (SWE-bench IDs contain `__`), and prints
the full `\begin{table}...\end{table}` block to stdout. Cross-checks:

- Subset counts equal 372 / 32 / 404 (asserts hard).
- Per-class counts sum across subsets: `Hunk4J + HunkSWE == PolyHunk` for every
  proximity class (asserts hard).

Either assertion failing means the source CSVs drifted — refresh the inputs via
`../build_hunkpoly_files.py` rather than hand-editing the table in
`evaluation.tex`.

## Trimming whitespace for paper inclusion

The raw matplotlib / VennDiagram PDFs carry visible whitespace margins around the
plot area (most pronounced on the Venn diagram — ~21% of vertical space is empty,
and the divergence violin loses ~12.5% height after trimming). `trim_plots.sh`
runs `pdfcrop` over every `plots/*.pdf` and writes a tight-bbox copy under
`plots/trimmed/` with the same filename — lossless and vector-preserving (the
underlying objects are unchanged; only the page MediaBox is shrunk).

```bash
cd hunk-poly
./trim_plots.sh                  # 0pt margin (tightest crop)
./trim_plots.sh --margin 5       # add 5pt all-around margin
```

The script aborts with a clear message if `pdfcrop` isn't on PATH (it ships with
TeX Live / MacTeX — see *Prerequisites*).

## Pre-generated PDFs

`plots/` already contains the four PDFs rendered from the current 404-instance
inputs, so the figures can be inspected directly from the repo without running
anything. Refreshing the inputs (see *Inputs* above) and re-running
`./generate_all_plots.sh` will overwrite these PDFs in place. The trimmed,
paper-ready versions are checked in under `plots/trimmed/` and refreshed by
`./trim_plots.sh`.
