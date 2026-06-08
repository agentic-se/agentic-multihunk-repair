#!/usr/bin/env python3
"""Verify divergence-violin (Fig 4) statistics + §4.6 prose against Table 4 anchors.

Companion script `verify_regression_stats.py` covers the regression-reduction
violin (Fig 5) and the Table 3 PolyHunk regression-reduction means.

This script reads the paper source at
  ../paper-agentic-multihunk-repair/evaluation.tex
extracts the per-agent numbers the §4.6 paragraph
*"Hunk Divergence as a Predictor of Agentic Repair Success"* asserts, and
checks them against the same data the producing script reads. If the prose
drifts from the data (e.g. a number is edited but the data is not refreshed,
or vice versa), Check P (paper-vs-data) reports the discrepancy.
"""

import json
import os
import re
import sys

import numpy as np
import pandas as pd

AGENT_NAMES = {
    "qwen_code":    "Qwen Code",
    "gemini_cli":   "Gemini-cli",
    "openai_codex": "OpenAI Codex",
    "claude_code":  "Claude Code",
}
AGENT_ORDER = list(AGENT_NAMES.values())

# Default path to the paper source. Override with $PAPER_TEX if needed.
PAPER_TEX_DEFAULT = "../paper-agentic-multihunk-repair/evaluation.tex"

TABLE4_FIXED_MEDIAN   = {"Qwen Code": 0.31, "Gemini-cli": 0.36, "OpenAI Codex": 0.39, "Claude Code": 0.40}
TABLE4_UNFIXED_MEDIAN = {"Qwen Code": 0.45, "Gemini-cli": 0.47, "OpenAI Codex": 0.47, "Claude Code": 0.47}
TABLE4_PASS_MAX       = {"Qwen Code": 1.27, "Gemini-cli": 1.27, "OpenAI Codex": 1.56, "Claude Code": 1.56}
TABLE4_FAIL_MAX       = 1.60
DIVERGENCE_TOL        = 0.005

# ----------------------------------------------------------------------------
# Section 4.6 prose anchors -- "Hunk Divergence as a Predictor of Agentic
# Repair Success" in paper-agentic-multihunk-repair/evaluation.tex
#
# Every (line, claim) pair below is pinned to an expected scalar or boolean.
# Editing any number in the prose without updating the matching anchor here
# will cause Check E to FAIL.
# ----------------------------------------------------------------------------
PROSE_4_6 = {
    # L521 overall-summary range endpoints
    "L521_pass_median_min":       0.31,   # Qwen
    "L521_pass_median_max":       0.40,   # Claude
    "L521_fail_median_min":       0.45,   # Qwen
    "L521_fail_median_max":       0.47,   # Gemini / Codex / Claude all tie
    "L521_overall_fail_tail":     1.60,   # "long tail extending up to 1.6"

    # L522 Qwen per-agent
    "L522_qwen_pass_median":      0.31,
    "L522_qwen_pass_q1":          0.14,
    "L522_qwen_pass_q3":          0.49,
    "L522_qwen_fail_median":      0.45,
    "L522_qwen_fail_max":         1.60,

    # L523 Gemini per-agent
    "L523_gemini_pass_median":    0.36,
    "L523_gemini_pass_max":       1.27,
    "L523_gemini_fail_median":    0.47,
    "L523_gemini_fail_max":       1.60,

    # L524 Codex per-agent
    "L524_codex_pass_median":     0.39,
    "L524_codex_fail_median":     0.47,

    # L525 Claude per-agent
    "L525_claude_pass_mean":      0.44,
    "L525_claude_fail_mean":      0.62,
    "L525_claude_pass_median":    0.40,
    "L525_claude_pass_q1":        0.24,
    "L525_claude_pass_q3":        0.61,
    "L525_claude_fail_median":    0.47,
    "L525_claude_fail_iqr":       0.41,
    "L525_claude_fail_max":       1.60,
    "L525_claude_fail_n":         29,     # integer count
}

