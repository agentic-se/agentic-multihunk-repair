#!/usr/bin/env python3
"""Verify regression-reduction violin (Fig 5) + §4.7 prose against Table 3 anchors.

Companion script `verify_violin_stats.py` covers the divergence violin (Fig 4)
and the §4.6 prose paragraph.

Reads the same per-agent `*_repair_ability.csv` files that
`create_regression_violin_plot.py` reads, applies the same exclusion filter
(`regression_reduction in {"undefined", ""}`), and asserts:

  Check RR-A -- per-agent sample size and exclusion counts
  Check RR-B -- per-agent mean regression reduction vs Table 3 anchors
  Check RR-C -- §4.7 "Variability in Regression Reduction" prose anchors
                (pos/zero/neg counts, std, min) per agent
  Check RR-D -- §4.7 qualitative claims (largest-mean ordering, narrow vs
                wide distribution dichotomy)
  Check RR-P -- Paper-vs-Data. Parses the §4.7 prose directly from
                evaluation.tex and asserts each captured number matches
                the data within tolerance. Flags drift in either direction.

Exit code is 0 on full pass, 1 on any check failure.
"""

import csv
import os
import re
import sys

import numpy as np

AGENT_ORDER = ["Qwen Code", "Gemini-cli", "OpenAI Codex", "Claude Code"]

# Default path to the paper source. Override with $PAPER_TEX if needed.
PAPER_TEX_DEFAULT = "../paper-agentic-multihunk-repair/evaluation.tex"

# Paths must stay in sync with create_regression_violin_plot.py.
RR_CSV_PATHS = {
    "Qwen Code":    "qwen_code_results/qwen_results/qwen_repair_ability.csv",
    "Gemini-cli":   "gemini_cli_results/gemini_repair_ability.csv",
    "OpenAI Codex": "openai_codex_results/results-codex/codex_repair_ability.csv",
    "Claude Code":  "claude_code_results/claude_results/claude_repair_ability.csv",
}

# ---------------------------------------------------------------------------
# Table 3 (PolyHunk) regression-reduction column. Tolerance is intentionally
# wider than divergence because the published table rounds at 2 dp and an
# unrounded mean can sit 0.01 away from the published value.
# ---------------------------------------------------------------------------
TABLE3_RR_MEAN = {"Qwen Code": -1.50, "Gemini-cli": -2.09, "OpenAI Codex": 2.16, "Claude Code": 2.16}
RR_TOL         = 0.01

# ---------------------------------------------------------------------------
# §4.7 "Variability in Regression Reduction" prose anchors. As of the current
# paper draft these come from the Hunk4J-only run (n=372 / 364) and have not
# been refreshed for the PolyHunk merge -- the script will flag any mismatch.
# Update each anchor when the prose is refreshed.
# ---------------------------------------------------------------------------
PROSE_4_7 = {
    # Claude (paper claims 93.0% positive of 372)
    "claude_positive_pct":  93.0,
    "claude_positive_n":    346,
    "claude_total_n":       372,
    "claude_zero_pct":      5.6,
    "claude_zero_n":        21,
    "claude_negative_pct":  1.3,
    "claude_negative_n":    5,
    "claude_std":           5.91,
    "claude_min":           -18,

    # Codex
    "codex_positive_pct":   89.9,
    "codex_zero_pct":       7.9,
    "codex_negative_pct":   2.2,
    "codex_std":            6.64,
    "codex_min":            -47,

    # Qwen (paper claims 30.2% positive of 364)
    "qwen_positive_pct":    30.2,
    "qwen_positive_n":      110,
    "qwen_total_n":         364,
    "qwen_zero_pct":        59.9,
    "qwen_zero_n":          218,
    "qwen_negative_pct":    9.9,
    "qwen_negative_n":      36,
    "qwen_std":             28.57,
    "qwen_min":             -543,

    # Gemini
    "gemini_positive_pct":  46.1,
    "gemini_zero_pct":      43.5,
    "gemini_negative_pct":  10.4,
    "gemini_std":           31.25,
    "gemini_min":           -488,
}

