#!/usr/bin/env python3
from __future__ import annotations
import argparse
import json
from pathlib import Path

def extract_events(input_path: Path) -> list[dict]:
    """
    Extract only the 'attributes' blocks containing 'event.name' 
    from a Gemini telemetry file, even if multiple JSON objects are concatenated.
    """
    filtered = []
    text = input_path.read_text(encoding="utf-8")

    decoder = json.JSONDecoder()
    idx = 0
    while idx < len(text):
        try:
            obj, end = decoder.raw_decode(text, idx)
            idx = end
            if isinstance(obj, dict):
                attrs = obj.get("attributes")
                if isinstance(attrs, dict) and "event.name" in attrs:
                    filtered.append(attrs)
        except json.JSONDecodeError:
            # Skip bad characters and continue
            idx += 1
            continue

    return filtered


def process_repo(example_dir: Path, output_dir: Path):
    """
    Traverse all bug directories under example_dir, extract clean events
    from their telemetry JSON, and save into clean_logs.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    for bug_dir in example_dir.iterdir():
        if not bug_dir.is_dir():
            continue

        logs_dir = bug_dir / "logs"
        if not logs_dir.exists():
            continue

        # Each logs/ dir has one JSON file (gemini-timestamp.json)
        json_files = list(logs_dir.glob("gemini-*.json"))
        if not json_files:
            continue

        json_file = json_files[0]  # use the single json file
        bug_id = bug_dir.name.replace("_", "-")  # convert Chart_2 → Chart-2
        out_path = output_dir / f"{bug_id}_logs.json"

        try:
            events = extract_events(json_file)
            with out_path.open("w", encoding="utf-8") as f:
                json.dump(events, f, indent=2)

            print(f"[OK] {bug_id}: wrote {len(events)} events → {out_path}")
        except Exception as e:
            print(f"[ERROR] {bug_id}: {e}")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Clean Gemini telemetry logs: extract only 'attributes' with 'event.name' per bug."
    )
    p.add_argument(
        "--src",
        required=True,
        help="Path to directory containing bug folders (e.g., Chart_2, Cli_7, ...)."
    )
    p.add_argument(
        "--out",
        required=True,
        help="Directory to write cleaned logs (one JSON per bug)."
    )
    return p.parse_args()


if __name__ == "__main__":
    args = parse_args()
    example_dir = Path(args.src).expanduser().resolve()
    output_dir = Path(args.out).expanduser().resolve()

    process_repo(example_dir, output_dir)
