"""
Analyze SWE-bench Verified patches to identify multi-hunk bugs.

A patch is considered multi-hunk if:
  1. It edits more than one file, OR
  2. Within a single file, there are multiple disjoint edit regions (multiple @@ markers)

Output: multihunk_analysis.json — keyed by instance_id, containing only multi-hunk
bugs, with a 'buggy_hunks' dict whose entries mirror the format used in
config/method_multihunk.json.
"""

import json
import re
from pathlib import Path


# ── Patch parsing ─────────────────────────────────────────────────────────────

def _extract_file_path(section: str) -> str:
    """Return the b/ file path from a diff --git section."""
    match = re.search(r"^diff --git a/.+? b/(.+)$", section, re.MULTILINE)
    if match:
        return match.group(1)
    match = re.search(r"^\+\+\+ b/(.+)$", section, re.MULTILINE)
    return match.group(1) if match else "<unknown>"


def _parse_hunk_header(header_line: str) -> tuple[int, int]:
    """
    Parse '@@ -start,count +... @@' and return (start_line, end_line) for the
    *original* (buggy) side.  When the count is omitted the unified diff
    standard implies a count of 1.
    """
    match = re.match(r"^@@ -(\d+)(?:,(\d+))? \+", header_line)
    if not match:
        return 0, 0
    start = int(match.group(1))
    count = int(match.group(2)) if match.group(2) is not None else 1
    # end_line is inclusive last line of the original hunk
    end = start + count - 1
    return start, end


def _hunk_code(hunk_lines: list[str]) -> str:
    """
    Build the code snippet for a hunk.  We keep context lines and lines that
    were removed (the buggy code), and drop added lines, to represent the
    *buggy* state — matching the spirit of the <START_BUG>…<END_BUG> format.
    The @@ header line is kept so the reader has positional context.
    """
    kept = []
    for line in hunk_lines:
        if line.startswith("+") and not line.startswith("+++"):
            continue  # skip added (fixed) lines
        kept.append(line)
    return "\n".join(kept)


def extract_hunks(patch: str) -> list[dict]:
    """
    Return a flat list of hunk dicts, one per @@ block across all files.
    Each dict has: file, start_line, end_line, code.
    """
    if not patch or not patch.strip():
        return []

    # Split the patch into per-file sections
    file_sections = re.split(r"(?=^diff --git )", patch, flags=re.MULTILINE)
    file_sections = [s for s in file_sections if s.strip()]

    hunks = []
    for section in file_sections:
        file_path = _extract_file_path(section)

        # Split the section into individual hunk blocks on @@ boundaries.
        # re.split with a capturing group keeps the delimiter as part of each chunk.
        parts = re.split(r"(^@@[^\n]*)", section, flags=re.MULTILINE)
        # parts alternates: [preamble, hdr, body, hdr, body, ...]
        i = 1  # skip preamble
        while i < len(parts) - 1:
            header = parts[i]
            body = parts[i + 1] if i + 1 < len(parts) else ""
            i += 2

            start_line, end_line = _parse_hunk_header(header)
            all_lines = [header] + body.splitlines()
            code = _hunk_code(all_lines)

            hunks.append(
                {
                    "file": file_path,
                    "start_line": start_line,
                    "end_line": end_line,
                    "code": code,
                }
            )

    return hunks


def is_multihunk(hunks: list[dict]) -> bool:
    if len(hunks) <= 1:
        return False
    # More than one hunk total is multi-hunk (covers both multi-file and
    # disjointed hunks within one file).
    return True


# ── I/O helpers ───────────────────────────────────────────────────────────────

def load_jsonl(path: str) -> list:
    records = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    data_path = Path(__file__).parent / "swe_bench.json"
    output_json = Path(__file__).parent / "multihunk_analysis.json"

    print(f"Loading {data_path} ...")
    records = load_jsonl(str(data_path))
    print(f"Loaded {len(records)} instances.\n")

    output = {}        # instance_id -> entry
    total_multihunk = 0
    multifile_count = 0
    disjoint_count = 0

    for record in records:
        instance_id = record.get("instance_id", "")
        patch = record.get("patch", "")

        hunks = extract_hunks(patch)

        if not is_multihunk(hunks):
            continue  # skip single-hunk bugs

        total_multihunk += 1

        # Classify for summary stats
        files_touched = list(dict.fromkeys(h["file"] for h in hunks))  # ordered unique
        if len(files_touched) > 1:
            multifile_count += 1
        else:
            disjoint_count += 1

        # Build buggy_hunks dict keyed by string index
        buggy_hunks = {
            str(i): {
                "file": h["file"],
                "start_line": h["start_line"],
                "end_line": h["end_line"],
                "code": h["code"],
            }
            for i, h in enumerate(hunks)
        }

        output[instance_id] = {
            "buggy_hunks": buggy_hunks,
        }

    # ── Summary ───────────────────────────────────────────────────────────────
    total = len(records)
    print("=" * 60)
    print("MULTI-HUNK ANALYSIS — SWE-bench Verified (500 instances)")
    print("=" * 60)
    print(f"Total instances       : {total}")
    print(f"Multi-hunk bugs       : {total_multihunk} ({total_multihunk/total*100:.1f}%)")
    print(f"  ├─ Multi-file edits : {multifile_count} ({multifile_count/total*100:.1f}%)")
    print(f"  └─ Disjoint hunks   : {disjoint_count} ({disjoint_count/total*100:.1f}%)")
    print(f"Single-hunk bugs      : {total - total_multihunk} ({(total-total_multihunk)/total*100:.1f}%)")

    hunk_counts = [len(v["buggy_hunks"]) for v in output.values()]
    if hunk_counts:
        print(f"\nAmong multi-hunk bugs:")
        print(f"  Min total hunks : {min(hunk_counts)}")
        print(f"  Max total hunks : {max(hunk_counts)}")
        print(f"  Mean total hunks: {sum(hunk_counts)/len(hunk_counts):.2f}")

    print()

    # ── Write JSON ────────────────────────────────────────────────────────────
    with open(output_json, "w") as f:
        json.dump(output, f, indent=4)
    print(f"Output written to: {output_json}  ({total_multihunk} entries)")


if __name__ == "__main__":
    main()
