#!/usr/bin/env python3
"""Test suite for proximity_class.py."""

import csv
import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))

from proximity_class import (
    Hunk,
    LCP_min,
    SF,
    SM,
    SP,
    build_hunks,
    classify,
    extract_method_from_header,
    longest_common_prefix,
)


# ── Fixtures ────────────────────────────────────────────────────────────────

def make_entry(*hunks):
    """hunks: iterable of (file, code) tuples."""
    return {
        "buggy_hunks": {str(i): {"file": f, "code": c} for i, (f, c) in enumerate(hunks)}
    }


# ── 1. extract_method_from_header ───────────────────────────────────────────

class TestExtractMethodFromHeader:
    def test_standard_def(self):
        assert extract_method_from_header(
            "@@ -76,9 +83,10 @@ def _check_required_columns(self):"
        ) == "_check_required_columns"

    def test_async_def(self):
        assert extract_method_from_header(
            "@@ -10,5 +10,7 @@ async def fetch(self):"
        ) == "fetch"

    def test_class(self):
        assert extract_method_from_header(
            "@@ -55,6 +55,13 @@ class BaseTimeSeries(QTable):"
        ) == "BaseTimeSeries"

    def test_no_trailing_context(self):
        assert extract_method_from_header("@@ -17,9 +17,9 @@") == "<module>"

    def test_empty_string(self):
        assert extract_method_from_header("") == "<module>"

    def test_single_line_range_no_comma(self):
        assert extract_method_from_header("@@ -55 +55 @@ def foo():") == "foo"

    def test_mixed_single_and_range(self):
        assert extract_method_from_header("@@ -1 +1,3 @@ class X:") == "X"

    def test_only_first_line_used(self):
        code = "@@ -1,2 +1,2 @@ def a():\n+    pass"
        assert extract_method_from_header(code) == "a"

    def test_raw_context_fallback(self):
        # Context that is neither def nor class falls through to raw
        assert extract_method_from_header(
            "@@ -1,1 +1,1 @@ if condition:"
        ) == "if condition:"

    def test_dunder_method(self):
        assert extract_method_from_header(
            "@@ -1,1 +1,1 @@ def __init__(self, x: int) -> None:"
        ) == "__init__"

    def test_garbage_header(self):
        assert extract_method_from_header("not a hunk header") == "<module>"

    def test_extra_whitespace_in_context(self):
        assert extract_method_from_header(
            "@@ -1,1 +1,1 @@   def  spaced  (  ):"
        ) == "spaced"


# ── 2. build_hunks ──────────────────────────────────────────────────────────

class TestBuildHunks:
    def test_multiple_hunks_count(self):
        entry = make_entry(
            ("a.py", "@@ -1,1 +1,1 @@ def f():"),
            ("b.py", "@@ -2,2 +2,2 @@ class C:"),
        )
        assert len(build_hunks(entry)) == 2

    def test_root_file_empty_pkg(self):
        entry = make_entry(("setup.py", "@@ -1,1 +1,1 @@ def f():"))
        h = build_hunks(entry)[0]
        assert h.pkg == []

    def test_nested_file_pkg(self):
        entry = make_entry(("a/b/c/x.py", "@@ -1,1 +1,1 @@ def f():"))
        h = build_hunks(entry)[0]
        assert h.pkg == ["a", "b", "c"]

    def test_missing_buggy_hunks(self):
        assert build_hunks({}) == []

    def test_missing_file_and_code(self):
        entry = {"buggy_hunks": {"0": {}}}
        h = build_hunks(entry)[0]
        assert h.file == ""
        assert h.method == "<module>"
        assert h.pkg == []

    def test_method_extracted_from_header(self):
        entry = make_entry(("pkg/m.py", "@@ -1,1 +1,1 @@ def repair(self):"))
        h = build_hunks(entry)[0]
        assert h.method == "repair"


# ── 3. longest_common_prefix ────────────────────────────────────────────────

class TestLongestCommonPrefix:
    def test_identical(self):
        assert longest_common_prefix(["a", "b", "c"], ["a", "b", "c"]) == 3

    def test_disjoint(self):
        assert longest_common_prefix(["a"], ["b"]) == 0

    def test_partial(self):
        assert longest_common_prefix(["a", "b", "c"], ["a", "b", "d"]) == 2

    def test_one_empty(self):
        assert longest_common_prefix([], ["a"]) == 0

    def test_both_empty(self):
        assert longest_common_prefix([], []) == 0

    def test_prefix_of(self):
        assert longest_common_prefix(["a", "b"], ["a", "b", "c"]) == 2


# ── 4. SF / SM / SP ─────────────────────────────────────────────────────────