# Qualitative / comparative claims that must be derived rather than read off
# a single cell. Each maps to a Boolean expectation; Check F evaluates the
# computation and asserts the result.
PROSE_4_6_QUAL = [
    # L521 "Across all agents, a consistent trend" (Pass median < Fail median
    # for every one of the four agents).
    ("L521_consistent_trend_pass_lt_fail", True),

    # L524 "Codex ... fail distribution is narrower" -- Codex Fail IQR must be
    # strictly less than every other agent's Fail IQR.
    ("L524_codex_fail_iqr_narrowest",      True),

    # L524 "aligning with its higher overall repair accuracy" -- Codex repair
    # accuracy (PolyHunk Table 3 = 87.38%) is higher than Qwen (26.98%) and
    # Gemini (43.07%), the two preceding paragraphs' subjects.
    ("L524_codex_repair_higher_than_qwen_gemini", True),

    # L525 "Claude shows the largest separation between passing and failing
    # cases in terms of mean divergence" -- Claude's (Fail mean - Pass mean)
    # gap is strictly larger than every other agent's gap.
    ("L525_claude_largest_mean_gap",       True),

    # L525 Claude "wider IQR" -- Claude Fail IQR > Claude Pass IQR.
    ("L525_claude_fail_iqr_wider_than_pass", True),

    # L525 Claude Fail "higher median than Pass".
    ("L525_claude_fail_median_higher_than_pass", True),

    # L526 "wide distribution of failing cases" -- Claude Fail std > Claude
    # Pass std AND Claude Fail std is the largest of the four agents' Fail
    # stds (the "wide" claim against context of "Codex narrower" + the
    # broader cross-agent comparison).
    ("L526_claude_fail_std_widest",        True),

    # L526 "Claude successfully repairs most low-divergence bugs" -- of bugs
    # below the overall median divergence, Claude repairs > 50%.
    ("L526_claude_repairs_majority_of_low_div", True),

    # L526 "less effective on bugs that require highly fragmented patches" --
    # Claude's repair rate on div >= 1.0 is strictly lower than its repair
    # rate on div < 0.40.
    ("L526_claude_high_div_lower_than_low_div", True),

    # L529 "lower divergence -> more likely repaired across agents" -- for
    # every agent, repair rate on div < 0.40 is strictly higher than repair
    # rate on div >= 0.60.
    ("L529_low_div_more_likely_for_all_agents", True),
]

def load_divergence_long():
    """Replicate generate_agent_divergence_violin_plot.py: one row per (bug, agent)."""
    div_df = pd.read_csv("hunk_divergence.csv")
    with open("fixed_bugs_by_agent.json") as f:
        fixed_bugs_json = json.load(f)
    div_lookup = dict(zip(div_df["bug_id"], div_df["divergence"]))
    rows = []
    for key, name in AGENT_NAMES.items():
        fixed_set = set(fixed_bugs_json.get(key, []))
        for bug, div in div_lookup.items():
            if pd.isna(div):
                continue
            outcome = "Pass" if bug in fixed_set else "Fail"
            rows.append({"agent": name, "bug_id": bug, "outcome": outcome, "divergence": div})
    return pd.DataFrame(rows)


def describe(values):
    a = np.asarray(values, dtype=float)
    q1 = np.percentile(a, 25)
    q3 = np.percentile(a, 75)
    return {
        "n":      len(a),
        "min":    float(a.min()),
        "Q1":     float(q1),
        "median": float(np.percentile(a, 50)),
        "Q3":     float(q3),
        "max":    float(a.max()),
        "IQR":    float(q3 - q1),
        "mean":   float(a.mean()),
        "std":    float(a.std(ddof=1)),
    }


def print_table(title, header, rows):
    print(f"\n## {title}\n")
    print("| " + " | ".join(header) + " |")
    print("|" + "|".join(["---"] * len(header)) + "|")
    for r in rows:
        print("| " + " | ".join(r) + " |")


# ---------------------------------------------------------------------------
# Paper parser. Extracts each claim from the §4.6 "Hunk Divergence as a
# Predictor of Agentic Repair Success" paragraph by anchoring on stable
# phrase fragments and pulling out the trailing number.
#
# Each regex captures the literal value AS WRITTEN IN THE PAPER (e.g. "0.31"),
# which we then compare against the float we compute from the data. The
# regexes are deliberately strict so that any rewording that changes the
# semantic claim breaks the parser and surfaces the issue.
# ---------------------------------------------------------------------------
SECTION_4_6_HEADER = r"\\header\{Hunk Divergence as a Predictor of Agentic Repair Success\}"
SECTION_4_6_END    = r"Overall, the results show a consistent relationship"