PROSE_4_7_QUAL = [
    # Claude+Codex positive RR vs Qwen+Gemini negative RR.
    ("claude_codex_positive_rr",  True),
    ("qwen_gemini_negative_rr",   True),
    # Claude+Codex distributions narrower (lower std) than Qwen+Gemini.
    ("claude_codex_narrower_than_qwen_gemini", True),
]

PCT_TOL = 0.5   # percentage-point tolerance for §4.7 percent anchors
STD_TOL = 0.10  # std tolerance


# ---------------------------------------------------------------------------
# Paper parser. Extracts each claim from §4.7 by anchoring on stable phrase
# fragments and pulling out the trailing number. Two paragraphs are parsed:
#
#   (a) The "share the highest regression reduction of +X" sentence, which
#       cites the four per-agent PolyHunk means (Block 1 / Table 3 anchors).
#   (b) The "Variability in Regression Reduction" paragraph after Fig 5,
#       which cites pos/zero/neg percentages + counts, sigma, and min for
#       each agent.
# ---------------------------------------------------------------------------
SECTION_4_7_HEADER = r"\\subsection\{Regression \(RQ4\)\}"
SECTION_4_7_END    = r"Overall, \\emph\{regression reduction\} reveals the hidden cost"

PAPER_4_7_REGEXES = {
    # Block 1 - per-agent PolyHunk regression means
    "claude_codex_shared_mean":  r"share the highest regression reduction of \+(\d+\.\d+)",
    "qwen_mean":                 r"most negative regression reduction values at -(\d+\.\d+) and -\d+\.\d+",
    "gemini_mean":               r"most negative regression reduction values at -\d+\.\d+ and -(\d+\.\d+)",

    # Block 4 - Variability paragraph (Claude)
    "claude_positive_pct":       r"\\claudecode achieves (\d+\.\d+)\\% positive outcomes",
    "claude_positive_n":         r"\\claudecode achieves \d+\.\d+\\% positive outcomes \((\d+) of \d+ repairs\)",
    "claude_total_n":            r"\\claudecode achieves \d+\.\d+\\% positive outcomes \(\d+ of (\d+) repairs\)",
    # Anchor on the comma+space immediately following the "(... repairs)" of
    # the positive-outcomes claim, so we stay inside the same sentence.
    "claude_zero_pct":           r"(\d+\.\d+)\\% zero-change \(\d+ repairs\), and only",
    "claude_zero_n":             r"\d+\.\d+\\% zero-change \((\d+) repairs\), and only",
    "claude_negative_pct":       r"and only (\d+\.\d+)\\% negative \(\d+ repairs\)\.",
    "claude_negative_n":         r"and only \d+\.\d+\\% negative \((\d+) repairs\)\.",

    # Block 4 - Variability paragraph (Codex)
    "codex_positive_pct":        r"\\codex shows similar behavior with (\d+\.\d+)\\% positive",
    "codex_zero_pct":            r"\\codex shows similar behavior with \d+\.\d+\\% positive, (\d+\.\d+)\\% zero",
    "codex_negative_pct":        r"\\codex shows similar behavior with \d+\.\d+\\% positive, \d+\.\d+\\% zero, and (\d+\.\d+)\\% negative",

    # Block 4 - Claude+Codex sigma + min (paired claims)
    "claude_std":                r"low variance \(\$\\sigma=(\d+\.\d+)",
    "codex_std":                 r"low variance \(\$\\sigma=\d+\.\d+\$ and \$?(\d+\.\d+)\$?\)",
    "claude_min":                r"min \$-(\d+)\$ and \$-\d+\$",
    "codex_min":                 r"min \$-\d+\$ and \$-(\d+)\$",

    # Block 4 - Variability paragraph (Qwen)
    "qwen_positive_pct":         r"\\qwencode achieves only (\d+\.\d+)\\% positive",
    "qwen_positive_n":           r"\\qwencode achieves only \d+\.\d+\\% positive outcomes \((\d+) of \d+ repairs\)",
    "qwen_total_n":              r"\\qwencode achieves only \d+\.\d+\\% positive outcomes \(\d+ of (\d+) repairs\)",
    "qwen_zero_pct":             r"with (\d+\.\d+)\\% zero-change \(\d+ repairs compile",
    "qwen_zero_n":               r"with \d+\.\d+\\% zero-change \((\d+) repairs compile",
    "qwen_negative_pct":         r"and (\d+\.\d+)\\% negative \(\d+ repairs introduce regressions\)",
    "qwen_negative_n":           r"and \d+\.\d+\\% negative \((\d+) repairs introduce regressions\)",

    # Block 4 - Variability paragraph (Gemini)
    "gemini_positive_pct":       r"\\geminicli shows (\d+\.\d+)\\% positive",
    "gemini_zero_pct":           r"\\geminicli shows \d+\.\d+\\% positive, (\d+\.\d+)\\% zero",
    "gemini_negative_pct":       r"\\geminicli shows \d+\.\d+\\% positive, \d+\.\d+\\% zero, and (\d+\.\d+)\\% negative",

    # Block 4 - Qwen+Gemini sigma + min (paired claims)
    "qwen_std":                  r"high variance \(\$\\sigma=(\d+\.\d+)",
    "gemini_std":                r"high variance \(\$\\sigma=\d+\.\d+\$ and \$?(\d+\.\d+)\$?\)",
    "qwen_min":                  r"catastrophic worst-cases \(min \$-(\d+)\$ and \$-\d+\$",
    "gemini_min":                r"catastrophic worst-cases \(min \$-\d+\$ and \$-(\d+)\$",
}