class TestPredicates:
    def test_single_hunk_all_true(self):
        H = [Hunk("a/x.py", "f", ["a"])]
        assert SF(H) and SM(H) and SP(H)

    def test_all_same(self):
        H = [Hunk("a/x.py", "f", ["a"]), Hunk("a/x.py", "f", ["a"])]
        assert SF(H) and SM(H) and SP(H)

    def test_same_file_diff_method(self):
        H = [Hunk("a/x.py", "f", ["a"]), Hunk("a/x.py", "g", ["a"])]
        assert SF(H)
        assert not SM(H)

    def test_diff_file_same_pkg(self):
        H = [Hunk("a/x.py", "f", ["a"]), Hunk("a/y.py", "g", ["a"])]
        assert not SF(H)
        assert SP(H)

    def test_diff_pkg(self):
        H = [Hunk("a/x.py", "f", ["a"]), Hunk("b/y.py", "g", ["b"])]
        assert not SP(H)


# ── 5. LCP_min ──────────────────────────────────────────────────────────────

class TestLCPMin:
    def test_zero_hunks(self):
        assert LCP_min([]) == 0

    def test_single_hunk(self):
        assert LCP_min([Hunk("a.py", "f", ["a"])]) == 0

    def test_two_hunks(self):
        H = [Hunk("a/b/x.py", "f", ["a", "b"]), Hunk("a/c/y.py", "g", ["a", "c"])]
        assert LCP_min(H) == 1

    def test_min_not_mean_across_three(self):
        # Two hunks share deep prefix; third is disjoint.
        # min pairwise LCP must be 0, not the average.
        H = [
            Hunk("a/b/c/x.py", "f", ["a", "b", "c"]),
            Hunk("a/b/c/y.py", "g", ["a", "b", "c"]),
            Hunk("z/q.py", "h", ["z"]),
        ]
        assert LCP_min(H) == 0

    def test_deep_shared_prefix(self):
        H = [
            Hunk("a/b/c/x.py", "f", ["a", "b", "c"]),
            Hunk("a/b/c/y.py", "g", ["a", "b", "c"]),
        ]
        assert LCP_min(H) == 3


# ── 6. classify ─────────────────────────────────────────────────────────────

class TestClassify:
    def test_nucleus(self):
        H = [Hunk("a/x.py", "f", ["a"]), Hunk("a/x.py", "f", ["a"])]
        assert classify(H, cutoff=0) == "Nucleus"

    def test_cluster(self):
        H = [Hunk("a/x.py", "f", ["a"]), Hunk("a/x.py", "g", ["a"])]
        assert classify(H, cutoff=0) == "Cluster"

    def test_orbit(self):
        H = [Hunk("a/x.py", "f", ["a"]), Hunk("a/y.py", "g", ["a"])]
        assert classify(H, cutoff=0) == "Orbit"

    def test_sprawl(self):
        # LCP = 2, cutoff = 1 → 2 > 1 → Sprawl
        H = [
            Hunk("a/b/c/x.py", "f", ["a", "b", "c"]),
            Hunk("a/b/d/y.py", "g", ["a", "b", "d"]),
        ]
        assert classify(H, cutoff=1) == "Sprawl"

    def test_fragment(self):
        # Same hunks, cutoff = 2 → 2 not > 2 → Fragment
        H = [
            Hunk("a/b/c/x.py", "f", ["a", "b", "c"]),
            Hunk("a/b/d/y.py", "g", ["a", "b", "d"]),
        ]
        assert classify(H, cutoff=2) == "Fragment"

    def test_single_hunk_is_nucleus(self):
        H = [Hunk("a/x.py", "f", ["a"])]
        assert classify(H, cutoff=0) == "Nucleus"

    def test_boundary_strictly_greater(self):
        # LCP exactly equals cutoff → Fragment (asserts `>` not `>=`)
        H = [
            Hunk("a/b/x.py", "f", ["a", "b"]),
            Hunk("a/c/y.py", "g", ["a", "c"]),
        ]
        # LCP = 1, cutoff = 1 → not > → Fragment
        assert classify(H, cutoff=1) == "Fragment"


# ── 7. main / CLI integration ───────────────────────────────────────────────

SCRIPT = Path(__file__).parent / "proximity_class.py"


def _run(input_json: Path, output_csv: Path, *extra):
    return subprocess.run(
        [sys.executable, str(SCRIPT), str(input_json), str(output_csv), *extra],
        capture_output=True,
        text=True,
        check=False,
    )


