import pandas as pd
import json
import seaborn as sns
import matplotlib.pyplot as plt
from matplotlib.colors import to_rgba

# Load divergence data
div_df = pd.read_csv("../bugwise_average_divergence.csv")
div_df['bug_id'] = div_df['bug_id'].str.replace("_", "-", regex=False)

# Load passed bugs
with open("../../results/rq2/passed_bugs.json") as f:
    passed_json = json.load(f)

# Model mapping
model_map = {
    "mistral.mistral-large-2407-v1:0": "Mistral-2407",
    "us.meta.llama3-3-70b-instruct-v1:0": "LLaMA3.3",
    "mode_4_model_gemini-2.5-flash-preview-04-17": "Gemini-2.5",
    "us.amazon.nova-pro-v1:0": "Nova-Pro",
    "mode_4_model_o4-mini-2025-04-16": "o4-mini"
}
model_order = ["Mistral-2407", "LLaMA3.3", "Gemini-2.5", "Nova-Pro", "o4-mini"]

# Collect data
plot_rows = []
all_bugs = set(div_df['bug_id'])

for key, name in model_map.items():
    passed_bugs = set(bug.replace("_", "-") for bug in passed_json.get(key, {}).get("passed", []))
    failed_bugs = all_bugs - passed_bugs

    print(f"Processing model: {name}")
    print(f"  Passed bugs: {len(passed_bugs)}")
    print(f"  Failed bugs: {len(failed_bugs)}")

    for bug in all_bugs:
        row = div_df[div_df['bug_id'] == bug]
        if row.empty or pd.isna(row['avg_divergence'].values[0]):
            continue
        divergence = row['avg_divergence'].values[0]
        outcome = "Passed" if bug in passed_bugs else "Failed"
        plot_rows.append({
            'model': name,
            'bug_id': bug,
            'outcome': outcome,
            'divergence': divergence
        })

# Create DataFrame
plot_df = pd.DataFrame(plot_rows)
plot_df['model'] = pd.Categorical(plot_df['model'], categories=model_order, ordered=True)

# Relabel outcomes for clarity
plot_df['outcome'] = plot_df['outcome'].replace({"Passed": "Pass", "Failed": "Fail"})
plot_df['outcome'] = pd.Categorical(plot_df['outcome'], categories=["Pass", "Fail"], ordered=True)

# Create model_outcome label for color mapping
plot_df['model_outcome'] = plot_df['model'].astype(str) + "_" + plot_df['outcome'].astype(str)

# Build custom palette
base_colors = sns.color_palette("Set2", n_colors=len(model_order))
palette = {}
for model, color in zip(model_order, base_colors):
    palette[f"{model}_Pass"] = to_rgba(color, alpha=0.8)
    palette[f"{model}_Fail"] = to_rgba(color, alpha=0.4)

# Plot setup
sns.set(style="white")
sns.set_context("talk", font_scale=1.1)  # Options: paper, notebook, talk, poster
# g = sns.catplot(
#     data=plot_df,
#     x="outcome", y="divergence", col="model",
#     kind="violin", hue="model_outcome", palette=palette,
#     inner="box", 
#     height=6, 
#     aspect=0.6,
#     sharey=True, col_order=model_order, legend=False
# )
g = sns.catplot(
    data=plot_df,
    x="outcome", y="divergence", col="model",
    kind="violin", hue="model_outcome", palette=palette,
    inner="box", height=5, aspect=0.35,
    sharey=True, col_order=model_order, legend=False
)

# Axis and layout
# g.set_titles("{col_name}")
# g.set_axis_labels("", "Hunk Divergence")
# g.fig.subplots_adjust(top=0.9)

g.set_titles("{col_name}")
g.set_axis_labels("", "Hunk Divergence")
g.fig.subplots_adjust(top=1.0, wspace=0.1)

# Remove internal gridlines, keep axis lines
for ax in g.axes.flat:
    ax.grid(False)
    sns.despine(ax=ax, top=True, right=True, left=False, bottom=False)

# Save to PDF (no display)
plt.tight_layout()
plt.savefig("llm_divergence_faceted_violin_plot.pdf", dpi=600)
print("Saved in llm_divergence_faceted_violin_plot.pdf")
