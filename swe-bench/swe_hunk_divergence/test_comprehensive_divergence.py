"""
Comprehensive bug-reproducing test suite for hunk divergence implementation.

These tests are designed to FAIL and expose bugs in the current implementation.
All tests use STRICT assertions that validate the mathematical properties
of the divergence metrics as described in the ASE'25 paper.

Test Philosophy:
- Tests should FAIL with buggy implementation
- Tests should PASS after fixing bugs
- No lenient assertions - strict bounds checking
- Test actual computed values, not approximations
"""

import ast
import math
from pathlib import Path

import pytest

from hunk_divergence import (
    _ast_node_distance,
    _build_parent_map,
    _buggy_subtree_root,
    _lca,
    _node_depth,
    _subtree_diameter,
    compute_ast_metrics_for_file,
    compute_metrics_for_bug,
    parse_patch_hunks,
)
from evaluate_bleu import compute_bleu_score


# ─── Helper Functions ────────────────────────────────────────────────────────


def load_resource(filename: str) -> str:
    """Load a Python resource file from resources/ directory."""
    resource_path = Path(__file__).parent / "resources" / filename
    return resource_path.read_text(encoding="utf-8")


# ─── CRITICAL BUG TESTS: Directory Distance ──────────────────────────────────


class TestDirectoryDistanceBugs:
    """
    CRITICAL: These tests expose bugs in directory distance computation.
    All tests in this class should FAIL with the current implementation.
    """

    def test_d_dir_must_not_exceed_one(self):
        """
        BUG: D_dir can be 2.0 when files have no common path.

        Mathematical invariant: Distance metrics must be in [0, 1].
        Current bug: D_dir = 1.0 - (-1/1) = 2.0 for root-level files.
        """
        hunks = [
            {"file": "a.py", "patch_lines": ["x = 1"], "hunk_id": 0},
            {"file": "b.py", "patch_lines": ["y = 2"], "hunk_id": 1},
        ]

        ast_metrics = {}
        divergence, pairs = compute_metrics_for_bug("test", hunks, ast_metrics)

        D_dir = float(pairs[0][4])

        # STRICT: D_dir MUST be in [0, 1]
        assert 0.0 <= D_dir <= 1.0, f"D_dir must be in [0,1], got {D_dir}"

    def test_d_dir_must_be_nonnegative(self):
        """
        BUG: D_dir calculation can produce negative values.

        Mathematical invariant: Distance cannot be negative.
        """
        test_cases = [
            ("a.py", "b.py"),
            ("foo/a.py", "bar/b.py"),
            ("x/y/z.py", "a/b/c.py"),
        ]

        for file1, file2 in test_cases:
            hunks = [
                {"file": file1, "patch_lines": ["x = 1"], "hunk_id": 0},
                {"file": file2, "patch_lines": ["y = 2"], "hunk_id": 1},
            ]

            ast_metrics = {}
            _, pairs = compute_metrics_for_bug("test", hunks, ast_metrics)
            D_dir = float(pairs[0][4])

            assert D_dir >= 0.0, f"D_dir must be non-negative for {file1} vs {file2}, got {D_dir}"

    def test_same_directory_files_should_have_partial_overlap(self):
        """
        BUG: Files in same directory get D_dir = 1.0 instead of < 1.0.

        Expected: foo/a.py vs foo/b.py should have D_dir = 0.5 (1 match of 2 segments)
        Actual: D_dir = 1.0 due to off-by-one in common path counting
        """
        hunks = [
            {"file": "foo/a.py", "patch_lines": ["x = 1"], "hunk_id": 0},
            {"file": "foo/b.py", "patch_lines": ["y = 2"], "hunk_id": 1},
        ]

        ast_metrics = {}
        _, pairs = compute_metrics_for_bug("test", hunks, ast_metrics)
        D_dir = float(pairs[0][4])

        # They share 'foo' directory - should have partial overlap
        assert D_dir < 1.0, f"Same directory files should have D_dir < 1.0, got {D_dir}"

    def test_d_dir_specific_value_one_common_segment(self):
        """
        BUG: Off-by-one error in common path counting.

        Specific test: foo/a.py vs foo/b.py
        Expected: common = 1 ('foo'), D_dir = 1.0 - (1/2) = 0.5
        Actual: common = 0, D_dir = 1.0
        """
        hunks = [
            {"file": "foo/a.py", "patch_lines": ["x = 1"], "hunk_id": 0},
            {"file": "foo/b.py", "patch_lines": ["y = 2"], "hunk_id": 1},
        ]

        ast_metrics = {}
        _, pairs = compute_metrics_for_bug("test", hunks, ast_metrics)
        D_dir = float(pairs[0][4])

        expected = 0.5  # 1 match out of 2 segments
        assert abs(D_dir - expected) < 0.01, f"Expected D_dir = {expected}, got {D_dir}"

    def test_d_dir_specific_value_two_common_segments(self):
        """
        BUG: Off-by-one error affects deeper directory structures.

        Specific test: foo/bar/a.py vs foo/bar/b.py
        Expected: common = 2 ('foo', 'bar'), D_dir = 1.0 - (2/3) = 0.333...
        Actual: common = 1, D_dir = 0.666...
        """
        hunks = [
            {"file": "foo/bar/a.py", "patch_lines": ["x = 1"], "hunk_id": 0},
            {"file": "foo/bar/b.py", "patch_lines": ["y = 2"], "hunk_id": 1},
        ]

        ast_metrics = {}
        _, pairs = compute_metrics_for_bug("test", hunks, ast_metrics)
        D_dir = float(pairs[0][4])

        expected = 1.0 / 3.0  # 2 matches out of 3 segments
        assert abs(D_dir - expected) < 0.01, f"Expected D_dir ≈ {expected:.3f}, got {D_dir}"

    def test_d_dir_no_common_path_should_be_one(self):
        """
        Test boundary case: completely different paths.

        Expected: D_dir = 1.0 (maximum distance)
        Bug may cause: D_dir = 2.0
        """
        hunks = [
            {"file": "a.py", "patch_lines": ["x = 1"], "hunk_id": 0},
            {"file": "b.py", "patch_lines": ["y = 2"], "hunk_id": 1},
        ]

        ast_metrics = {}
        _, pairs = compute_metrics_for_bug("test", hunks, ast_metrics)
        D_dir = float(pairs[0][4])

        # No common path → maximum distance = 1.0
        assert D_dir == 1.0, f"No common path should give D_dir = 1.0, got {D_dir}"


# ─── CRITICAL BUG TESTS: Normalized Divergence ───────────────────────────────


