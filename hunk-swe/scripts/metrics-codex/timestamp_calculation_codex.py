#!/usr/bin/env python3
import argparse, csv, json, re
from pathlib import Path
from datetime import datetime, timezone
from typing import Iterable, Dict, List, Optional

# ---------- JSON parsing helpers ----------

def parse_iso8601(ts: str) -> Optional[datetime]:
    if not ts:
        return None
    # handle trailing 'Z'
    if ts.endswith("Z"):
        ts = ts[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(ts)
        # ensure timezone-aware
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except ValueError:
        return None

def parse_log_timestamp(line: str) -> Optional[datetime]:
    """Parse timestamp from .log file format like [2025-10-30T06:38:50]"""
    match = re.search(r'\[(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})\]', line)
    if match:
        return parse_iso8601(match.group(1) + "Z")
    return None

def timestamps_from_jsonl_file(path: Path) -> List[datetime]:
    """Extract timestamps from Codex JSONL files."""
    stamps: List[datetime] = []
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    if isinstance(obj, dict):
                        # Check for timestamp field
                        ts = obj.get("timestamp")
                        if ts:
                            dt = parse_iso8601(ts)
                            if dt:
                                stamps.append(dt)
                except json.JSONDecodeError:
                    continue
    except Exception:
        pass
    return stamps

def timestamps_from_log_file(path: Path) -> List[datetime]:
    """Extract timestamps from Codex .log files."""
    stamps: List[datetime] = []
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                dt = parse_log_timestamp(line)
                if dt:
                    stamps.append(dt)
    except Exception:
        pass
    return stamps

# ---------- bug <-> log file matching ----------

def normalize_bug_id(bug_id: str) -> str:
    # Normalize 'Chart_14' <-> 'Chart-14' to a canonical form
    return re.sub(r"[_-]", "-", bug_id.strip())

def find_log_files_for_bug(log_dir: Path, bug_id: str) -> List[Path]:
    """Find all log files (JSONL and .log) for a given bug."""
    if not log_dir.exists():
        return []

    norm = normalize_bug_id(bug_id)           # Chart-14
    alt  = norm.replace("-", "_")             # Chart_14

    files = []
    # Look for bug-specific directory
    bug_dir = log_dir / alt
    if bug_dir.exists() and bug_dir.is_dir():
        for p in bug_dir.rglob("*"):
            if p.is_file() and p.suffix.lower() in {".json", ".jsonl", ".log"}:
                files.append(p)

    return sorted(files)

def duration_seconds_from_dir(log_dir: Path, bug_id: str) -> Optional[float]:
    files = find_log_files_for_bug(log_dir, bug_id)
    if not files:
        return None

    all_stamps: List[datetime] = []
    for f in files:
        if f.suffix.lower() in {".json", ".jsonl"}:
            all_stamps.extend(timestamps_from_jsonl_file(f))
        elif f.suffix.lower() == ".log":
            all_stamps.extend(timestamps_from_log_file(f))

    if len(all_stamps) < 2:
        return None

    first, last = min(all_stamps), max(all_stamps)
    return (last - first).total_seconds()

# ---------- CSV IO ----------

def read_status_map(csv_path: Path) -> Dict[str, str]:
    m: Dict[str, str] = {}
    with csv_path.open(newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            bug = (row.get("bug_id") or row.get("bug") or row.get("id") or "").strip()
            if not bug:
                continue
            # map 'Yes'/'No' -> 'pass'/'fail'
            raw = (row.get("pass") or row.get("status") or "").strip().lower()
            status = "pass" if raw in ("yes", "true", "pass", "passed", "1") else \
                     ("fail" if raw else "")
            m[bug] = status
    return m

def write_output(rows: List[Dict[str, str]], out_csv: Path):
    fieldnames = ["bug_id", "status", "duration_seconds"]
    with out_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow(r)

# ---------- Main ----------

def main():
    ap = argparse.ArgumentParser(description="Compute durations from Codex logs.")
    ap.add_argument("--status-csv", required=True, help="Path to CSV with bug_id and pass/status columns")
    ap.add_argument("--logs-dir", required=True, help="Folder with Codex log directories (one per bug)")
    ap.add_argument("--out", required=True, help="Output CSV path")
    args = ap.parse_args()

    status_csv = Path(args.status_csv).expanduser().resolve()
    logs_dir = Path(args.logs_dir).expanduser().resolve()
    out_csv = Path(args.out).expanduser().resolve()

    status_map = read_status_map(status_csv)

    rows: List[Dict[str, str]] = []
    for bug_id in sorted(status_map.keys(), key=str):
        status = status_map.get(bug_id, "")
        dur = duration_seconds_from_dir(logs_dir, bug_id)

        rows.append({
            "bug_id": bug_id,
            "status": status,
            "duration_seconds": "" if dur is None else f"{dur:.3f}",
        })

    out_csv.parent.mkdir(parents=True, exist_ok=True)
    write_output(rows, out_csv)
    print(f"Wrote {len(rows)} rows → {out_csv}")

if __name__ == "__main__":
    main()
