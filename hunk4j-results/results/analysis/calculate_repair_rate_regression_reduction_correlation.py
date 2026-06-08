#!/usr/bin/env python3
"""
Calculate Pearson correlation between repair success rate and regression reduction.
"""

import numpy as np
from scipy import stats

# Data from repair ability analysis
data = {
    'Claude Code': {'repair_rate': 93.28, 'regression_reduction': 2.47},
    'OpenAI Codex': {'repair_rate': 87.10, 'regression_reduction': 2.25},
    'Gemini CLI': {'repair_rate': 41.67, 'regression_reduction': -1.92},
    'Qwen Code': {'repair_rate': 25.81, 'regression_reduction': -1.34}
}

# Extract arrays for correlation calculation
tools = list(data.keys())
repair_rates = np.array([data[tool]['repair_rate'] for tool in tools])
regression_reductions = np.array([data[tool]['regression_reduction'] for tool in tools])

# Calculate Pearson correlation
pearson_r, p_value = stats.pearsonr(repair_rates, regression_reductions)

print("Correlation Analysis: Repair Success Rate vs Regression Reduction")
print("=" * 70)
print("\nData points:")
for tool in tools:
    print(f"  {tool:15s}: {data[tool]['repair_rate']:6.2f}% repair rate, "
          f"{data[tool]['regression_reduction']:+6.2f} regression reduction")

print(f"\nPearson correlation coefficient (r): {pearson_r:.4f}")
print(f"P-value: {p_value:.4f}")
print(f"R-squared (r²): {pearson_r**2:.4f}")

# Interpret the correlation
print("\nInterpretation:")
if abs(pearson_r) >= 0.9:
    strength = "very strong"
elif abs(pearson_r) >= 0.7:
    strength = "strong"
elif abs(pearson_r) >= 0.5:
    strength = "moderate"
elif abs(pearson_r) >= 0.3:
    strength = "weak"
else:
    strength = "very weak"

direction = "positive" if pearson_r > 0 else "negative"
print(f"  {strength.capitalize()} {direction} correlation")

if p_value < 0.001:
    sig = "p < 0.001 (highly significant)"
elif p_value < 0.01:
    sig = "p < 0.01 (very significant)"
elif p_value < 0.05:
    sig = "p < 0.05 (significant)"
elif p_value < 0.10:
    sig = "p < 0.10 (marginally significant)"
else:
    sig = "p >= 0.10 (not significant)"

print(f"  Statistical significance: {sig}")

# Note about sample size
print(f"\nNote: Sample size n={len(tools)} is very small. With only 4 data points,")
print("correlation analysis has limited statistical power and should be interpreted")
print("with caution. The p-value threshold for significance may not be meaningful")
print("with such a small sample.")
