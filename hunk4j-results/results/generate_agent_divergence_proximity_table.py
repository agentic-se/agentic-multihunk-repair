#!/usr/bin/env python3
"""
Generate LaTeX table for agent performance metrics.
Shows hunk divergence for fixed/unfixed bugs and spatial proximity distribution.
"""
import pandas as pd
import json
import numpy as np

# Load data
div_df = pd.read_csv("hunk_divergence.csv")
prox_df = pd.read_csv("proximity_class.csv")
with open("fixed_bugs_by_agent.json") as f:
    fixed_bugs_json = json.load(f)

# Agent configuration (in order: Qwen, Gemini, Codex, Claude)
agents = [
    ("qwen_code", r"\texttt{Qwen Code}"),
    ("gemini_cli", r"\texttt{Gemini CLI}"),
    ("openai_codex", r"\texttt{OpenAI Codex}"),
    ("claude_code", r"\texttt{Claude Code}"),
]

proximity_classes = ["Nucleus", "Cluster", "Orbit", "Sprawl", "Fragment"]

# All bugs
all_bugs = set(div_df['bug_id'].dropna())

# Build proximity class mapping
prox_map = {}
for _, row in prox_df.iterrows():
    prox_map[row['bug_id']] = row['proximity_class']

print("\\begin{table*}[!ht]")
print("\\centering")
print("\\scriptsize")
print("\\caption{Hunk divergence for fixed and unfixed bugs, and spatial proximity distribution (\\% fixed) across coding agents}")
print("\\label{tab:agent-performance}")
print("\\begin{tabular}{l|ccc|ccc|ccccc}")
print("\\toprule")
print("\\textbf{Agent}")
print("  & \\multicolumn{3}{c|}{\\textbf{Hunk Divergence (Fixed)}}")
print("  & \\multicolumn{3}{c|}{\\textbf{Hunk Divergence (Unfixed)}}")
print("  & \\multicolumn{5}{c}{\\textbf{Spatial Proximity (\\% Fixed)}} \\\\")
print("& Median & Mean & Max")
print("  & Median & Mean & Max")
print("  & Nucleus & Cluster & Orbit & Sprawl & Fragment \\\\")
print("\\midrule")

for agent_key, agent_name in agents:
    # Get fixed and unfixed bugs for this agent
    fixed_bugs = set(fixed_bugs_json.get(agent_key, []))
    unfixed_bugs = all_bugs - fixed_bugs

    # Get divergence values for fixed bugs
    fixed_div = div_df[div_df['bug_id'].isin(fixed_bugs)]['divergence'].dropna()
    unfixed_div = div_df[div_df['bug_id'].isin(unfixed_bugs)]['divergence'].dropna()

    # Calculate divergence stats
    if len(fixed_div) > 0:
        fixed_median = fixed_div.median()
        fixed_mean = fixed_div.mean()
        fixed_max = fixed_div.max()
    else:
        fixed_median = fixed_mean = fixed_max = 0.0

    if len(unfixed_div) > 0:
        unfixed_median = unfixed_div.median()
        unfixed_mean = unfixed_div.mean()
        unfixed_max = unfixed_div.max()
    else:
        unfixed_median = unfixed_mean = unfixed_max = 0.0

    # Calculate spatial proximity percentages
    prox_percentages = []
    for prox_class in proximity_classes:
        # Get all bugs in this proximity class
        bugs_in_class = [bug for bug in all_bugs if prox_map.get(bug) == prox_class]
        total_in_class = len(bugs_in_class)

        if total_in_class > 0:
            # Count how many the agent fixed
            fixed_in_class = len([bug for bug in bugs_in_class if bug in fixed_bugs])
            percentage = (fixed_in_class / total_in_class) * 100
        else:
            percentage = 0.0

        prox_percentages.append(percentage)

    # Format and print the row
    print(f"{agent_name}")
    print(f"  & {fixed_median:.2f} & {fixed_mean:.2f} & {fixed_max:.2f}")
    print(f"  & {unfixed_median:.2f} & {unfixed_mean:.2f} & {unfixed_max:.2f}")
    print(f"  & {prox_percentages[0]:.2f} & {prox_percentages[1]:.2f} & {prox_percentages[2]:.2f} & {prox_percentages[3]:.2f} & {prox_percentages[4]:.2f} \\\\")
    print()

print("\\bottomrule")
print("\\end{tabular}")
print("\\end{table*}")
