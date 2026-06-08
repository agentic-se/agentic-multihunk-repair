#!/usr/bin/env python3
"""
Simple, intuitive explanation of Pearson correlation.
"""

# Our 4 data points
data = [
    ('Claude Code',   93.28,  2.47),
    ('OpenAI Codex',  87.10,  2.25),
    ('Gemini CLI',    41.67, -1.92),
    ('Qwen Code',     25.81, -1.34)
]

print("=" * 70)
print("WHAT IS PEARSON CORRELATION?")
print("=" * 70)
print("\nPearson correlation (r) measures if two variables move together.")
print("- r = +1.0: Perfect positive relationship (when X goes up, Y goes up)")
print("- r = 0.0:  No relationship (X and Y are independent)")
print("- r = -1.0: Perfect negative relationship (when X goes up, Y goes down)")
print("\n" + "=" * 70)
print("OUR DATA")
print("=" * 70)

print("\nX = Repair Success Rate (%)")
print("Y = Regression Reduction\n")

for tool, repair_rate, reg_red in data:
    print(f"{tool:15s}: X={repair_rate:6.2f}%, Y={reg_red:+6.2f}")

print("\n" + "=" * 70)
print("VISUAL PATTERN")
print("=" * 70)
print("\nLet's rank them from lowest to highest on BOTH dimensions:\n")

# Sort by repair rate
sorted_by_repair = sorted(data, key=lambda x: x[1])
print("Ranked by Repair Rate:")
for i, (tool, repair_rate, reg_red) in enumerate(sorted_by_repair, 1):
    print(f"  {i}. {tool:15s}: {repair_rate:6.2f}% repair, {reg_red:+6.2f} regression")

print()

# Sort by regression reduction
sorted_by_regression = sorted(data, key=lambda x: x[2])
print("Ranked by Regression Reduction:")
for i, (tool, repair_rate, reg_red) in enumerate(sorted_by_regression, 1):
    print(f"  {i}. {tool:15s}: {repair_rate:6.2f}% repair, {reg_red:+6.2f} regression")

print("\n" + "=" * 70)
print("KEY OBSERVATION")
print("=" * 70)
print("\nNotice: THE RANKINGS ARE ALMOST IDENTICAL!")
print("\n  Lowest repair rate  → Qwen     → Also has lowest regression reduction")
print("  Second lowest       → Gemini   → Also has second lowest regression reduction")
print("  Second highest      → Codex    → Also has second highest regression reduction")
print("  Highest repair rate → Claude   → Also has highest regression reduction")
print("\nThis nearly perfect matching of rankings means STRONG POSITIVE CORRELATION!")

print("\n" + "=" * 70)
print("THE CALCULATION RESULT")
print("=" * 70)
print("\nr = 0.9552 means:")
print("  - Very strong positive correlation (close to perfect +1.0)")
print("  - When repair rate is high, regression reduction is high")
print("  - When repair rate is low, regression reduction is low")
print("  - They move together in the same direction")

print("\n" + "=" * 70)
print("THE CATCH")
print("=" * 70)
print("\nWe only have n=4 tools (4 data points).")
print("With such a small sample, correlation analysis has limited reliability.")
print("Even random data can show strong correlation with just 4 points!")
print("\nThe p-value = 0.0448 suggests it's statistically significant,")
print("but many statisticians would be cautious about claiming significance")
print("with only 4 observations.")