class TestMainIntegration:
    def test_csv_header_and_rows(self, tmp_path):
        data = {
            "bug-1": make_entry(
                ("pkg/a.py", "@@ -1,1 +1,1 @@ def f():"),
                ("pkg/a.py", "@@ -2,1 +2,1 @@ def f():"),
            ),
            "bug-2": make_entry(
                ("pkg/a.py", "@@ -1,1 +1,1 @@ def f():"),
                ("pkg/a.py", "@@ -2,1 +2,1 @@ def g():"),
            ),
            "bug-3": make_entry(
                ("pkg/a.py", "@@ -1,1 +1,1 @@ def f():"),
                ("pkg/b.py", "@@ -2,1 +2,1 @@ def g():"),
            ),
        }
        in_json = tmp_path / "in.json"
        out_csv = tmp_path / "out.csv"
        in_json.write_text(json.dumps(data))

        r = _run(in_json, out_csv)
        assert r.returncode == 0, r.stderr

        with open(out_csv) as fh:
            rows = list(csv.reader(fh))
        assert rows[0] == ["issue_id", "proximity_class"]
        assert len(rows) == 1 + len(data)

        result = dict(rows[1:])
        assert result["bug-1"] == "Nucleus"
        assert result["bug-2"] == "Cluster"
        assert result["bug-3"] == "Orbit"

    def test_threshold_override(self, tmp_path):
        # Two hunks across deep packages; classification depends on cutoff.
        data = {
            "bug-1": make_entry(
                ("a/b/c/x.py", "@@ -1,1 +1,1 @@ def f():"),
                ("a/b/d/y.py", "@@ -2,1 +2,1 @@ def g():"),
            ),
        }
        in_json = tmp_path / "in.json"
        in_json.write_text(json.dumps(data))

        out1 = tmp_path / "out1.csv"
        r1 = _run(in_json, out1, "--threshold", "1")
        assert r1.returncode == 0
        assert dict(list(csv.reader(open(out1)))[1:])["bug-1"] == "Sprawl"

        out2 = tmp_path / "out2.csv"
        r2 = _run(in_json, out2, "--threshold", "2")
        assert r2.returncode == 0
        assert dict(list(csv.reader(open(out2)))[1:])["bug-1"] == "Fragment"

    def test_default_cutoff_logged(self, tmp_path):
        data = {
            "bug-1": make_entry(
                ("a/b/c/d/x.py", "@@ -1,1 +1,1 @@ def f():"),
                ("a/b/c/d/y.py", "@@ -2,1 +2,1 @@ def g():"),
            ),
        }
        in_json = tmp_path / "in.json"
        out_csv = tmp_path / "out.csv"
        in_json.write_text(json.dumps(data))

        r = _run(in_json, out_csv)
        assert r.returncode == 0
        # median module depth = 4, floor(4/2) = 2
        assert "Median module depth = 4" in r.stdout
        assert "cutoff = 2" in r.stdout

    def test_empty_input(self, tmp_path):
        in_json = tmp_path / "in.json"
        out_csv = tmp_path / "out.csv"
        in_json.write_text("{}")

        r = _run(in_json, out_csv)
        assert r.returncode == 0
        with open(out_csv) as fh:
            rows = list(csv.reader(fh))
        assert rows == [["issue_id", "proximity_class"]]
        assert "cutoff = 0" in r.stdout


# ── 8. Resource-backed tests (one real bug per proximity class) ─────────────

RESOURCES = Path(__file__).parent / "resources"

# Maps proximity class -> (fixture file, expected bug_id).
# Each fixture contains the buggy_hunks of one real SWE-bench multi-hunk bug,
# pre-classified by proximity_class.py at the global cutoff (1) computed
# across the 32-bug subset.
RESOURCE_CASES = [
    ("Nucleus",  "nucleus.json",  "django__django-11740"),
    ("Cluster",  "cluster.json",  "astropy__astropy-13033"),
    ("Orbit",    "orbit.json",    "astropy__astropy-14369"),
    ("Sprawl",   "sprawl.json",   "django__django-11138"),
    ("Fragment", "fragment.json", "django__django-11400"),
]


class TestResourceFixtures:
    @pytest.mark.parametrize("expected_class, fixture, bug_id", RESOURCE_CASES)
    def test_classify_in_memory(self, expected_class, fixture, bug_id):
        data = json.loads((RESOURCES / fixture).read_text())
        assert bug_id in data
        H = build_hunks(data[bug_id])
        # Cutoff = 1 matches the value computed on the full 32-bug subset.
        assert classify(H, cutoff=1) == expected_class

    @pytest.mark.parametrize("expected_class, fixture, bug_id", RESOURCE_CASES)
    def test_classify_via_cli(self, tmp_path, expected_class, fixture, bug_id):
        out_csv = tmp_path / "out.csv"
        r = _run(RESOURCES / fixture, out_csv, "--threshold", "1")
        assert r.returncode == 0, r.stderr
        rows = list(csv.reader(open(out_csv)))
        assert rows[0] == ["issue_id", "proximity_class"]
        result = dict(rows[1:])
        assert result[bug_id] == expected_class


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