def extract_section(tex_path, header_re, end_re):
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


def parse_paper_4_7(tex_path):
    """Return dict {anchor_key: float or int} parsed from the §4.7 paragraphs."""
    section = extract_section(tex_path, SECTION_4_7_HEADER, SECTION_4_7_END)
    if section is None:
        return None, f"§4.7 not found in {tex_path}"
    parsed = {}
    missing = []
    for key, pattern in PAPER_4_7_REGEXES.items():
        m = re.search(pattern, section)
        if not m:
            missing.append(key)
            continue
        raw = m.group(1)
        if key.endswith(("_n", "_min")):
            parsed[key] = int(raw)
        else:
            parsed[key] = float(raw)
    err = None
    if missing:
        err = "could not parse paper claims: " + ", ".join(missing)
    return parsed, err


def load_regression_per_agent():
    """Replicate create_regression_violin_plot.py exclusion filter."""
    out = {}
    for name, path in RR_CSV_PATHS.items():
        vals, skipped = [], 0
        with open(path) as f:
            for row in csv.DictReader(f):
                s = row["regression_reduction"]
                if s in ("undefined", ""):
                    skipped += 1
                    continue
                vals.append(int(s))
        out[name] = (vals, skipped)
    return out


def print_table(title, header, rows):
    print(f"\n## {title}\n")
    print("| " + " | ".join(header) + " |")
    print("|" + "|".join(["---"] * len(header)) + "|")
    for r in rows:
        print("| " + " | ".join(r) + " |")