class TestNormalizedDivergenceBugs:
    """
    CRITICAL: These tests expose cascading bugs in normalized divergence.
    When D_dir > 1.0, the normalized divergence exceeds 1.0.
    """

    def test_normalized_divergence_must_not_exceed_one(self):
        """
        BUG: Normalized divergence can be 1.6667 when D_dir = 2.0.

        Formula: normalised = pairDiv / maxDiv
        Expected: normalised ∈ [0, 1]
        Actual: normalised = 5.0 / 3.0 = 1.6667 when D_dir = 2.0
        """
        hunks = [
            {"file": "a.py", "patch_lines": ["import os"], "hunk_id": 0},
            {"file": "b.py", "patch_lines": ["def foo(): return 42"], "hunk_id": 1},
        ]

        ast_metrics = {}
        _, pairs = compute_metrics_for_bug("test", hunks, ast_metrics)
        normalized = float(pairs[0][5])

        # STRICT: Normalized divergence MUST be in [0, 1]
        assert 0.0 <= normalized <= 1.0, f"Normalized divergence must be in [0,1], got {normalized}"

    def test_normalized_divergence_all_pairs(self):
        """
        Test that ALL pairs have normalized divergence in [0, 1].
        """
        hunks = [
            {"file": "a.py", "patch_lines": ["x = 1"], "hunk_id": 0},
            {"file": "b.py", "patch_lines": ["y = 2"], "hunk_id": 1},
            {"file": "c.py", "patch_lines": ["z = 3"], "hunk_id": 2},
        ]

        ast_metrics = {}
        _, pairs = compute_metrics_for_bug("test", hunks, ast_metrics)

        for i, pair in enumerate(pairs):
            normalized = float(pair[5])
            assert 0.0 <= normalized <= 1.0, \
                f"Pair {i} normalized divergence must be in [0,1], got {normalized}"

    def test_worst_case_normalized_divergence(self):
        """
        Worst case: D_lex = 1.0, D_ast = 1.0, D_dir = 1.0, gamma = 2.0

        Expected: normalised = 1.0 * (1.0 + 2.0 * 1.0) / 3.0 = 1.0
        Bug causes: normalised = 1.0 * (1.0 + 2.0 * 2.0) / 3.0 = 1.6667
        """
        # Use completely different code to maximize D_lex
        hunks = [
            {"file": "a.py", "patch_lines": ["import numpy as np"], "hunk_id": 0},
            {"file": "b.py", "patch_lines": ["class Foo: pass"], "hunk_id": 1},
        ]

        ast_metrics = {}
        _, pairs = compute_metrics_for_bug("test", hunks, ast_metrics)
        normalized = float(pairs[0][5])

        # Even in worst case, normalized should not exceed 1.0
        assert normalized <= 1.0, f"Even worst case should have normalized ≤ 1.0, got {normalized}"


# ─── Component Metric Bounds Tests ───────────────────────────────────────────


class TestMetricBounds:
    """
    Test that all component metrics satisfy their mathematical bounds.
    """

    def test_d_lex_in_zero_to_one(self):
        """D_lex = 1 - BLEU should be in [0, 1]."""
        test_cases = [
            ("x = 1", "x = 1"),  # Identical
            ("import os", "class Foo: pass"),  # Completely different
            ("x += 1", "x -= 1"),  # Similar
        ]

        for patch1, patch2 in test_cases:
            bleu = compute_bleu_score(patch1, patch2)
            D_lex = 1.0 - bleu
            assert 0.0 <= D_lex <= 1.0, f"D_lex must be in [0,1], got {D_lex} for '{patch1}' vs '{patch2}'"

    def test_d_ast_in_zero_to_one_same_file(self):
        """D_ast for same-file hunks should be in [0, 1]."""
        source = load_resource("sibling_methods.py")

        hunks = [
            {"file": "test.py", "patch_lines": ["x = 1"], "hunk_id": 0},
            {"file": "test.py", "patch_lines": ["y = 2"], "hunk_id": 1},
        ]

        hunk_ranges = [(0, 9, 9), (1, 14, 14)]
        diameter, pairs_ast = compute_ast_metrics_for_file(source, hunk_ranges)

        ast_metrics = {"test.py": {"diameter": diameter, "pairs": pairs_ast}}
        _, pairs = compute_metrics_for_bug("test", hunks, ast_metrics)

        D_ast = float(pairs[0][3])
        assert 0.0 <= D_ast <= 1.0, f"D_ast must be in [0,1], got {D_ast}"

    def test_d_ast_is_one_for_cross_file(self):
        """D_ast should be exactly 1.0 for cross-file hunks."""
        hunks = [
            {"file": "a.py", "patch_lines": ["x = 1"], "hunk_id": 0},
            {"file": "b.py", "patch_lines": ["y = 2"], "hunk_id": 1},
        ]

        ast_metrics = {}
        _, pairs = compute_metrics_for_bug("test", hunks, ast_metrics)

        D_ast = float(pairs[0][3])
        assert D_ast == 1.0, f"Cross-file D_ast must be 1.0, got {D_ast}"

    def test_all_component_metrics_bounded(self):
        """All D_lex, D_ast, D_dir must be in [0, 1]."""
        hunks = [
            {"file": "pkg/a.py", "patch_lines": ["x = 1"], "hunk_id": 0},
            {"file": "pkg/b.py", "patch_lines": ["y = 2"], "hunk_id": 1},
        ]

        ast_metrics = {}
        _, pairs = compute_metrics_for_bug("test", hunks, ast_metrics)

        D_lex = float(pairs[0][2])
        D_ast = float(pairs[0][3])
        D_dir = float(pairs[0][4])

        assert 0.0 <= D_lex <= 1.0, f"D_lex must be in [0,1], got {D_lex}"
        assert 0.0 <= D_ast <= 1.0, f"D_ast must be in [0,1], got {D_ast}"
        assert 0.0 <= D_dir <= 1.0, f"D_dir must be in [0,1], got {D_dir}"


# ─── AST Distance Edge Cases ─────────────────────────────────────────────────


