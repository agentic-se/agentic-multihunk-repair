#!/usr/bin/env python3
import argparse, csv, json, random
from pathlib import Path
from typing import Dict, List

def read_buckets(csv_path: Path) -> Dict[str, List[str]]:
    """Map proximity_class -> [bug_id,...]."""
    buckets: Dict[str, List[str]] = {}
    with csv_path.open(newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            bug = (row.get("bug_id") or "").strip()
            cls = (row.get("proximity_class") or "").strip()
            if not bug or not cls:
                continue
            buckets.setdefault(cls, []).append(bug)
    return buckets

def main():
    ap = argparse.ArgumentParser(description="Sample bugs per proximity class and copy full objects.")
    ap.add_argument("--csv", required=True, help="CSV with headers: bug_id,proximity_class")
    ap.add_argument("--json", required=True, help="JSON object keyed by bug_id")
    ap.add_argument("--out", required=True, help="Output JSON path")
    ap.add_argument("--per-class", type=int, default=10, help="Samples per class (default: 10)")
    ap.add_argument("--seed", type=int, default=42, help="Random seed (default: 42)")
    args = ap.parse_args()

    csv_path = Path(args.csv).expanduser().resolve()
    all_path = Path(args.json).expanduser().resolve()
    out_path = Path(args.out).expanduser().resolve()

    rng = random.Random(args.seed)

    buckets = read_buckets(csv_path)
    all_bugs: Dict[str, dict] = json.loads(all_path.read_text(encoding="utf-8"))
    if not isinstance(all_bugs, dict):
        raise ValueError("all-bugs JSON must be an object keyed by bug_id")

    selected: Dict[str, dict] = {}
    for cls, ids in buckets.items():
        # keep only those that exist in all_bugs
        pool = [b for b in ids if b in all_bugs]
        if not pool:
            continue
        if len(pool) > args.per_class:
            pool = rng.sample(pool, args.per_class)
        else:
            rng.shuffle(pool)
        for bug_id in pool:
            selected[bug_id] = all_bugs[bug_id]

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(selected, indent=2), encoding="utf-8")
    print(f"Wrote {len(selected)} bugs → {out_path}")

if __name__ == "__main__":
    main()