PAPER_4_6_REGEXES = {
    # L521 - overall range endpoints
    "L521_pass_median_min":       r"median divergence for passing cases ranging from (\d+\.\d+) to \d+\.\d+",
    "L521_pass_median_max":       r"median divergence for passing cases ranging from \d+\.\d+ to (\d+\.\d+)",
    "L521_fail_median_min":       r"median divergence of failing cases ranging from (\d+\.\d+) to \d+\.\d+",
    "L521_fail_median_max":       r"median divergence of failing cases ranging from \d+\.\d+ to (\d+\.\d+)",
    "L521_overall_fail_tail":     r"long tail extending up to (\d+\.?\d*)",

    # L522 Qwen Code per-agent (anchor on the phrase, not on \qwencode + lookahead,
    # because [^.]* would stop at the first decimal point).
    "L522_qwen_pass_median":      r"passing bugs have a median divergence of (\d+\.\d+)",
    "L522_qwen_pass_q1":          r"interquartile range of (\d+\.\d+) to \d+\.\d+, whereas failed repairs",
    "L522_qwen_pass_q3":          r"interquartile range of \d+\.\d+ to (\d+\.\d+), whereas failed repairs",
    "L522_qwen_fail_median":      r"failed repairs have a median of (\d+\.\d+) and can reach",
    "L522_qwen_fail_max":         r"failed repairs have a median of \d+\.\d+ and can reach (\d+\.?\d*)",

    # L523 Gemini per-agent
    "L523_gemini_pass_median":    r"pass cases centered at (\d+\.\d+) \(extending",
    "L523_gemini_pass_max":       r"pass cases centered at \d+\.\d+ \(extending to (\d+\.\d+)\)",
    "L523_gemini_fail_median":    r"fail cases at (\d+\.\d+) \(extending",
    "L523_gemini_fail_max":       r"fail cases at \d+\.\d+ \(extending to (\d+\.?\d*)\)",

    # L524 Codex per-agent
    "L524_codex_pass_median":     r"\\codex shows a slightly higher pass median of (\d+\.\d+)",
    "L524_codex_fail_median":     r"\\codex shows a slightly higher pass median of \d+\.\d+ and a fail median of (\d+\.\d+)",

    # L525 Claude per-agent
    "L525_claude_pass_mean":      r"in terms of mean divergence \((\d+\.\d+) for passing",
    "L525_claude_fail_mean":      r"vs\.\s*(\d+\.\d+) for failing",
    "L525_claude_pass_median":    r"For passing cases, the median divergence is (\d+\.\d+)",
    "L525_claude_pass_q1":        r"with an interquartile range of (\d+\.\d+)[–—\-]\d+\.\d+",
    "L525_claude_pass_q3":        r"with an interquartile range of \d+\.\d+[–—\-](\d+\.\d+)",
    "L525_claude_fail_n":         r"the (\d+) failing cases have a higher median divergence",
    "L525_claude_fail_median":    r"failing cases have a higher median divergence of (\d+\.\d+)",
    "L525_claude_fail_iqr":       r"wider interquartile range of (\d+\.\d+)",
    "L525_claude_fail_max":       r"long upper tail extending to (\d+\.?\d*)",
}


def extract_section(tex_path, header_re, end_re):
    """Pull out the text between the header and the closing 'Overall' sentence."""
    if not os.path.exists(tex_path):
        return None
    with open(tex_path) as f:
        full = f.read()
    h = re.search(header_re, full)
    if not h:
        return None
    rest = full[h.start():]
    e = re.search(end_re, rest)
    if not e:
        return rest
    return rest[: e.end()]