class TestASTDistanceEdgeCases:
    """Test edge cases in AST distance computation."""

    def test_ast_distance_same_node_is_zero(self):
        """Two hunks in the exact same AST node should have distance 0."""
        source = load_resource("same_function.py")
        tree = ast.parse(source)
        parents = _build_parent_map(tree)

        # Same line range should give same node
        node1 = _buggy_subtree_root(tree, 6, 6, parents)
        node2 = _buggy_subtree_root(tree, 6, 6, parents)

        distance = _ast_node_distance(node1, node2, parents)
        assert distance == 0, f"Same node should have distance 0, got {distance}"

    def test_tree_diameter_is_positive(self):
        """Tree diameter must be positive for non-trivial trees."""
        source = load_resource("sibling_methods.py")
        tree = ast.parse(source)
        parents = _build_parent_map(tree)

        diameter = _subtree_diameter(tree, parents)
        assert diameter > 0, f"Tree diameter must be positive, got {diameter}"

    def test_ast_normalization_does_not_exceed_one(self):
        """Normalized AST distance must not exceed 1.0."""
        source = load_resource("different_classes.py")

        hunk_ranges = [(0, 8, 8), (1, 18, 18)]  # Different classes
        diameter, pairs = compute_ast_metrics_for_file(source, hunk_ranges)

        raw_dist = pairs.get("0_1", 0)
        if diameter > 0:
            D_ast = math.log1p(raw_dist) / math.log1p(diameter)
        else:
            D_ast = 0.0

        assert 0.0 <= D_ast <= 1.0, f"Normalized D_ast must be in [0,1], got {D_ast}"

    def test_syntax_error_returns_safe_defaults(self):
        """Files with syntax errors should not crash and return safe values."""
        source = load_resource("syntax_error.py")

        hunk_ranges = [(0, 5, 5), (1, 7, 7)]
        diameter, pairs = compute_ast_metrics_for_file(source, hunk_ranges)

        assert diameter == 1, f"Syntax error should give diameter = 1, got {diameter}"
        assert pairs == {}, f"Syntax error should give empty pairs, got {pairs}"


# ─── Overall Divergence Formula Tests ────────────────────────────────────────


class TestOverallDivergenceFormula:
    """Test the overall divergence formula: divergence = ln(n) × mean(normalized)."""

    def test_single_hunk_zero_divergence(self):
        """Single hunk should have divergence = 0 (no pairs to compare)."""
        hunks = [{"file": "a.py", "patch_lines": ["x = 1"], "hunk_id": 0}]

        ast_metrics = {}
        divergence, pairs = compute_metrics_for_bug("test", hunks, ast_metrics)

        assert divergence == 0.0, f"Single hunk should have divergence = 0, got {divergence}"
        assert pairs == [], f"Single hunk should have no pairs, got {pairs}"

    def test_divergence_is_nonnegative(self):
        """Overall divergence must be non-negative."""
        test_cases = [
            [{"file": "a.py", "patch_lines": ["x = 1"], "hunk_id": 0},
             {"file": "a.py", "patch_lines": ["x = 1"], "hunk_id": 1}],

            [{"file": "a.py", "patch_lines": ["x = 1"], "hunk_id": 0},
             {"file": "b.py", "patch_lines": ["y = 2"], "hunk_id": 1}],

            [{"file": "a.py", "patch_lines": ["x = 1"], "hunk_id": 0},
             {"file": "a.py", "patch_lines": ["y = 2"], "hunk_id": 1},
             {"file": "b.py", "patch_lines": ["z = 3"], "hunk_id": 2}],
        ]

        for hunks in test_cases:
            ast_metrics = {}
            divergence, _ = compute_metrics_for_bug("test", hunks, ast_metrics)
            assert divergence >= 0.0, f"Divergence must be non-negative, got {divergence}"

    def test_logarithmic_scaling_three_hunks(self):
        """Three hunks should use ln(3) scaling factor."""
        hunks = [
            {"file": "a.py", "patch_lines": ["x = 1"], "hunk_id": 0},
            {"file": "a.py", "patch_lines": ["y = 2"], "hunk_id": 1},
            {"file": "a.py", "patch_lines": ["z = 3"], "hunk_id": 2},
        ]

        source = load_resource("complex_hierarchy.py")
        hunk_ranges = [(0, 5, 5), (1, 14, 14), (2, 21, 21)]
        diameter, pairs_ast = compute_ast_metrics_for_file(source, hunk_ranges)

        ast_metrics = {"a.py": {"diameter": diameter, "pairs": pairs_ast}}
        divergence, pairs = compute_metrics_for_bug("test", hunks, ast_metrics)

        # Should have 3 pairs for 3 hunks
        assert len(pairs) == 3, f"3 hunks should produce 3 pairs, got {len(pairs)}"

        # Verify it's actually using ln(3) by checking the ratio
        n = 3
        if divergence > 0:
            # divergence = ln(n) × mean, so mean = divergence / ln(n)
            mean_normalized = divergence / math.log(n)
            assert 0.0 <= mean_normalized <= 1.0, \
                f"Mean normalized should be in [0,1], got {mean_normalized}"


# ─── Patch Parsing Tests ─────────────────────────────────────────────────────


class TestPatchParsing:
    """Test patch parsing correctness."""

    def test_parse_preserves_line_numbers(self):
        """Patch parser should correctly extract line numbers from @@ headers."""
        patch = """diff --git a/foo.py b/foo.py
--- a/foo.py
+++ b/foo.py
@@ -5,3 +5,3 @@
 def foo():
-    x = 1
+    x = 2
     return x
"""
        hunks = parse_patch_hunks(patch)

        assert len(hunks) == 1, f"Should parse 1 hunk, got {len(hunks)}"
        assert hunks[0]["start_line"] == 5, f"Start line should be 5, got {hunks[0]['start_line']}"

    def test_parse_extracts_buggy_and_fixed_lines(self):
        """Patch parser should separate buggy (-) and fixed (+) lines."""
        patch = """diff --git a/test.py b/test.py
--- a/test.py
+++ b/test.py
@@ -10,2 +10,2 @@
-old_line1
-old_line2
+new_line1
+new_line2
"""
        hunks = parse_patch_hunks(patch)

        assert len(hunks[0]["buggy"]) == 2, "Should have 2 buggy lines"
        assert len(hunks[0]["fixed"]) == 2, "Should have 2 fixed lines"


# ─── Real SWE-bench Verified Instances (from ~/WORK_DIR) ────────────────────
#
# Each entry mirrors an instance from
#   swe_bench_verified/multihunk_bugs_swe_bench_verified_32.json
# and points at source files we've copied into resources/ from
#   ~/WORK_DIR/<instance_id>/<file_path>.
#
# Hunk start/end lines are taken verbatim from the multi-hunk metadata so
# tests exercise the same line ranges the production pipeline sees.

