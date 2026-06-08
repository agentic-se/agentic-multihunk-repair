"""
Classify all 500 SWE-bench Verified instances by hunk type (single-hunk vs
multi-hunk) and issue type (Bug, Regression, Feature/Enhancement, Unlabeled).

Reads:
  - swe_bench.jsonl             (500 instances with patches)
  - swe-bench_issue_labels.json (GitHub issue labels)
  - multihunk_swe_bench_verified.json     (pre-computed multi-hunk set)

Outputs:
  - swe_bench_verified_issue_classification.json   (all 500, keyed by instance_id)
"""

import json
from collections import Counter
from pathlib import Path


# ── Label normalisation ──────────────────────────────────────────────────────

BUG_LABELS = {
    "bug", "type: bug", "type:bug", "bug :beetle:", "status: confirmed bug",
    "crash 💥", "wrong result", "false positive 🦟", "false negative 🦋",
    "regression", "type: regression",
}

FEATURE_LABELS = {
    "feature request", "new feature", "enhancement", "enhancement ✨",
    "type:enhancement", "type: enhancement",
    "type:proposal", "type: proposal", "proposal 📨",
    "blueprints",
}


def classify_issue(tags: list[str]) -> str:
    """
    Return one of: Bug, Feature/Enhancement, Unlabeled.
    Priority: Bug > Feature/Enhancement > Unlabeled.
    """
    lower_tags = {t.lower().strip() for t in tags}

    if lower_tags & BUG_LABELS:
        return "Bug"
    if lower_tags & FEATURE_LABELS:
        return "Feature/Enhancement"
    return "Unlabeled"


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    base = Path(__file__).parent

    # Load data
    swe_records = []
    with open(base / "swe_bench.jsonl") as f:
        for line in f:
            if line.strip():
                swe_records.append(json.loads(line))

    issue_labels = json.load(open(base / "swe-bench_issue_labels.json"))
    multihunk = json.load(open(base / "multihunk_swe_bench_verified.json"))

    for iid, entry in multihunk.items():
        if not entry.get("buggy_hunks"):
            raise ValueError(
                f"{iid}: multihunk entry has empty or missing buggy_hunks; "
                f"an instance flagged as multi-hunk must contain at least one hunk"
            )

    print(f"Loaded {len(swe_records)} instances, "
          f"{len(issue_labels)} label entries, "
          f"{len(multihunk)} multi-hunk bugs.\n")

    # Classify
    classified = {}
    hunk_counts = Counter()
    issue_counts = Counter()
    cross = Counter()

    for record in swe_records:
        iid = record["instance_id"]

        hunk_type = "multi-hunk" if iid in multihunk else "single-hunk"
        tags = issue_labels.get(iid, [])
        issue_type = classify_issue(tags)

        hunk_counts[hunk_type] += 1
        issue_counts[issue_type] += 1
        cross[(hunk_type, issue_type)] += 1

        entry = {
            "hunk_type": hunk_type,
            "issue_type": issue_type,
        }
        if iid in multihunk:
            entry["num_hunks"] = len(multihunk[iid]["buggy_hunks"])
        else:
            entry["num_hunks"] = 1

        classified[iid] = entry

    # ── Summary ───────────────────────────────────────────────────────────────
    total = len(swe_records)
    print("=" * 65)
    print("SWE-bench Verified — Classification Summary (500 instances)")
    print("=" * 65)

    print("\n-- By Hunk Type --")
    for ht in ["single-hunk", "multi-hunk"]:
        print(f"  {ht:12s} : {hunk_counts[ht]:4d} ({hunk_counts[ht]/total*100:.1f}%)")

    print("\n-- By Issue Type --")
    for it in ["Bug", "Feature/Enhancement", "Unlabeled"]:
        print(f"  {it:22s} : {issue_counts[it]:4d} ({issue_counts[it]/total*100:.1f}%)")

    print("\n-- Cross-tabulation (Hunk Type x Issue Type) --")
    print(f"  {'':22s}  {'single-hunk':>12s}  {'multi-hunk':>12s}")
    for it in ["Bug", "Feature/Enhancement", "Unlabeled"]:
        s = cross[("single-hunk", it)]
        m = cross[("multi-hunk", it)]
        print(f"  {it:22s}  {s:12d}  {m:12d}")

    print()

    # ── Write output ──────────────────────────────────────────────────────────
    output_path = base / "swe_bench_verified_issue_classification.json"
    with open(output_path, "w") as f:
        json.dump(classified, f, indent=4)
    print(f"Written to: {output_path}  ({len(classified)} entries)")


if __name__ == "__main__":
    main()