def parse_paper_4_6(tex_path):
    """Return dict {anchor_key: float or int} parsed from the §4.6 paragraph."""
    section = extract_section(tex_path, SECTION_4_6_HEADER, SECTION_4_6_END)
    if section is None:
        return None, f"section not found in {tex_path}"
    parsed = {}
    missing = []
    for key, pattern in PAPER_4_6_REGEXES.items():
        m = re.search(pattern, section)
        if not m:
            missing.append(key)
            continue
        raw = m.group(1)
        if key.endswith("_fail_n"):
            parsed[key] = int(raw)
        else:
            parsed[key] = float(raw)
    err = None
    if missing:
        err = "could not parse paper claims: " + ", ".join(missing)
    return parsed, err


def verify():
    failures = []

    plot_df = load_divergence_long()
    stats = {}
    rows = []
    for agent in AGENT_ORDER:
        for outcome in ("Pass", "Fail"):
            sub = plot_df[(plot_df["agent"] == agent) & (plot_df["outcome"] == outcome)]
            s = describe(sub["divergence"])
            stats[(agent, outcome)] = s
            rows.append([
                agent, outcome, str(s["n"]),
                f"{s['min']:.3f}", f"{s['Q1']:.3f}", f"{s['median']:.3f}",
                f"{s['Q3']:.3f}", f"{s['max']:.3f}", f"{s['IQR']:.3f}",
                f"{s['mean']:.3f}", f"{s['std']:.3f}",
            ])
    print_table(
        "Divergence violin -- per (agent, outcome) descriptive statistics",
        ["Agent", "Outcome", "n", "min", "Q1", "median", "Q3", "max", "IQR", "mean", "std"],
        rows,
    )

    rowsA = []
    for agent in AGENT_ORDER:
        np_, nf_ = stats[(agent, "Pass")]["n"], stats[(agent, "Fail")]["n"]
        excluded = 404 - (np_ + nf_)
        verdict = "PASS" if excluded == 0 else "FAIL"
        if excluded != 0:
            failures.append(f"Check A {agent}: excluded={excluded}")
        rowsA.append([agent, str(np_), str(nf_), str(np_ + nf_), str(excluded), verdict])
    print_table(
        "Check A -- n(Pass) + n(Fail) per agent",
        ["Agent", "n(Pass)", "n(Fail)", "Sum", "Excluded", "Verdict"],
        rowsA,
    )

    rowsB = []
    for agent, anchor in TABLE4_FIXED_MEDIAN.items():
        med = stats[(agent, "Pass")]["median"]
        diff = med - anchor
        verdict = "PASS" if abs(diff) <= DIVERGENCE_TOL else "FAIL"
        if verdict == "FAIL":
            failures.append(f"Check B {agent}: Pass median={med:.3f} vs anchor={anchor:.3f}")
        rowsB.append([agent, f"{med:.3f}", f"{anchor:.3f}", f"{diff:+.3f}", verdict])
    print_table(
        "Check B -- Pass medians vs Table 4 (Hunk Divergence Fixed)",
        ["Agent", "Computed Pass median", "Table 4", "Diff", "Verdict (+/-0.005)"],
        rowsB,
    )

    rowsC = []
    for agent, anchor in TABLE4_UNFIXED_MEDIAN.items():
        med = stats[(agent, "Fail")]["median"]
        diff = med - anchor
        verdict = "PASS" if abs(diff) <= DIVERGENCE_TOL else "FAIL"
        if verdict == "FAIL":
            failures.append(f"Check C {agent}: Fail median={med:.3f} vs anchor={anchor:.3f}")
        rowsC.append([agent, f"{med:.3f}", f"{anchor:.3f}", f"{diff:+.3f}", verdict])
    print_table(
        "Check C -- Fail medians vs Table 4 (Hunk Divergence Unfixed)",
        ["Agent", "Computed Fail median", "Table 4", "Diff", "Verdict (+/-0.005)"],
        rowsC,
    )

    rowsD = []
    for agent in AGENT_ORDER:
        pm = stats[(agent, "Pass")]["max"]
        fm = stats[(agent, "Fail")]["max"]
        pa = TABLE4_PASS_MAX[agent]
        ok_p = abs(pm - pa) <= DIVERGENCE_TOL
        ok_f = abs(fm - TABLE4_FAIL_MAX) <= DIVERGENCE_TOL
        if not ok_p:
            failures.append(f"Check D {agent} Pass-max: {pm:.4f} vs {pa}")
        if not ok_f:
            failures.append(f"Check D {agent} Fail-max: {fm:.4f} vs {TABLE4_FAIL_MAX}")
        rowsD.append([
            agent, f"{pm:.4f}", f"{pa:.2f}", "PASS" if ok_p else "FAIL",
            f"{fm:.4f}", f"{TABLE4_FAIL_MAX:.2f}", "PASS" if ok_f else "FAIL",
        ])
    print_table(
        "Check D -- Pass-max and Fail-max vs Table 4",
        ["Agent", "Pass max", "Anchor", "Verdict", "Fail max", "Anchor", "Verdict"],
        rowsD,
    )

    # ------------------------------------------------------------------
    # Check E -- Section 4.6 prose anchors (scalar / integer)
    # ------------------------------------------------------------------
    pass_meds = {a: stats[(a, "Pass")]["median"] for a in AGENT_ORDER}
    fail_meds = {a: stats[(a, "Fail")]["median"] for a in AGENT_ORDER}
    fail_maxes = {a: stats[(a, "Fail")]["max"] for a in AGENT_ORDER}

    # Map each anchor key to its computed value from the violin data.
    computed = {
        "L521_pass_median_min":    min(pass_meds.values()),
        "L521_pass_median_max":    max(pass_meds.values()),
        "L521_fail_median_min":    min(fail_meds.values()),
        "L521_fail_median_max":    max(fail_meds.values()),
        "L521_overall_fail_tail":  max(fail_maxes.values()),

        "L522_qwen_pass_median":   stats[("Qwen Code", "Pass")]["median"],
        "L522_qwen_pass_q1":       stats[("Qwen Code", "Pass")]["Q1"],
        "L522_qwen_pass_q3":       stats[("Qwen Code", "Pass")]["Q3"],
        "L522_qwen_fail_median":   stats[("Qwen Code", "Fail")]["median"],
        "L522_qwen_fail_max":      stats[("Qwen Code", "Fail")]["max"],

        "L523_gemini_pass_median": stats[("Gemini-cli", "Pass")]["median"],
        "L523_gemini_pass_max":    stats[("Gemini-cli", "Pass")]["max"],
        "L523_gemini_fail_median": stats[("Gemini-cli", "Fail")]["median"],
        "L523_gemini_fail_max":    stats[("Gemini-cli", "Fail")]["max"],

        "L524_codex_pass_median":  stats[("OpenAI Codex", "Pass")]["median"],
        "L524_codex_fail_median":  stats[("OpenAI Codex", "Fail")]["median"],

        "L525_claude_pass_mean":   stats[("Claude Code", "Pass")]["mean"],
        "L525_claude_fail_mean":   stats[("Claude Code", "Fail")]["mean"],
        "L525_claude_pass_median": stats[("Claude Code", "Pass")]["median"],
        "L525_claude_pass_q1":     stats[("Claude Code", "Pass")]["Q1"],
        "L525_claude_pass_q3":     stats[("Claude Code", "Pass")]["Q3"],
        "L525_claude_fail_median": stats[("Claude Code", "Fail")]["median"],
        "L525_claude_fail_iqr":    stats[("Claude Code", "Fail")]["IQR"],
        "L525_claude_fail_max":    stats[("Claude Code", "Fail")]["max"],
        "L525_claude_fail_n":      stats[("Claude Code", "Fail")]["n"],
    }

    rowsE = []
    for key, anchor in PROSE_4_6.items():
        c = computed[key]
        if isinstance(anchor, int):
            ok = int(c) == anchor
            diff_str = f"{int(c) - anchor:+d}"
            c_str = str(int(c))
            tol_str = "exact"
        else:
            ok = abs(c - anchor) <= DIVERGENCE_TOL
            diff_str = f"{c - anchor:+.4f}"
            c_str = f"{c:.4f}"
            tol_str = "+/-0.005"
        if not ok:
            failures.append(f"Check E {key}: computed {c_str} vs prose anchor {anchor} (diff {diff_str})")
        rowsE.append([key, c_str, str(anchor), diff_str, "PASS" if ok else "FAIL"])
    print_table(
        "Check E -- Section 4.6 prose anchors (scalar/integer)",
        ["Prose claim", "Computed", "Prose anchor", "Diff", "Verdict"],
        rowsE,
    )

    # ------------------------------------------------------------------
    # Check F -- Section 4.6 qualitative / comparative claims (Boolean)
    # ------------------------------------------------------------------
    # Repair-accuracy values come from Table 3 PolyHunk; pinned here so
    # we don't read another file.
    repair_pct = {"Qwen Code": 26.98, "Gemini-cli": 43.07, "OpenAI Codex": 87.38, "Claude Code": 92.82}

    div_df = pd.read_csv("hunk_divergence.csv")
    with open("fixed_bugs_by_agent.json") as f:
        fbj = json.load(f)
    fixed_sets = {AGENT_NAMES[k]: set(v) for k, v in fbj.items()}
    bug_div = {b: d for b, d in zip(div_df["bug_id"], div_df["divergence"]) if not pd.isna(d)}
    overall_median_div = float(np.median(list(bug_div.values())))

    def repair_rate(agent, predicate):
        eligible = [(b, d) for b, d in bug_div.items() if predicate(d)]
        if not eligible:
            return float("nan"), 0
        repaired = sum(1 for b, _ in eligible if b in fixed_sets[agent])
        return repaired / len(eligible), len(eligible)

    facts = {}

    facts["L521_consistent_trend_pass_lt_fail"] = all(
        stats[(a, "Pass")]["median"] < stats[(a, "Fail")]["median"] for a in AGENT_ORDER
    )

    codex_fail_iqr = stats[("OpenAI Codex", "Fail")]["IQR"]
    facts["L524_codex_fail_iqr_narrowest"] = all(
        codex_fail_iqr < stats[(a, "Fail")]["IQR"]
        for a in AGENT_ORDER if a != "OpenAI Codex"
    )

    facts["L524_codex_repair_higher_than_qwen_gemini"] = (
        repair_pct["OpenAI Codex"] > repair_pct["Qwen Code"]
        and repair_pct["OpenAI Codex"] > repair_pct["Gemini-cli"]
    )

    mean_gaps = {a: stats[(a, "Fail")]["mean"] - stats[(a, "Pass")]["mean"] for a in AGENT_ORDER}
    facts["L525_claude_largest_mean_gap"] = all(
        mean_gaps["Claude Code"] > mean_gaps[a]
        for a in AGENT_ORDER if a != "Claude Code"
    )

    facts["L525_claude_fail_iqr_wider_than_pass"] = (
        stats[("Claude Code", "Fail")]["IQR"] > stats[("Claude Code", "Pass")]["IQR"]
    )
    facts["L525_claude_fail_median_higher_than_pass"] = (
        stats[("Claude Code", "Fail")]["median"] > stats[("Claude Code", "Pass")]["median"]
    )

    claude_fail_std = stats[("Claude Code", "Fail")]["std"]
    facts["L526_claude_fail_std_widest"] = (
        claude_fail_std > stats[("Claude Code", "Pass")]["std"]
        and all(claude_fail_std > stats[(a, "Fail")]["std"] for a in AGENT_ORDER if a != "Claude Code")
    )

    claude_low_rate, _ = repair_rate("Claude Code", lambda d: d < overall_median_div)
    claude_high_rate_strict, _ = repair_rate("Claude Code", lambda d: d >= 1.0)
    claude_low_strict, _ = repair_rate("Claude Code", lambda d: d < 0.40)

    facts["L526_claude_repairs_majority_of_low_div"] = claude_low_rate > 0.5
    facts["L526_claude_high_div_lower_than_low_div"] = claude_high_rate_strict < claude_low_strict

    facts["L529_low_div_more_likely_for_all_agents"] = all(
        repair_rate(a, lambda d: d < 0.40)[0] > repair_rate(a, lambda d: d >= 0.60)[0]
        for a in AGENT_ORDER
    )

    rowsF = []
    for key, expected in PROSE_4_6_QUAL:
        actual = facts[key]
        ok = actual == expected
        if not ok:
            failures.append(f"Check F {key}: expected {expected}, got {actual}")
        rowsF.append([key, str(actual), str(expected), "PASS" if ok else "FAIL"])
    print_table(
        "Check F -- Section 4.6 qualitative claims (Boolean)",
        ["Prose claim", "Computed", "Expected", "Verdict"],
        rowsF,
    )

    # Side-table: the underlying numbers feeding Check F (for transparency)
    rowsG = [
        ["L521 consistent trend (Pass<Fail per agent)",
         "; ".join(f"{a}: {stats[(a,'Pass')]['median']:.3f}<{stats[(a,'Fail')]['median']:.3f}" for a in AGENT_ORDER)],
        ["L524 Codex Fail IQR vs others",
         f"Codex={codex_fail_iqr:.4f}; others=" + ", ".join(f"{a}:{stats[(a,'Fail')]['IQR']:.4f}" for a in AGENT_ORDER if a!="OpenAI Codex")],
        ["L525 mean-divergence gap (Fail-Pass)",
         ", ".join(f"{a}:+{mean_gaps[a]:.4f}" for a in AGENT_ORDER)],
        ["L526 Claude Fail std vs others",
         f"Claude Fail={claude_fail_std:.4f}; Pass={stats[('Claude Code','Pass')]['std']:.4f}; others Fail=" +
         ", ".join(f"{a}:{stats[(a,'Fail')]['std']:.4f}" for a in AGENT_ORDER if a!="Claude Code")],
        ["L526 Claude repair-rate low-div vs high-div",
         f"div<0.40: {100*claude_low_strict:.1f}% ; div>=1.0: {100*claude_high_rate_strict:.1f}%"],
        ["L529 per-agent repair rate low<0.40 vs high>=0.60",
         "; ".join(
             f"{a}: {100*repair_rate(a, lambda d: d < 0.40)[0]:.1f}% vs {100*repair_rate(a, lambda d: d >= 0.60)[0]:.1f}%"
             for a in AGENT_ORDER
         )],
    ]
    print_table(
        "Underlying values feeding Check F",
        ["Claim", "Values"],
        rowsG,
    )

    # ------------------------------------------------------------------
    # Check P -- Paper vs Data. Parse the §4.6 paragraph straight out of
    # evaluation.tex and assert every captured number matches what we
    # compute from the data within tolerance. This catches drift in either
    # direction (paper updated, data not refreshed; or data refreshed,
    # paper not updated).
    # ------------------------------------------------------------------
    paper_tex = os.environ.get("PAPER_TEX", PAPER_TEX_DEFAULT)
    paper, parse_err = parse_paper_4_6(paper_tex)
    rowsP = []
    if paper is None:
        failures.append(f"Check P: {parse_err}")
        rowsP.append(["(parser)", "n/a", "n/a", "n/a", "FAIL: " + (parse_err or "unknown")])
    else:
        if parse_err:
            failures.append(f"Check P: {parse_err}")
            rowsP.append(["(parser warning)", "n/a", "n/a", "n/a", "WARN: " + parse_err])
        for key in PAPER_4_6_REGEXES.keys():
            if key not in paper:
                continue
            paper_val = paper[key]
            data_val = computed[key]
            if isinstance(paper_val, int):
                ok = int(data_val) == paper_val
                diff_str = f"{int(data_val) - paper_val:+d}"
                data_str = str(int(data_val))
                paper_str = str(paper_val)
                tol_str = "exact"
            else:
                ok = abs(data_val - paper_val) <= DIVERGENCE_TOL
                diff_str = f"{data_val - paper_val:+.4f}"
                data_str = f"{data_val:.4f}"
                paper_str = f"{paper_val}"
                tol_str = f"+/-{DIVERGENCE_TOL}"
            if not ok:
                failures.append(
                    f"Check P {key}: paper says {paper_str}, data gives {data_str} (diff {diff_str}, tol {tol_str})"
                )
            rowsP.append([key, paper_str, data_str, diff_str, "PASS" if ok else "FAIL"])
    print_table(
        f"Check P -- §4.6 paper-vs-data assertions (paper: {paper_tex})",
        ["Prose claim", "Paper says", "Data says", "Diff", "Verdict"],
        rowsP,
    )

    print()
    if failures:
        print(f"VERIFICATION: FAIL ({len(failures)} discrepancies)")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("VERIFICATION: PASS (all checks within tolerance)")
    return 0


if __name__ == "__main__":
    sys.exit(verify())
