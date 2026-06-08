#!/usr/bin/env bash
# Generate all four hunk-poly figure PDFs in one shot.
#
# Outputs:
#   plots/venn_diagram_agent_repair_overlap.pdf  (Venn)
#   plots/upset_plot_agent_repair_proximity.pdf  (Fig. 3)
#   plots/agent_divergence_violin_plot.pdf       (Fig. 4)
#   plots/agent_regression_reduction_violin.pdf  (Fig. 5)
#
# Prerequisites:
#   - Python 3.8+ with pandas, numpy, matplotlib, seaborn
#   - R 4.0+ with VennDiagram, jsonlite
# See README.md for the one-shot package install commands.

set -euo pipefail

# cd into the script's own directory so the figure scripts' relative
# input paths resolve regardless of where this entrypoint is invoked from.
cd "$(dirname "$0")"

mkdir -p plots

echo "==> [1/4] Venn diagram of 4-agent fixed-bug overlap"
Rscript generate_venn_diagram_agent_repair_overlap.R

echo
echo "==> [2/4] Fig. 3 — UpSet plot of agent intersections x proximity class"
python3 generate_upset_plot_agent_repair_proximity.py

echo
echo "==> [3/4] Fig. 4 — divergence violins, Pass vs Fail per agent"
python3 generate_agent_divergence_violin_plot.py

echo
echo "==> [4/4] Fig. 5 — regression reduction distribution per agent"
# create_regression_violin_plot.py calls plt.show() at the end; force a
# non-interactive backend so this works on headless systems too.
MPLBACKEND=Agg python3 create_regression_violin_plot.py

echo
echo "All four figures generated:"
ls -la plots/*.pdf 2>/dev/null || true
