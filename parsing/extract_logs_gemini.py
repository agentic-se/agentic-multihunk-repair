#!/usr/bin/env python3
import shutil
from pathlib import Path

def collect_raw_logs(example_dir: Path, output_dir: Path):
    example_dir = example_dir.expanduser().resolve()
    output_dir = output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    # Iterate through bug directories in example_dir
    for bug_dir in example_dir.iterdir():
        if not bug_dir.is_dir():
            continue

        logs_dir = bug_dir / "logs"
        if not logs_dir.exists():
            continue

        # Find JSON files inside logs/
        json_files = list(logs_dir.glob("*.json"))
        if not json_files:
            continue

        # Usually there should only be one JSON log per bug
        for jf in json_files:
            # Rename to bug_id_logs.json (Chart_2 → Chart-2_logs.json)
            bug_id = bug_dir.name.replace("_", "-")
            out_file = output_dir / f"{bug_id}_logs.json"
            shutil.copy(jf, out_file)
            print(f"[OK] Copied {jf} → {out_file}")

if __name__ == "__main__":
    example_dir = Path("~/Desktop/example_dir")
    output_dir = Path("~/Desktop/raw_logs")
    collect_raw_logs(example_dir, output_dir)