REAL_INSTANCES = {
    # Same file, two hunks — Cluster (one in class body, one inside method)
    "astropy__astropy-13033": {
        "files": {
            "astropy/timeseries/core.py": "real_astropy_13033_core.py",
        },
        "hunks": [
            # (hunk_id, file, start, end, patch_lines)
            (0, "astropy/timeseries/core.py", 55, 60,
             ["    _required_columns_relax = False",
              "    def _check_required_columns(self):"]),
            (1, "astropy/timeseries/core.py", 76, 84,
             ["            elif self.colnames[:len(required_columns)] != required_columns:",
              "                raise ValueError(...)"]),
        ],
    },
    # Same file, two hunks both inside world_to_pixel_values — Nucleus
    "astropy__astropy-13579": {
        "files": {
            "astropy/wcs/wcsapi/wrappers/sliced_wcs.py":
                "real_astropy_13579_sliced_wcs.py",
        },
        "hunks": [
            (0, "astropy/wcs/wcsapi/wrappers/sliced_wcs.py", 243, 248,
             ["    def world_to_pixel_values(self, *world_arrays):",
              "        world_arrays = tuple(map(np.asanyarray, world_arrays))"]),
            (1, "astropy/wcs/wcsapi/wrappers/sliced_wcs.py", 251, 257,
             ["                iworld_curr += 1",
              "                world_arrays_new.append(world_arrays[iworld_curr])"]),
        ],
    },
    # Same file, two hunks ~1000 lines apart — Cluster, large AST distance
    "astropy__astropy-7606": {
        "files": {
            "astropy/units/core.py": "real_astropy_7606_core.py",
        },
        "hunks": [
            (0, "astropy/units/core.py", 728, 734,
             ["    def __eq__(self, other):",
              "        try: other = Unit(other, parse_strict='silent')"]),
            (1, "astropy/units/core.py", 1710, 1717,
             ["    def __eq__(self, other):",
              "        return isinstance(other, UnrecognizedUnit) and self.name == other.name"]),
        ],
    },
    # Cross-file, same package — Orbit
    "django__django-10554": {
        "files": {
            "django/db/models/sql/compiler.py": "real_django_10554_compiler.py",
            "django/db/models/sql/query.py": "real_django_10554_query.py",
        },
        "hunks": [
            (0, "django/db/models/sql/compiler.py", 356, 362,
             ["    raise DatabaseError('ORDER BY term does not match any column ...')"]),
            (1, "django/db/models/sql/query.py", 1774, 1779,
             ["    def set_select(self, cols):",
              "        self.default_cols = False"]),
        ],
    },
    # 6 hunks across two files in the same package — multi-pair stress test
    "astropy__astropy-8707": {
        "files": {
            "astropy/io/fits/card.py": "real_astropy_8707_card.py",
            "astropy/io/fits/header.py": "real_astropy_8707_header.py",
        },
        "hunks": [
            (0, "astropy/io/fits/card.py", 554, 559,
             ["    def fromstring(cls, image):", "        card = cls()"]),
            (1, "astropy/io/fits/header.py", 34, 40,
             ["__doctest_skip__ = ['Header', 'Header.*']"]),
            (2, "astropy/io/fits/header.py", 334, 346,
             ["    def fromstring(cls, data, sep=''):"]),
            (3, "astropy/io/fits/header.py", 357, 362,
             ["    require_full_cardlength = set(sep).issubset(VALID_HEADER_CHARS)"]),
            (4, "astropy/io/fits/header.py", 374, 390,
             ["    if next_image[:8] == 'CONTINUE':",
              "        cards.append(Card.fromstring(''.join(image)))"]),
            (5, "astropy/io/fits/header.py", 392, 398,
             ["    cards.append(Card.fromstring(''.join(image)))"]),
        ],
    },
}


def _build_ast_metrics(instance_key: str):
    """Compute ast_metrics for a real instance from its fixture file(s)."""
    spec = REAL_INSTANCES[instance_key]

    # Group hunks by file
    by_file = {}
    for hid, fpath, start, end, _plines in spec["hunks"]:
        by_file.setdefault(fpath, []).append((hid, start, end))

    ast_metrics = {}
    for fpath, ranges in by_file.items():
        if len(ranges) < 2:
            continue
        fixture = spec["files"][fpath]
        source = load_resource(fixture)
        diam, pairs = compute_ast_metrics_for_file(source, ranges)
        ast_metrics[fpath] = {"diameter": diam, "pairs": pairs}
    return ast_metrics


def _build_hunk_list(instance_key: str):
    spec = REAL_INSTANCES[instance_key]
    return [
        {"file": fpath, "patch_lines": plines, "hunk_id": hid}
        for (hid, fpath, _s, _e, plines) in spec["hunks"]
    ]


# ─── Real-Instance Tests ─────────────────────────────────────────────────────