def verify():
    failures = []
    rr = load_regression_per_agent()

    # ------------------------------------------------------------------
    # Descriptive stats per agent (the same view Fig 5 plots)
    # ------------------------------------------------------------------
    stats = {}
    rows_desc = []
    for agent in AGENT_ORDER:
        vals, skipped = rr[agent]
        a = np.array(vals, dtype=float)
        q1, q3 = float(np.percentile(a, 25)), float(np.percentile(a, 75))
        med = float(np.percentile(a, 50))
        stats[agent] = {
            "n":        len(a),
            "skipped":  skipped,
            "mean":     float(a.mean()),
            "median":   med,
            "std":      float(a.std(ddof=1)),
            "min":      int(a.min()),
            "max":      int(a.max()),
            "Q1":       q1,
            "Q3":       q3,
            "IQR":      q3 - q1,
            "pos":      int((a > 0).sum()),
            "zero":     int((a == 0).sum()),
            "neg":      int((a < 0).sum()),
        }
        s = stats[agent]
        rows_desc.append([
            agent, str(s["n"]), str(s["skipped"]),
            f"{a.min():.3f}", f"{q1:.3f}", f"{med:.3f}", f"{q3:.3f}", f"{a.max():.3f}",
            f"{s['IQR']:.3f}", f"{s['mean']:.3f}", f"{s['std']:.3f}",
            str(s["pos"]), str(s["zero"]), str(s["neg"]),
        ])
    print_table(
        "Regression violin -- per-agent descriptive statistics",
        ["Agent", "n", "excluded", "min", "Q1", "median", "Q3", "max", "IQR", "mean", "std", "pos", "zero", "neg"],
        rows_desc,
    )

    # ------------------------------------------------------------------
    # Check RR-A -- sample size sanity (n + excluded = 404)
    # ------------------------------------------------------------------
    rows_a = []
    for agent in AGENT_ORDER:
        s = stats[agent]
        total = s["n"] + s["skipped"]
        verdict = "PASS" if total == 404 else "FAIL"
        if verdict == "FAIL":
            failures.append(f"Check RR-A {agent}: n + excluded = {total}, expected 404")
        rows_a.append([agent, str(s["n"]), str(s["skipped"]), str(total), verdict])
    print_table(
        "Check RR-A -- n + excluded = 404 per agent",
        ["Agent", "n", "excluded", "Sum", "Verdict"],
        rows_a,
    )

    # ------------------------------------------------------------------
    # Check RR-B -- Table 3 PolyHunk regression-reduction means
    # ------------------------------------------------------------------
    rows_b = []
    for agent, anchor in TABLE3_RR_MEAN.items():
        m = stats[agent]["mean"]
        diff = m - anchor
        verdict = "PASS" if abs(diff) <= RR_TOL else "FAIL"
        if verdict == "FAIL":
            failures.append(f"Check RR-B {agent}: computed mean {m:.4f} vs Table 3 anchor {anchor:+.2f} (diff {diff:+.4f})")
        rows_b.append([agent, f"{m:+.4f}", f"{anchor:+.2f}", f"{diff:+.4f}", verdict])
    print_table(
        "Check RR-B -- regression-reduction means vs Table 3 (PolyHunk)",
        ["Agent", "Computed mean", "Table 3", "Diff", "Verdict (+/-0.01)"],
        rows_b,
    )

    # ------------------------------------------------------------------
    # Check RR-C -- §4.7 "Variability in Regression Reduction" prose anchors
    # ------------------------------------------------------------------
    def pct(s, key): return 100.0 * s[key] / s["n"]

    computed_prose = {}
    for short, agent in [("claude", "Claude Code"), ("codex", "OpenAI Codex"),
                         ("qwen", "Qwen Code"), ("gemini", "Gemini-cli")]:
        s = stats[agent]
        computed_prose[f"{short}_positive_pct"] = pct(s, "pos")
        computed_prose[f"{short}_zero_pct"]     = pct(s, "zero")
        computed_prose[f"{short}_negative_pct"] = pct(s, "neg")
        computed_prose[f"{short}_std"]          = s["std"]
        computed_prose[f"{short}_min"]          = s["min"]
        if short in ("claude", "qwen"):
            computed_prose[f"{short}_positive_n"] = s["pos"]
            computed_prose[f"{short}_zero_n"]     = s["zero"]
            computed_prose[f"{short}_negative_n"] = s["neg"]
            computed_prose[f"{short}_total_n"]    = s["n"]

    rows_c = []
    for key, anchor in PROSE_4_7.items():
        c = computed_prose[key]
        if isinstance(anchor, int) and key.endswith(("_n", "_min")):
            ok = int(c) == anchor
            diff_str = f"{int(c) - anchor:+d}"
            c_str = str(int(c))
            tol_str = "exact"
        elif key.endswith("_std"):
            ok = abs(c - anchor) <= STD_TOL
            diff_str = f"{c - anchor:+.4f}"
            c_str = f"{c:.4f}"
            tol_str = f"+/-{STD_TOL}"
        else:  # *_pct
            ok = abs(c - anchor) <= PCT_TOL
            diff_str = f"{c - anchor:+.2f}"
            c_str = f"{c:.2f}"
            tol_str = f"+/-{PCT_TOL}"
        if not ok:
            failures.append(f"Check RR-C {key}: computed {c_str} vs prose anchor {anchor} (diff {diff_str}, tol {tol_str})")
        rows_c.append([key, c_str, str(anchor), diff_str, tol_str, "PASS" if ok else "FAIL"])
    print_table(
        "Check RR-C -- §4.7 prose anchors (Variability in Regression Reduction)",
        ["Prose claim", "Computed", "Prose anchor", "Diff", "Tolerance", "Verdict"],
        rows_c,
    )

    # ------------------------------------------------------------------
    # Check RR-D -- §4.7 qualitative comparative claims (Boolean)
    # ------------------------------------------------------------------
    facts = {
        "claude_codex_positive_rr": (
            stats["Claude Code"]["mean"] > 0 and stats["OpenAI Codex"]["mean"] > 0
        ),
        "qwen_gemini_negative_rr": (
            stats["Qwen Code"]["mean"] < 0 and stats["Gemini-cli"]["mean"] < 0
        ),
        "claude_codex_narrower_than_qwen_gemini": (
            max(stats["Claude Code"]["std"], stats["OpenAI Codex"]["std"])
            < min(stats["Qwen Code"]["std"], stats["Gemini-cli"]["std"])
        ),
    }

    rows_d = []
    for key, expected in PROSE_4_7_QUAL:
        actual = facts[key]
        ok = actual == expected
        if not ok:
            failures.append(f"Check RR-D {key}: expected {expected}, got {actual}")
        rows_d.append([key, str(actual), str(expected), "PASS" if ok else "FAIL"])
    print_table(
        "Check RR-D -- §4.7 qualitative claims (Boolean)",
        ["Prose claim", "Computed", "Expected", "Verdict"],
        rows_d,
    )

    rows_g = [
        ["claude_codex_positive_rr",
         f"Claude mean={stats['Claude Code']['mean']:+.4f}; Codex mean={stats['OpenAI Codex']['mean']:+.4f}"],
        ["qwen_gemini_negative_rr",
         f"Qwen mean={stats['Qwen Code']['mean']:+.4f}; Gemini mean={stats['Gemini-cli']['mean']:+.4f}"],
        ["claude_codex_narrower_than_qwen_gemini",
         f"Claude std={stats['Claude Code']['std']:.4f}; Codex std={stats['OpenAI Codex']['std']:.4f}; "
         f"Qwen std={stats['Qwen Code']['std']:.4f}; Gemini std={stats['Gemini-cli']['std']:.4f}"],
    ]
    print_table(
        "Underlying values feeding Check RR-D",
        ["Claim", "Values"],
        rows_g,
    )

    # ------------------------------------------------------------------
    # Check RR-P -- Paper vs Data for §4.7. Parses the prose straight out
    # of evaluation.tex and asserts every captured number agrees with the
    # data within tolerance. Flags drift in either direction.
    # ------------------------------------------------------------------
    paper_tex = os.environ.get("PAPER_TEX", PAPER_TEX_DEFAULT)
    paper, parse_err = parse_paper_4_7(paper_tex)

    # Build the data-side lookup table that mirrors the paper's anchor keys.
    cd = stats["Claude Code"]
    cdx = stats["OpenAI Codex"]
    qw = stats["Qwen Code"]
    gm = stats["Gemini-cli"]

    data = {
        # Block 1: per-agent PolyHunk means
        "claude_codex_shared_mean":  None,  # special: paper claims they share one value
        "qwen_mean":                 abs(qw["mean"]),       # paper writes as -X.XX
        "gemini_mean":               abs(gm["mean"]),

        # Claude
        "claude_positive_pct":       100.0 * cd["pos"] / cd["n"],
        "claude_positive_n":         cd["pos"],
        "claude_total_n":            cd["n"],
        "claude_zero_pct":           100.0 * cd["zero"] / cd["n"],
        "claude_zero_n":             cd["zero"],
        "claude_negative_pct":       100.0 * cd["neg"] / cd["n"],
        "claude_negative_n":         cd["neg"],
        "claude_std":                cd["std"],
        "claude_min":                abs(cd["min"]),       # paper writes as -X

        # Codex
        "codex_positive_pct":        100.0 * cdx["pos"] / cdx["n"],
        "codex_zero_pct":            100.0 * cdx["zero"] / cdx["n"],
        "codex_negative_pct":        100.0 * cdx["neg"] / cdx["n"],
        "codex_std":                 cdx["std"],
        "codex_min":                 abs(cdx["min"]),

        # Qwen
        "qwen_positive_pct":         100.0 * qw["pos"] / qw["n"],
        "qwen_positive_n":           qw["pos"],
        "qwen_total_n":              qw["n"],
        "qwen_zero_pct":             100.0 * qw["zero"] / qw["n"],
        "qwen_zero_n":               qw["zero"],
        "qwen_negative_pct":         100.0 * qw["neg"] / qw["n"],
        "qwen_negative_n":           qw["neg"],
        "qwen_std":                  qw["std"],
        "qwen_min":                  abs(qw["min"]),

        # Gemini
        "gemini_positive_pct":       100.0 * gm["pos"] / gm["n"],
        "gemini_zero_pct":           100.0 * gm["zero"] / gm["n"],
        "gemini_negative_pct":       100.0 * gm["neg"] / gm["n"],
        "gemini_std":                gm["std"],
        "gemini_min":                abs(gm["min"]),
    }

    rows_p = []
    if paper is None:
        failures.append(f"Check RR-P: {parse_err}")
        rows_p.append(["(parser)", "n/a", "n/a", "n/a", "FAIL: " + (parse_err or "unknown")])
    else:
        if parse_err:
            rows_p.append(["(parser warning)", "n/a", "n/a", "n/a", "WARN: " + parse_err])

        for key in PAPER_4_7_REGEXES.keys():
            if key not in paper:
                continue
            paper_val = paper[key]

            # Special case: paper claims Claude and Codex share +X.XX.
            # Check that this single shared value matches BOTH agents' means
            # within RR_TOL.
            if key == "claude_codex_shared_mean":
                claude_ok = abs(cd["mean"] - paper_val) <= RR_TOL
                codex_ok  = abs(cdx["mean"] - paper_val) <= RR_TOL
                ok = claude_ok and codex_ok
                claude_str = f"{cd['mean']:+.4f}"
                codex_str  = f"{cdx['mean']:+.4f}"
                data_str   = f"Claude={claude_str}, Codex={codex_str}"
                paper_str  = f"+{paper_val}"
                diff_str   = f"Claude {cd['mean']-paper_val:+.4f} / Codex {cdx['mean']-paper_val:+.4f}"
                if not ok:
                    failures.append(
                        f"Check RR-P {key}: paper says both Claude and Codex = +{paper_val}, "
                        f"data gives Claude {claude_str}, Codex {codex_str}"
                    )
                rows_p.append([key, paper_str, data_str, diff_str, "PASS" if ok else "FAIL"])
                continue

            data_val = data[key]

            if isinstance(paper_val, int):
                ok = int(data_val) == paper_val
                diff_str = f"{int(data_val) - paper_val:+d}"
                data_str = str(int(data_val))
                paper_str = str(paper_val)
                tol_str = "exact"
            elif key.endswith("_std"):
                ok = abs(data_val - paper_val) <= STD_TOL
                diff_str = f"{data_val - paper_val:+.4f}"
                data_str = f"{data_val:.4f}"
                paper_str = f"{paper_val}"
                tol_str = f"+/-{STD_TOL}"
            elif key.endswith("_pct"):
                ok = abs(data_val - paper_val) <= PCT_TOL
                diff_str = f"{data_val - paper_val:+.2f}"
                data_str = f"{data_val:.2f}"
                paper_str = f"{paper_val}"
                tol_str = f"+/-{PCT_TOL}"
            else:  # *_mean (qwen_mean, gemini_mean, absolute value)
                ok = abs(data_val - paper_val) <= RR_TOL
                diff_str = f"{data_val - paper_val:+.4f}"
                data_str = f"-{data_val:.4f}" if "mean" in key else f"{data_val:.4f}"
                paper_str = f"-{paper_val}" if "mean" in key else f"{paper_val}"
                tol_str = f"+/-{RR_TOL}"

            if not ok:
                failures.append(
                    f"Check RR-P {key}: paper says {paper_str}, data gives {data_str} (diff {diff_str}, tol {tol_str})"
                )
            rows_p.append([key, paper_str, data_str, diff_str, "PASS" if ok else "FAIL"])

    print_table(
        f"Check RR-P -- §4.7 paper-vs-data assertions (paper: {paper_tex})",
        ["Prose claim", "Paper says", "Data says", "Diff", "Verdict"],
        rows_p,
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
