#!/usr/bin/env python3
import argparse, csv, json, re
from pathlib import Path
from datetime import datetime, timezone
from typing import Iterable, Dict, List, Optional

# ---------- JSON parsing helpers ----------

def iter_json_objects(text: str) -> Iterable[dict]:
    """
    Yield JSON objects from a string that may contain:
    - a JSON array,
    - multiple concatenated JSON objects,
    - line-delimited JSON (NDJSON).
    """
    # Fast path: if it's a JSON array
    try:
        obj = json.loads(text)
        if isinstance(obj, list):
            for item in obj:
                if isinstance(item, dict):
                    yield item
            return
    except json.JSONDecodeError:
        pass

    # General path: mixed/concatenated/NDJSON
    dec = json.JSONDecoder()
    i, n = 0, len(text)
    while i < n:
        # skip whitespace
        while i < n and text[i].isspace():
            i += 1
        if i >= n:
            break
        try:
            obj, end = dec.raw_decode(text, i)
            if isinstance(obj, dict):
                yield obj
            elif isinstance(obj, list):
                for item in obj:
                    if isinstance(item, dict):
                        yield item
            i = end
        except json.JSONDecodeError:
            # try a single line (NDJSON)
            j = text.find("\n", i)
            if j == -1:
                j = n
            line = text[i:j].strip()
            if line:
                try:
                    obj = json.loads(line)
                    if isinstance(obj, dict):
                        yield obj
                    elif isinstance(obj, list):
                        for item in obj:
                            if isinstance(item, dict):
                                yield item
                except json.JSONDecodeError:
                    pass
            i = j + 1

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

def timestamps_from_log_file(path: Path) -> List[datetime]:
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        text = path.read_text(encoding="latin-1")

    stamps: List[datetime] = []
    for obj in iter_json_objects(text):
        # Look for timestamp in common places
        candidates = []
        if "event.timestamp" in obj:
            candidates.append(obj.get("event.timestamp"))
        if "attributes" in obj and isinstance(obj["attributes"], dict):
            if "event.timestamp" in obj["attributes"]:
                candidates.append(obj["attributes"].get("event.timestamp"))
        for ts in candidates:
            dt = parse_iso8601(ts) if isinstance(ts, str) else None
            if dt:
                stamps.append(dt)
    return stamps

# ---------- bug <-> log file matching ----------

def normalize_bug_id(bug_id: str) -> str:
    # Normalize 'Chart_14' <-> 'Chart-14' to a canonical form
    return re.sub(r"[_-]", "-", bug_id.strip())

def bug_regex(bug_id: str) -> re.Pattern:
    norm = normalize_bug_id(bug_id)
    # e.g., r'(?i)\bChart[-_]?14\b'
    m = re.match(r"^([A-Za-z]+)-(\d+)$", norm)
    if not m:
        # fallback: literal substring
        return re.compile(re.escape(norm), re.IGNORECASE)
    proj, num = m.group(1), m.group(2)
    return re.compile(rf"(?i)\b{re.escape(proj)}[-_]?{re.escape(num)}\b")

def find_log_files_for_bug(log_dir: Path, bug_id: str) -> List[Path]:
    if not log_dir.exists():
        return []
    norm = normalize_bug_id(bug_id)           # Chart-14
    alt  = norm.replace("-", "_")             # Chart_14

    files = []
    for p in log_dir.rglob("*"):
        if not p.is_file() or p.suffix.lower() not in {".json", ".jsonl", ".log"}:
            continue
        parts = [part.lower() for part in p.parts]
        name  = p.name.lower()
        # match if any path component or filename contains bug id
        if any(norm.lower() in part or alt.lower() in part for part in parts) or \
           (norm.lower() in name or alt.lower() in name):
            files.append(p)
    return sorted(files)


def duration_seconds_from_dir(log_dir: Path, bug_id: str) -> Optional[float]:
    files = find_log_files_for_bug(log_dir, bug_id)
    if not files:
        return None
    all_stamps: List[datetime] = []
    for f in files:
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
    fieldnames = ["bug_id", "status-vanilla", "status-mcp", "duration-vanilla", "duration-mcp"]
    with out_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow(r)

# ---------- Main ----------

def main():
    ap = argparse.ArgumentParser(description="Merge vanilla & MCP results and compute durations from logs.")
    ap.add_argument("--vanilla-csv", required=True, help="Path to vanilla CSV (must include bug_id, status*)")
    ap.add_argument("--mcp-csv", required=True, help="Path to MCP CSV (must include bug_id, status*)")
    ap.add_argument("--vanilla-logs", required=True, help="Folder with vanilla JSON log files")
    ap.add_argument("--mcp-logs", required=True, help="Folder with MCP JSON log files")
    ap.add_argument("--out", required=True, help="Output CSV path")
    args = ap.parse_args()

    vanilla_csv = Path(args.vanilla_csv).expanduser().resolve()
    mcp_csv = Path(args.mcp_csv).expanduser().resolve()
    vanilla_logs = Path(args.vanilla_logs).expanduser().resolve()
    mcp_logs = Path(args.mcp_logs).expanduser().resolve()
    out_csv = Path(args.out).expanduser().resolve()

    vanilla_map = read_status_map(vanilla_csv)
    mcp_map = read_status_map(mcp_csv)

    rows: List[Dict[str, str]] = []
    for bug_id in sorted(mcp_map.keys(), key=str):
        status_mcp = mcp_map.get(bug_id, "")
        status_vanilla = vanilla_map.get(bug_id, "")

        dur_v = duration_seconds_from_dir(vanilla_logs, bug_id)
        dur_m = duration_seconds_from_dir(mcp_logs, bug_id)

        rows.append({
            "bug_id": bug_id,
            "status-vanilla": status_vanilla,
            "status-mcp": status_mcp,
            "duration-vanilla": "" if dur_v is None else f"{dur_v:.3f}",
            "duration-mcp": "" if dur_m is None else f"{dur_m:.3f}",
        })

    out_csv.parent.mkdir(parents=True, exist_ok=True)
    write_output(rows, out_csv)
    print(f"Wrote {len(rows)} rows → {out_csv}")

if __name__ == "__main__":
    main()