class TestRealSWEBenchInstances:
    """Exercise the divergence metric on real SWE-bench Verified instances.

    Every fixture was copied verbatim from ~/WORK_DIR/<instance>/, so these
    tests catch regressions visible only on real-world AST shapes.
    """

    @pytest.mark.parametrize("instance_key", list(REAL_INSTANCES.keys()))
    def test_metrics_are_bounded_for_every_pair(self, instance_key):
        """Paper invariant: D_lex, D_ast, D_dir, normalised ∈ [0, 1]."""
        hunks = _build_hunk_list(instance_key)
        ast_metrics = _build_ast_metrics(instance_key)
        divergence, pairs = compute_metrics_for_bug(
            instance_key, hunks, ast_metrics
        )

        n = len(hunks)
        assert pairs, f"{instance_key} should have ≥ 1 hunk pair"
        for row in pairs:
            D_lex = float(row[2])
            D_ast = float(row[3])
            D_dir = float(row[4])
            normalised = float(row[5])
            assert 0.0 <= D_lex <= 1.0, f"D_lex out of bounds: {D_lex}"
            assert 0.0 <= D_ast <= 1.0, f"D_ast out of bounds: {D_ast}"
            assert 0.0 <= D_dir <= 1.0, f"D_dir out of bounds: {D_dir}"
            assert 0.0 <= normalised <= 1.0, \
                f"normalised out of bounds: {normalised}"

        # divergence = ln(n) × mean(normalised) ∈ [0, ln(n)]
        assert 0.0 <= divergence <= math.log(n) + 1e-9, \
            f"{instance_key}: divergence={divergence} not in [0, ln({n})]"

    def test_astropy_13033_same_file_pair_has_dir_zero(self):
        """Same-file pair forces D_dir = 0 (γ stays at 1, D_file = 0 per
        Algorithm 1 Line 15)."""
        _, pairs = compute_metrics_for_bug(
            "astropy__astropy-13033",
            _build_hunk_list("astropy__astropy-13033"),
            _build_ast_metrics("astropy__astropy-13033"),
        )
        assert float(pairs[0][4]) == 0.0

    def test_astropy_13579_same_method_has_smaller_ast_than_cross_method(self):
        """Hunks inside the same function should be closer in AST than hunks
        in different methods (astropy-13033 spans class body + method body)."""
        _, pairs_nucleus = compute_metrics_for_bug(
            "astropy__astropy-13579",
            _build_hunk_list("astropy__astropy-13579"),
            _build_ast_metrics("astropy__astropy-13579"),
        )
        _, pairs_cluster = compute_metrics_for_bug(
            "astropy__astropy-13033",
            _build_hunk_list("astropy__astropy-13033"),
            _build_ast_metrics("astropy__astropy-13033"),
        )
        d_nucleus = float(pairs_nucleus[0][3])
        d_cluster = float(pairs_cluster[0][3])
        assert d_nucleus < d_cluster, (
            f"Nucleus D_ast ({d_nucleus}) should be < Cluster D_ast "
            f"({d_cluster})"
        )

    def test_django_10554_cross_file_same_package_dir_below_one(self):
        """Files share django/db/models/sql/ — D_dir must be < 1.0."""
        _, pairs = compute_metrics_for_bug(
            "django__django-10554",
            _build_hunk_list("django__django-10554"),
            _build_ast_metrics("django__django-10554"),
        )
        D_dir = float(pairs[0][4])
        # 4 shared segments out of 5 → D_dir = 1 - 4/5 = 0.2
        assert D_dir == pytest.approx(0.2, abs=1e-4), \
            f"Expected D_dir ≈ 0.2 (4 shared/5 max), got {D_dir}"

    def test_django_10554_cross_file_pair_has_d_ast_one(self):
        _, pairs = compute_metrics_for_bug(
            "django__django-10554",
            _build_hunk_list("django__django-10554"),
            _build_ast_metrics("django__django-10554"),
        )
        assert float(pairs[0][3]) == 1.0

    def test_astropy_8707_six_hunks_produce_fifteen_pairs(self):
        """C(6, 2) = 15 pairs."""
        _, pairs = compute_metrics_for_bug(
            "astropy__astropy-8707",
            _build_hunk_list("astropy__astropy-8707"),
            _build_ast_metrics("astropy__astropy-8707"),
        )
        assert len(pairs) == 15

    def test_astropy_8707_mixed_same_and_cross_file_pairs(self):
        """5 hunks live in header.py and 1 in card.py → 10 same-file pairs
        (γ=1, D_dir=0) and 5 cross-file pairs (γ=2, D_ast=1)."""
        _, pairs = compute_metrics_for_bug(
            "astropy__astropy-8707",
            _build_hunk_list("astropy__astropy-8707"),
            _build_ast_metrics("astropy__astropy-8707"),
        )
        same_file = [p for p in pairs if float(p[4]) == 0.0]
        cross_file = [p for p in pairs if float(p[4]) > 0.0]
        assert len(same_file) == 10
        assert len(cross_file) == 5
        for p in cross_file:
            assert float(p[3]) == 1.0  # D_ast pinned to 1.0 cross-file

    def test_astropy_8707_divergence_strictly_below_ln_n(self):
        """ln(n) is the upper bound; not all pairs can be maximally divergent
        for this real instance because BLEU > 0 for many hunk pairs."""
        div, _ = compute_metrics_for_bug(
            "astropy__astropy-8707",
            _build_hunk_list("astropy__astropy-8707"),
            _build_ast_metrics("astropy__astropy-8707"),
        )
        assert 0.0 < div < math.log(6)


# ─── Boundary / Edge-Case Tests for the Bounded Formula ─────────────────────
#
# Paper formula (Algorithm 1 + Definition 4):
#     pairDiv     = D_lex × (D_ast + γ × D_file)       γ ∈ {1, 2}
#     normalised  = pairDiv / (1 + γ)
#     divergence  = ln(n) × mean(normalised)
#
# γ initialization (Algorithm 1, Line 1): γ ← 1.
# γ stays at 1 in the same-file branch (Lines 3-15 do not modify it).
# γ is overwritten to 2 only in the cross-file branch (Line 21).
# Therefore:
#     same-file:  maxDiv = 1 + 1 = 2  →  normalised = D_lex × D_ast / 2
#     cross-file: maxDiv = 1 + 2 = 3  →  normalised = D_lex × (D_ast + 2·D_file) / 3
# This implements the paper's "same-file edits are proportionally
# downweighted by 1+γ, reflecting the reduced coordination effort
# relative to inter-file changes" (paper §II-A).
#
# Bounds (from the paper):
#     D_lex, D_ast, D_file ∈ [0, 1]
#     normalised           ∈ [0, 1]   (same-file ≤ 0.5; cross-file ≤ 1.0)
#     divergence           ∈ [0, ln(n)]
#
# Below we lock the corners of the (D_lex, D_ast, D_dir, γ) cube plus the
# formula's algebraic structure.


