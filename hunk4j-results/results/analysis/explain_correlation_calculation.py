#!/usr/bin/env python3
"""
Step-by-step explanation of Pearson correlation calculation.
Shows exactly how r = 0.9552 is computed from the data.
"""

import numpy as np

# Data from repair ability analysis
print("Step 1: Our Data Points")
print("=" * 70)
data = [
    ('Claude Code', 93.28, 2.47),
    ('OpenAI Codex', 87.10, 2.25),
    ('Gemini CLI', 41.67, -1.92),
    ('Qwen Code', 25.81, -1.34)
]

print(f"{'Tool':<15} {'Repair Rate (%)':<20} {'Regression Reduction':<20}")
print("-" * 70)
for tool, repair_rate, reg_reduction in data:
    print(f"{tool:<15} {repair_rate:<20.2f} {reg_reduction:<20.2f}")

# Extract X (repair rates) and Y (regression reductions)
X = np.array([d[1] for d in data])  # repair rates
Y = np.array([d[2] for d in data])  # regression reductions

print("\n" + "=" * 70)
print("Step 2: Calculate Means")
print("=" * 70)
mean_x = np.mean(X)
mean_y = np.mean(Y)
print(f"Mean repair rate (x̄):           {mean_x:.4f}%")
print(f"Mean regression reduction (ȳ):   {mean_y:.4f}")

print("\n" + "=" * 70)
print("Step 3: Calculate Deviations from Mean")
print("=" * 70)
print(f"{'Tool':<15} {'(xi - x̄)':<20} {'(yi - ȳ)':<20}")
print("-" * 70)
deviations_x = X - mean_x
deviations_y = Y - mean_y
for i, (tool, _, _) in enumerate(data):
    print(f"{tool:<15} {deviations_x[i]:<20.4f} {deviations_y[i]:<20.4f}")

print("\n" + "=" * 70)
print("Step 4: Calculate Products and Squares")
print("=" * 70)
print(f"{'Tool':<15} {'(xi-x̄)(yi-ȳ)':<20} {'(xi-x̄)²':<20} {'(yi-ȳ)²':<20}")
print("-" * 70)
products = deviations_x * deviations_y
squares_x = deviations_x ** 2
squares_y = deviations_y ** 2
for i, (tool, _, _) in enumerate(data):
    print(f"{tool:<15} {products[i]:<20.4f} {squares_x[i]:<20.4f} {squares_y[i]:<20.4f}")

print("\n" + "=" * 70)
print("Step 5: Calculate Sums")
print("=" * 70)
sum_products = np.sum(products)
sum_squares_x = np.sum(squares_x)
sum_squares_y = np.sum(squares_y)
print(f"Σ[(xi - x̄)(yi - ȳ)]:  {sum_products:.4f}")
print(f"Σ[(xi - x̄)²]:         {sum_squares_x:.4f}")
print(f"Σ[(yi - ȳ)²]:         {sum_squares_y:.4f}")

print("\n" + "=" * 70)
print("Step 6: Calculate Pearson Correlation Coefficient")
print("=" * 70)
print("\nFormula: r = Σ[(xi - x̄)(yi - ȳ)] / √[Σ(xi - x̄)² × Σ(yi - ȳ)²]")
print()
denominator = np.sqrt(sum_squares_x * sum_squares_y)
print(f"Numerator:   {sum_products:.4f}")
print(f"Denominator: √({sum_squares_x:.4f} × {sum_squares_y:.4f}) = √{sum_squares_x * sum_squares_y:.4f} = {denominator:.4f}")
print()
r = sum_products / denominator
print(f"r = {sum_products:.4f} / {denominator:.4f} = {r:.4f}")

print("\n" + "=" * 70)
print("Step 7: Interpretation")
print("=" * 70)
print(f"Pearson correlation: r = {r:.4f}")
print(f"R-squared:          r² = {r**2:.4f} ({r**2*100:.2f}% of variance explained)")
print("\nThis means there is a VERY STRONG positive linear relationship between")
print("repair success rate and regression reduction.")
print("\nAs repair rate increases by 1%, regression reduction increases by approximately")
print(f"{r * (np.std(Y) / np.std(X)):.4f} units on average.")
