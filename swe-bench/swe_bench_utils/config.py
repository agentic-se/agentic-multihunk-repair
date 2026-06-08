"""Bug list + SWE-bench record loading + prompt rendering."""

import json
from pathlib import Path

# Paths relative to swe-bench/ directory
SWE_BENCH_DIR = Path(__file__).resolve().parent.parent
MULTIHUNK_JSON = SWE_BENCH_DIR / "swe_bench_verified" / "multihunk_bugs_swe_bench_verified_32.json"
SWEBENCH_JSONL = SWE_BENCH_DIR / "swe_bench_verified" / "swe_bench.jsonl"
DEFAULT_PROMPT = SWE_BENCH_DIR / "swe_bench_utils" / "prompt.md"


def load_multihunk_bugs(path: Path = MULTIHUNK_JSON) -> dict:
    """Load the multihunk bugs list (instance_id -> buggy_hunks)."""
    return json.loads(path.read_text(encoding="utf-8"))


def load_swebench_records(instance_ids: set, jsonl_path: Path = SWEBENCH_JSONL) -> dict:
    """Return a dict {instance_id: record} for the requested IDs."""
    out = {}
    with open(jsonl_path) as f:
        for line in f:
            if not line.strip():
                continue
            r = json.loads(line)
            if r["instance_id"] in instance_ids:
                out[r["instance_id"]] = r
    return out


def _as_list(v) -> list[str]:
    return json.loads(v) if isinstance(v, str) else (v or [])


def get_fail_to_pass(record: dict) -> list[str]:
    return _as_list(record.get("FAIL_TO_PASS", "[]"))


def get_pass_to_pass(record: dict) -> list[str]:
    return _as_list(record.get("PASS_TO_PASS", "[]"))


def render_prompt(template_path: Path, record: dict) -> str:
    """
    Render the agent prompt. Substitutes:
      {{problem_statement}}, {{fail_to_pass}}, {{hints_section}}.
    """
    fail_to_pass = "\n".join(get_fail_to_pass(record))
    hints = (record.get("hints_text") or "").strip()
    hints_section = f"**Additional Hints**:\n{hints}\n" if hints else ""

    return (template_path.read_text(encoding="utf-8")
            .replace("{{problem_statement}}", record.get("problem_statement", ""))
            .replace("{{fail_to_pass}}", fail_to_pass)
            .replace("{{hints_section}}", hints_section))