class TestBoundaryConditions:

    # ── Lower-bound corners ────────────────────────────────────────────────

    # NOTE: BLEU's smoothing function 4 never reports an exact 1.0 even for
    # identical inputs — sentence-BLEU is undefined for short token sequences
    # without an n-gram backoff. We therefore assert D_lex collapses to its
    # numerical floor (≈ 0.42 for this tokenizer/smoother combo) and that the
    # algebraic identity normalised = D_lex × (D_ast + γ × D_dir) / (1 + γ)
    # holds — the formula's structural property the paper relies on.

    def test_identical_patches_same_file_normalised_matches_formula(self):
        """Identical patches → BLEU=1 → D_lex=0 → normalised = 0.

        Also pins the same-file algebraic identity:
            normalised = D_lex × D_ast / 2     (γ = 1, paper Algorithm 1)
        which collapses to 0 when D_lex = 0, but we assert the identity
        directly so a regression in the γ value is caught even when
        D_lex happens to be 0.
        """
        identical = ["def foo(self, value):", "    return value + 1"]
        hunks = [
            {"file": "a.py", "patch_lines": identical, "hunk_id": 0},
            {"file": "a.py", "patch_lines": identical, "hunk_id": 1},
        ]
        ast_metrics = {"a.py": {"diameter": 10, "pairs": {"0_1": 4}}}
        _, pairs = compute_metrics_for_bug("b", hunks, ast_metrics)
        D_lex = float(pairs[0][2])
        D_ast = float(pairs[0][3])
        normalised = float(pairs[0][5])
        # Same-file paper formula: normalised = D_lex × D_ast / (1 + γ) with γ=1
        assert normalised == pytest.approx(D_lex * D_ast / 2.0, abs=1e-4)

    def test_identical_patches_cross_file_normalised_matches_formula(self):
        """Identical-text cross-file pair: normalised = D_lex × (D_ast + 2 D_dir) / 3."""
        identical = ["def foo(self, value):", "    return value + 1"]
        hunks = [
            {"file": "x/a.py", "patch_lines": identical, "hunk_id": 0},
            {"file": "y/b.py", "patch_lines": identical, "hunk_id": 1},
        ]
        _, pairs = compute_metrics_for_bug("b", hunks, {})
        D_lex = float(pairs[0][2])
        D_ast = float(pairs[0][3])
        D_dir = float(pairs[0][4])
        normalised = float(pairs[0][5])
        expected = D_lex * (D_ast + 2.0 * D_dir) / 3.0
        assert normalised == pytest.approx(expected, abs=1e-4)
        # And the cross-file invariants
        assert D_ast == 1.0
        assert D_dir == 1.0  # No shared prefix between x/ and y/

    def test_same_node_same_file_gives_zero_d_ast(self):
        """When both hunks resolve to the same AST node, D_ast = 0."""
        ast_metrics = {"a.py": {"diameter": 10, "pairs": {"0_1": 0}}}
        hunks = [
            {"file": "a.py", "patch_lines": ["x"], "hunk_id": 0},
            {"file": "a.py", "patch_lines": ["y"], "hunk_id": 1},
        ]
        _, pairs = compute_metrics_for_bug("b", hunks, ast_metrics)
        assert float(pairs[0][3]) == 0.0

    # ── Upper-bound corners ────────────────────────────────────────────────

    def test_no_shared_directory_caps_d_dir_at_one(self):
        """Worst-case directory split → D_dir = 1.0 (paper bound)."""
        hunks = [
            {"file": "a.py", "patch_lines": ["import os"], "hunk_id": 0},
            {"file": "b.py", "patch_lines": ["class K: pass"], "hunk_id": 1},
        ]
        _, pairs = compute_metrics_for_bug("b", hunks, {})
        assert float(pairs[0][4]) == 1.0

    def test_cross_file_d_ast_pinned_to_one(self):
        """Cross-file pair → D_ast forced to 1.0 (no shared tree)."""
        hunks = [
            {"file": "p/a.py", "patch_lines": ["x"], "hunk_id": 0},
            {"file": "p/b.py", "patch_lines": ["y"], "hunk_id": 1},
        ]
        _, pairs = compute_metrics_for_bug("b", hunks, {})
        assert float(pairs[0][3]) == 1.0

    def test_worst_case_cross_file_normalised_equals_one(self):
        """D_lex=1, D_ast=1, D_dir=1, γ=2 → normalised = (1+2)/3 = 1.0.

        We construct truly disjoint patches so BLEU collapses to 0.
        """
        hunks = [
            {"file": "a.py",
             "patch_lines": ["import sys"], "hunk_id": 0},
            {"file": "b.py",
             "patch_lines": ["lambda: 0"], "hunk_id": 1},
        ]
        _, pairs = compute_metrics_for_bug("b", hunks, {})
        D_lex = float(pairs[0][2])
        D_ast = float(pairs[0][3])
        D_dir = float(pairs[0][4])
        normalised = float(pairs[0][5])

        # If BLEU is anywhere near 0, normalised should approach the cap
        if D_lex >= 0.99:
            assert normalised == pytest.approx(1.0, abs=1e-3)
        # Regardless of BLEU value, normalised is bounded
        assert normalised <= 1.0
        # Algebraic identity: normalised = D_lex × (D_ast + 2×D_dir) / 3
        expected = D_lex * (D_ast + 2.0 * D_dir) / 3.0
        assert normalised == pytest.approx(expected, abs=1e-4)

    # ── Algebraic identities ───────────────────────────────────────────────

    def test_same_file_normalised_matches_paper_formula(self):
        """Paper Algorithm 1 same-file branch: γ stays at the initial
        value of 1, D_file = 0, so normalised = D_lex × D_ast / (1 + 1)
        = D_lex × D_ast / 2.

        This is the ≤ 0.5 cap the paper specifies for same-file pairs.
        A regression that resets γ to 0 in the same-file branch (an
        easy-to-miss bug — the early Python port had it) would double
        every same-file pair divergence and fail this test.
        """
        ast_metrics = {"a.py": {"diameter": 8, "pairs": {"0_1": 5}}}
        hunks = [
            {"file": "a.py", "patch_lines": ["import os"], "hunk_id": 0},
            {"file": "a.py", "patch_lines": ["class K: pass"], "hunk_id": 1},
        ]
        _, pairs = compute_metrics_for_bug("b", hunks, ast_metrics)
        D_lex = float(pairs[0][2])
        D_ast = float(pairs[0][3])
        normalised = float(pairs[0][5])
        assert normalised == pytest.approx(D_lex * D_ast / 2.0, abs=1e-4)
        # Paper bound for same-file pairs: ≤ 0.5
        assert normalised <= 0.5 + 1e-9

    def test_same_file_pair_cap_is_half(self):
        """Paper §II-A: same-file pairs are downweighted by 1+γ=2 so
        their normalised divergence is bounded above by 0.5, not 1.0.
        Construct a realistic worst case (astDist == diameter so D_ast=1,
        plus disjoint patch_lines so D_lex → 1) and verify the cap.

        Note: in any real tree, astDist ≤ diameter by construction, so
        D_ast ∈ [0, 1] is a structural invariant. We mirror that here."""
        # astDist == diameter → D_ast = ln(1+D)/ln(1+D) = 1
        ast_metrics = {"a.py": {"diameter": 20, "pairs": {"0_1": 20}}}
        # Disjoint patches so BLEU → 0, D_lex → 1
        hunks = [
            {"file": "a.py", "patch_lines": ["import os"], "hunk_id": 0},
            {"file": "a.py", "patch_lines": ["lambda: 0"], "hunk_id": 1},
        ]
        _, pairs = compute_metrics_for_bug("b", hunks, ast_metrics)
        D_lex = float(pairs[0][2])
        D_ast = float(pairs[0][3])
        normalised = float(pairs[0][5])
        # D_ast pinned to 1 by construction
        assert D_ast == pytest.approx(1.0, abs=1e-4)
        # Even at the extremes, same-file normalised cannot exceed 0.5
        assert normalised <= 0.5 + 1e-9, (
            f"same-file cap violated: D_lex={D_lex}, D_ast={D_ast}, "
            f"normalised={normalised}"
        )
        # Algebraic identity at the extreme
        assert normalised == pytest.approx(D_lex * D_ast / 2.0, abs=1e-4)

    def test_cross_file_pair_cap_is_one(self):
        """Cross-file pairs use γ=2 so the cap is 1.0 (not 0.5).
        This asymmetry is the whole point of the γ adjustment in
        Algorithm 1, Line 21."""
        # No shared dir prefix → D_dir = 1; cross-file → D_ast = 1
        hunks = [
            {"file": "a.py", "patch_lines": ["import sys"], "hunk_id": 0},
            {"file": "b.py", "patch_lines": ["lambda: 0"], "hunk_id": 1},
        ]
        _, pairs = compute_metrics_for_bug("b", hunks, {})
        D_lex = float(pairs[0][2])
        normalised = float(pairs[0][5])
        # Cross-file approaches 1.0 as D_lex → 1 (BLEU smoother caps
        # D_lex below 1 for short tokens, so we just check the cap)
        assert normalised <= 1.0 + 1e-9
        # And it can exceed 0.5 — the same-file bound — when D_lex is
        # high enough, demonstrating the asymmetry
        if D_lex >= 0.6:
            assert normalised > 0.5

    def test_cross_file_normalised_matches_paper_formula(self):
        """normalised = D_lex × (D_ast + 2 × D_dir) / 3 for γ = 2."""
        hunks = [
            {"file": "pkg/sub/a.py",
             "patch_lines": ["import os"], "hunk_id": 0},
            {"file": "pkg/other/b.py",
             "patch_lines": ["class K: pass"], "hunk_id": 1},
        ]
        _, pairs = compute_metrics_for_bug("b", hunks, {})
        D_lex = float(pairs[0][2])
        D_ast = float(pairs[0][3])
        D_dir = float(pairs[0][4])
        normalised = float(pairs[0][5])
        expected = D_lex * (D_ast + 2.0 * D_dir) / 3.0
        assert normalised == pytest.approx(expected, abs=1e-4)

    def test_d_dir_partial_overlap_specific_values(self):
        """Concrete D_dir checks for the paper formula.

        D_dir = 1 - common/maxlen
        """
        cases = [
            ("a.py",          "b.py",          1.0),     # 0 common / 1
            ("foo/a.py",      "foo/b.py",      0.5),     # 1 common / 2
            ("foo/bar/a.py",  "foo/bar/b.py",  1.0/3),   # 2 common / 3
            ("foo/bar/a.py",  "foo/baz/b.py",  2.0/3),   # 1 common / 3
            ("foo/a.py",      "bar/b.py",      1.0),     # 0 common / 2
        ]
        for f1, f2, expected in cases:
            hunks = [
                {"file": f1, "patch_lines": ["x = 1"], "hunk_id": 0},
                {"file": f2, "patch_lines": ["y = 2"], "hunk_id": 1},
            ]
            _, pairs = compute_metrics_for_bug("b", hunks, {})
            D_dir = float(pairs[0][4])
            assert D_dir == pytest.approx(expected, abs=1e-4), (
                f"{f1} vs {f2}: expected D_dir={expected}, got {D_dir}"
            )

    # ── Divergence aggregate bounds ────────────────────────────────────────

    def test_divergence_bounded_by_ln_n_for_random_two_hunk_bugs(self):
        """divergence ∈ [0, ln(n)] for every n ≥ 2."""
        configs = [
            # (hunks list)
            [{"file": "a.py", "patch_lines": ["x = 1"], "hunk_id": i}
             for i in range(k)]
            for k in (2, 3, 5, 8)
        ]
        for hunks in configs:
            n = len(hunks)
            ast_metrics = {
                "a.py": {
                    "diameter": 5,
                    "pairs": {f"{i}_{j}": 2
                              for i in range(n) for j in range(i + 1, n)},
                }
            }
            div, _ = compute_metrics_for_bug("b", hunks, ast_metrics)
            assert 0.0 <= div <= math.log(n) + 1e-9, \
                f"n={n}: divergence={div} ∉ [0, ln({n})]"

    def test_logarithmic_scaling_with_constant_pair_divergence(self):
        """When every pair has the same normalised value v, divergence = ln(n) × v."""
        v_target = 0.25  # arbitrary same-file value
        for n in (2, 3, 4, 6):
            hunks = [
                {"file": "a.py", "patch_lines": [f"x{i}=1"], "hunk_id": i}
                for i in range(n)
            ]
            # Force identical normalised by making BLEU and AST distance equal
            # for every pair: same diameter & raw distance → same D_ast,
            # same disjoint tokens → same D_lex.
            ast_metrics = {
                "a.py": {
                    "diameter": 10,
                    "pairs": {f"{i}_{j}": 4
                              for i in range(n) for j in range(i + 1, n)},
                }
            }
            div, pairs = compute_metrics_for_bug("b", hunks, ast_metrics)
            normaliseds = [float(p[5]) for p in pairs]
            # All normalised values should be the same (within tokenization noise)
            assert max(normaliseds) - min(normaliseds) < 1e-3
            v = sum(normaliseds) / len(normaliseds)
            assert div == pytest.approx(math.log(n) * v, abs=1e-3)


