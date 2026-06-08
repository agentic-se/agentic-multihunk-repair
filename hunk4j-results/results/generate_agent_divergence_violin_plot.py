#!/usr/bin/env python3
"""
Faceted violin plot showing hunk divergence distribution for coding agents.
Shows Fixed vs Not Fixed bugs for each agent (Gemini CLI, Qwen Code, Claude Code, OpenAI Codex).
For TOSEM paper submission.
"""
import pandas as pd
import json
import seaborn as sns
import matplotlib.pyplot as plt
from matplotlib.colors import to_rgba

# Load divergence data
div_df = pd.read_csv("hunk_divergence.csv")

# Load fixed bugs by agent
with open("fixed_bugs_by_agent.json") as f:
    fixed_bugs_json = json.load(f)

# Agent mapping
agent_map = {
    "gemini_cli": "Gemini CLI",
    "qwen_code": "Qwen Code",
    "claude_code": "Claude Code",
    "openai_codex": "OpenAI Codex"
}
agent_order = ["Qwen Code", "Gemini CLI", "OpenAI Codex", "Claude Code"]

# Collect data
plot_rows = []
all_bugs = set(div_df['bug_id'])

for key, name in agent_map.items():
    fixed_bugs = set(fixed_bugs_json.get(key, []))
    not_fixed_bugs = all_bugs - fixed_bugs

    print(f"Processing agent: {name}")
    print(f"  Fixed bugs: {len(fixed_bugs)}")
    print(f"  Not Fixed bugs: {len(not_fixed_bugs)}")

    for bug in all_bugs:
        row = div_df[div_df['bug_id'] == bug]
        if row.empty or pd.isna(row['divergence'].values[0]):
            continue
        divergence = row['divergence'].values[0]
        outcome = "Pass" if bug in fixed_bugs else "Fail"
        plot_rows.append({
            'agent': name,
            'bug_id': bug,
            'outcome': outcome,
            'divergence': divergence
        })

# Create DataFrame
plot_df = pd.DataFrame(plot_rows)
plot_df['agent'] = pd.Categorical(plot_df['agent'], categories=agent_order, ordered=True)
plot_df['outcome'] = pd.Categorical(plot_df['outcome'], categories=["Pass", "Fail"], ordered=True)

# Create agent_outcome label for color mapping
plot_df['agent_outcome'] = plot_df['agent'].astype(str) + "_" + plot_df['outcome'].astype(str)

# Build custom palette
base_colors = sns.color_palette("Set2", n_colors=len(agent_order))
palette = {}
for agent, color in zip(agent_order, base_colors):
    palette[f"{agent}_Pass"] = to_rgba(color, alpha=0.8)
    palette[f"{agent}_Fail"] = to_rgba(color, alpha=0.4)

# Plot setup
sns.set(style="white")
sns.set_context("talk", font_scale=1.1)
g = sns.catplot(
    data=plot_df,
    x="outcome", y="divergence", col="agent",
    kind="violin", hue="agent_outcome", palette=palette,
    inner="box", height=5, aspect=0.6,
    sharey=True, col_order=agent_order, legend=False
)

# Axis and layout
g.set_titles("{col_name}")
g.set_axis_labels("", "Hunk Divergence")
g.set(ylim=(-0.5, 2.0))
g.fig.subplots_adjust(top=1.0, wspace=0.7)

# Remove internal gridlines, keep axis lines
for ax in g.axes.flat:
    ax.grid(False)
    sns.despine(ax=ax, top=True, right=True, left=False, bottom=False)

# Save to PDF
plt.tight_layout()
plt.savefig("plots/agent_divergence_violin_plot.pdf", dpi=600)
print("\nPlot saved to: plots/agent_divergence_violin_plot.pdf")