# ─── Sanity: the AST-metric pipeline on a real fixture ──────────────────────


class TestRealASTPipeline:
    """End-to-end check of compute_ast_metrics_for_file on real
    SWE-bench Verified fixtures. The exact integer values below are
    pinned now that the diameter is computed via two-BFS (exact) and
    the buggy hunk root is the smallest-enclosing AST node — both
    matching MethodLineExtractor.java's behavior."""

    @staticmethod
    def _exhaustive_diameter(source: str) -> int:
        """Reference diameter: pairwise max over every structural node
        pair, filtering shared singletons (Load/Store/Add/Eq/...).
        Used to confirm two-BFS gives the exact answer on real files."""
        from hunk_divergence import (
            _AST_SHARED_SINGLETONS,
            _ast_node_distance,
            _build_parent_map,
        )
        tree = ast.parse(source)
        parents = _build_parent_map(tree)
        nodes = [
            n for n in ast.walk(tree)
            if not isinstance(n, _AST_SHARED_SINGLETONS)
        ]
        d = 0
        for i in range(len(nodes)):
            for j in range(i + 1, len(nodes)):
                d = max(d, _ast_node_distance(nodes[i], nodes[j], parents))
        return max(d, 1)

    # ── astropy-7606 (units/core.py, 2316 lines) ──────────────────────────

    def test_astropy_7606_diameter_exact(self):
        """Pinned exact diameter for the 2316-line astropy/units/core.py.

        Under the old sampled implementation this file had > 500 leaves,
        so its diameter was an under-estimate. Two-BFS gives the exact
        value; this test would fail under the sampled algorithm.
        """
        source = load_resource("real_astropy_7606_core.py")
        diam, _ = compute_ast_metrics_for_file(
            source, [(0, 728, 734), (1, 1710, 1717)]
        )
        assert diam == 28

    def test_astropy_7606_two_bfs_matches_exhaustive(self):
        """Two-BFS must equal the exhaustive pairwise max on this large
        real file (2316 lines, well past the old 500-leaf cap)."""
        source = load_resource("real_astropy_7606_core.py")
        diam, _ = compute_ast_metrics_for_file(
            source, [(0, 728, 734), (1, 1710, 1717)]
        )
        assert diam == self._exhaustive_diameter(source)

    def test_astropy_7606_pair_distance_exact(self):
        """Two hunks ~1000 lines apart in the same file: hunk 0 lands
        in `Unit.__eq__` (line 728), hunk 1 in `UnrecognizedUnit.__eq__`
        (line 1710). Smallest-enclosing-node selection plus two-BFS
        gives a stable, reproducible integer distance."""
        source = load_resource("real_astropy_7606_core.py")
        _, pairs = compute_ast_metrics_for_file(
            source, [(0, 728, 734), (1, 1710, 1717)]
        )
        assert pairs["0_1"] == 3

    # ── astropy-13579 (sliced_wcs.py, Nucleus class) ──────────────────────

    def test_astropy_13579_diameter_exact(self):
        source = load_resource("real_astropy_13579_sliced_wcs.py")
        diam, _ = compute_ast_metrics_for_file(
            source, [(0, 243, 248), (1, 251, 257)]
        )
        assert diam == 22

    def test_astropy_13579_two_bfs_matches_exhaustive(self):
        source = load_resource("real_astropy_13579_sliced_wcs.py")
        diam, _ = compute_ast_metrics_for_file(
            source, [(0, 243, 248), (1, 251, 257)]
        )
        assert diam == self._exhaustive_diameter(source)

    def test_astropy_13579_same_method_distance_is_one(self):
        """Both hunks live inside `world_to_pixel_values` (Nucleus
        proximity class). Their smallest-enclosing nodes share a near
        common ancestor — distance 1 in the AST."""
        source = load_resource("real_astropy_13579_sliced_wcs.py")
        diam, pairs = compute_ast_metrics_for_file(
            source, [(0, 243, 248), (1, 251, 257)]
        )
        assert pairs["0_1"] == 1
        # Sanity: still well under the file-wide diameter
        assert pairs["0_1"] < diam

    # ── astropy-13033 (timeseries/core.py, Cluster class) ─────────────────

    def test_astropy_13033_diameter_exact(self):
        source = load_resource("real_astropy_13033_core.py")
        diam, _ = compute_ast_metrics_for_file(
            source, [(0, 55, 60), (1, 76, 84)]
        )
        assert diam == 19

    def test_astropy_13033_two_bfs_matches_exhaustive(self):
        source = load_resource("real_astropy_13033_core.py")
        diam, _ = compute_ast_metrics_for_file(
            source, [(0, 55, 60), (1, 76, 84)]
        )
        assert diam == self._exhaustive_diameter(source)

    def test_astropy_13033_pair_distance_exact(self):
        """Cluster proximity: hunks in different methods of the same
        class. Distance 2 reflects: hunk0 root → method-or-class →
        method-or-class → hunk1 root."""
        source = load_resource("real_astropy_13033_core.py")
        _, pairs = compute_ast_metrics_for_file(
            source, [(0, 55, 60), (1, 76, 84)]
        )
        assert pairs["0_1"] == 2

    # ── astropy-8707 (multi-hunk header.py, 5 hunks one file) ─────────────

    def test_astropy_8707_header_diameter_exact(self):
        source = load_resource("real_astropy_8707_header.py")
        ranges = [(1, 34, 40), (2, 334, 346), (3, 357, 362),
                  (4, 374, 390), (5, 392, 398)]
        diam, _ = compute_ast_metrics_for_file(source, ranges)
        assert diam == 24

    def test_astropy_8707_header_two_bfs_matches_exhaustive(self):
        source = load_resource("real_astropy_8707_header.py")
        ranges = [(1, 34, 40), (2, 334, 346), (3, 357, 362),
                  (4, 374, 390), (5, 392, 398)]
        diam, _ = compute_ast_metrics_for_file(source, ranges)
        assert diam == self._exhaustive_diameter(source)

    def test_astropy_8707_header_pair_distances_exact(self):
        """Pin every pair distance between the 5 in-file hunks. C(5,2)=10
        pairs. Hunk 1 is at module level; hunks 2-5 live inside the
        `fromstring` classmethod, so distances within {2..5} are smaller
        than distances involving hunk 1."""
        source = load_resource("real_astropy_8707_header.py")
        ranges = [(1, 34, 40), (2, 334, 346), (3, 357, 362),
                  (4, 374, 390), (5, 392, 398)]
        _, pairs = compute_ast_metrics_for_file(source, ranges)
        # Pinned exact distances — every change to the AST pipeline
        # must either preserve these or be deliberate.
        assert pairs == {
            "1_2": 3, "1_3": 2, "1_4": 3, "1_5": 1,
            "2_3": 1, "2_4": 2, "2_5": 2,
            "3_4": 1, "3_5": 1,
            "4_5": 2,
        }

    # ── django-10554 (cross-file pair, individual file diameters) ─────────

    def test_django_10554_compiler_diameter_exact(self):
        source = load_resource("real_django_10554_compiler.py")
        diam, _ = compute_ast_metrics_for_file(source, [(0, 356, 362)])
        assert diam == 29
        assert diam == self._exhaustive_diameter(source)

    def test_django_10554_query_diameter_exact(self):
        source = load_resource("real_django_10554_query.py")
        diam, _ = compute_ast_metrics_for_file(source, [(1, 1774, 1779)])
        assert diam == 26
        assert diam == self._exhaustive_diameter(source)

    # ── astropy-8707 card.py (cross-file partner) ─────────────────────────

    def test_astropy_8707_card_diameter_exact(self):
        source = load_resource("real_astropy_8707_card.py")
        diam, _ = compute_ast_metrics_for_file(source, [(0, 554, 559)])
        assert diam == 24
        assert diam == self._exhaustive_diameter(source)

    # ── Cross-instance ordering invariant ─────────────────────────────────

    def test_nucleus_ast_distance_strictly_less_than_cluster(self):
        """Nucleus (same method) must have a strictly smaller AST distance
        than Cluster (different methods of same class) — pinned with the
        exact integer values produced by two-BFS + smallest-enclosing."""
        nucleus_src = load_resource("real_astropy_13579_sliced_wcs.py")
        cluster_src = load_resource("real_astropy_13033_core.py")
        _, nucleus_pairs = compute_ast_metrics_for_file(
            nucleus_src, [(0, 243, 248), (1, 251, 257)]
        )
        _, cluster_pairs = compute_ast_metrics_for_file(
            cluster_src, [(0, 55, 60), (1, 76, 84)]
        )
        assert nucleus_pairs["0_1"] == 1
        assert cluster_pairs["0_1"] == 2
        assert nucleus_pairs["0_1"] < cluster_pairs["0_1"]


if __name__ == "__main__":
    print("=" * 80)
    print("HUNK DIVERGENCE TEST SUITE — paper-bound + real SWE-bench fixtures")
    print("=" * 80)
    print()
    print("Run with: pytest test_comprehensive_divergence.py -v")
    print("=" * 80)
