#!/usr/bin/env python3
"""Test suite for classify_instances.py.

Exercises:
    - classify_issue(): label normalisation and Bug > Feature > Unlabeled priority
    - main(): end-to-end classification + JSON output, by pointing the script
      at synthetic swe_bench.jsonl / labels JSON / multi-hunk JSON in tmp_path.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))

import classify_instances
from classify_instances import classify_issue, BUG_LABELS, FEATURE_LABELS


# ─── Pure-function tests: classify_issue ────────────────────────────────────


class TestClassifyIssueBug:
    """Issues carrying any Bug label should resolve to 'Bug'."""

    def test_canonical_bug_label(self):
        assert classify_issue(["bug"]) == "Bug"

    def test_type_bug_label_with_space(self):
        assert classify_issue(["type: bug"]) == "Bug"

    def test_type_bug_label_no_space(self):
        assert classify_issue(["type:bug"]) == "Bug"

    def test_emoji_bug_label_normalised(self):
        assert classify_issue(["bug :beetle:"]) == "Bug"

    def test_status_confirmed_bug(self):
        assert classify_issue(["status: confirmed bug"]) == "Bug"

    def test_crash_label(self):
        assert classify_issue(["crash 💥"]) == "Bug"

    def test_wrong_result(self):
        assert classify_issue(["wrong result"]) == "Bug"

    def test_false_positive(self):
        assert classify_issue(["false positive 🦟"]) == "Bug"

    def test_false_negative(self):
        assert classify_issue(["false negative 🦋"]) == "Bug"

    def test_regression_routes_to_bug(self):
        """Regression labels are folded into Bug per BUG_LABELS."""
        assert classify_issue(["regression"]) == "Bug"

    def test_type_regression_routes_to_bug(self):
        assert classify_issue(["type: regression"]) == "Bug"

    def test_case_insensitive_match(self):
        assert classify_issue(["BUG"]) == "Bug"
        assert classify_issue(["Type: Bug"]) == "Bug"

    def test_strips_whitespace(self):
        assert classify_issue(["  bug  "]) == "Bug"


class TestClassifyIssueFeature:
    """Feature/enhancement labels resolve to 'Feature/Enhancement'."""

    def test_feature_request(self):
        assert classify_issue(["feature request"]) == "Feature/Enhancement"

    def test_new_feature(self):
        assert classify_issue(["new feature"]) == "Feature/Enhancement"

    def test_enhancement(self):
        assert classify_issue(["enhancement"]) == "Feature/Enhancement"

    def test_enhancement_emoji(self):
        assert classify_issue(["enhancement ✨"]) == "Feature/Enhancement"

    def test_type_enhancement(self):
        assert classify_issue(["type: enhancement"]) == "Feature/Enhancement"

    def test_proposal_emoji(self):
        assert classify_issue(["proposal 📨"]) == "Feature/Enhancement"

    def test_type_proposal_with_space(self):
        assert classify_issue(["type: proposal"]) == "Feature/Enhancement"

    def test_type_proposal_no_space(self):
        assert classify_issue(["type:proposal"]) == "Feature/Enhancement"

    def test_blueprints(self):
        assert classify_issue(["blueprints"]) == "Feature/Enhancement"


class TestClassifyIssueUnlabeled:
    """Anything that doesn't match Bug or Feature falls through."""

    def test_empty_list(self):
        assert classify_issue([]) == "Unlabeled"

    def test_unrecognised_label(self):
        assert classify_issue(["needs-triage"]) == "Unlabeled"

    def test_multiple_unrecognised(self):
        assert classify_issue(["good first issue", "help wanted"]) == "Unlabeled"


class TestClassifyIssuePriority:
    """Bug > Feature/Enhancement > Unlabeled — verify the precedence."""

    def test_bug_wins_over_feature(self):
        assert classify_issue(["enhancement", "bug"]) == "Bug"

    def test_bug_wins_over_feature_reversed_order(self):
        assert classify_issue(["bug", "enhancement"]) == "Bug"

    def test_feature_wins_over_unlabeled(self):
        assert classify_issue(["needs-triage", "enhancement"]) == "Feature/Enhancement"

    def test_regression_treated_as_bug_not_feature(self):
        """A regression+enhancement issue still classifies as Bug."""
        assert classify_issue(["regression", "enhancement"]) == "Bug"


class TestLabelSetIntegrity:
    """Sanity checks on the configured label sets."""

    def test_bug_and_feature_sets_are_disjoint(self):
        assert BUG_LABELS.isdisjoint(FEATURE_LABELS), (
            f"Overlap: {BUG_LABELS & FEATURE_LABELS}"
        )

    def test_all_bug_labels_lowercase(self):
        for label in BUG_LABELS:
            assert label == label.lower()

    def test_all_feature_labels_lowercase(self):
        for label in FEATURE_LABELS:
            assert label == label.lower()


# ─── End-to-end tests for main() ────────────────────────────────────────────


def _write_inputs(work_dir: Path,
                  swe_records: list[dict],
                  issue_labels: dict[str, list[str]],
                  multihunk: dict[str, dict]) -> None:
    """Materialise the three input files main() reads."""
    jsonl = work_dir / "swe_bench.jsonl"
    with jsonl.open("w") as f:
        for rec in swe_records:
            f.write(json.dumps(rec) + "\n")
    (work_dir / "swe-bench_issue_labels.json").write_text(json.dumps(issue_labels))
    (work_dir / "multihunk_swe_bench_verified.json").write_text(json.dumps(multihunk))


@pytest.fixture
def synthetic_repo(tmp_path, monkeypatch):
    """Redirect classify_instances to read from tmp_path inputs.

    Returns the work directory; tests populate the three input files inside it.
    """
    fake_script = tmp_path / "classify_instances.py"
    fake_script.write_text("# placeholder\n")
    monkeypatch.setattr(classify_instances, "__file__", str(fake_script))
    return tmp_path


class TestMainEndToEnd:

    def test_writes_classification_for_every_instance(self, synthetic_repo):
        swe = [
            {"instance_id": "proj__bug-1"},
            {"instance_id": "proj__feature-1"},
            {"instance_id": "proj__unlabeled-1"},
            {"instance_id": "proj__multi-1"},
        ]
        labels = {
            "proj__bug-1": ["bug"],
            "proj__feature-1": ["enhancement"],
            "proj__unlabeled-1": [],
            "proj__multi-1": ["bug"],
        }
        multi = {
            "proj__multi-1": {
                "buggy_hunks": {
                    "0": {"file": "x.py"},
                    "1": {"file": "y.py"},
                    "2": {"file": "z.py"},
                }
            },
        }
        _write_inputs(synthetic_repo, swe, labels, multi)

        classify_instances.main()

        out = json.loads(
            (synthetic_repo / "swe_bench_verified_issue_classification.json").read_text()
        )

        assert set(out.keys()) == {
            "proj__bug-1", "proj__feature-1", "proj__unlabeled-1", "proj__multi-1"
        }
        assert out["proj__bug-1"] == {
            "hunk_type": "single-hunk", "issue_type": "Bug", "num_hunks": 1
        }
        assert out["proj__feature-1"] == {
            "hunk_type": "single-hunk",
            "issue_type": "Feature/Enhancement",
            "num_hunks": 1,
        }
        assert out["proj__unlabeled-1"] == {
            "hunk_type": "single-hunk", "issue_type": "Unlabeled", "num_hunks": 1
        }
        assert out["proj__multi-1"] == {
            "hunk_type": "multi-hunk", "issue_type": "Bug", "num_hunks": 3
        }

    def test_single_hunk_default_num_hunks_is_one(self, synthetic_repo):
        _write_inputs(
            synthetic_repo,
            swe_records=[{"instance_id": "x"}],
            issue_labels={},
            multihunk={},
        )
        classify_instances.main()
        out = json.loads(
            (synthetic_repo / "swe_bench_verified_issue_classification.json").read_text()
        )
        assert out["x"]["num_hunks"] == 1
        assert out["x"]["hunk_type"] == "single-hunk"

    def test_empty_buggy_hunks_dict_raises(self, synthetic_repo):
        """An entry in the multihunk file with zero hunks violates the file's
        invariant (presence ⇒ multi-hunk). main() must reject it loudly."""
        _write_inputs(
            synthetic_repo,
            swe_records=[{"instance_id": "x"}],
            issue_labels={"x": ["bug"]},
            multihunk={"x": {"buggy_hunks": {}}},
        )
        with pytest.raises(ValueError, match="empty or missing buggy_hunks"):
            classify_instances.main()

    def test_missing_buggy_hunks_key_raises(self, synthetic_repo):
        """A multihunk entry without a buggy_hunks key is equally malformed."""
        _write_inputs(
            synthetic_repo,
            swe_records=[{"instance_id": "x"}],
            issue_labels={"x": ["bug"]},
            multihunk={"x": {}},
        )
        with pytest.raises(ValueError, match="empty or missing buggy_hunks"):
            classify_instances.main()

    def test_multihunk_num_hunks_matches_buggy_hunks_size(self, synthetic_repo):
        multi = {
            "x": {"buggy_hunks": {str(i): {} for i in range(7)}},
        }
        _write_inputs(
            synthetic_repo,
            swe_records=[{"instance_id": "x"}],
            issue_labels={"x": ["bug"]},
            multihunk=multi,
        )
        classify_instances.main()
        out = json.loads(
            (synthetic_repo / "swe_bench_verified_issue_classification.json").read_text()
        )
        assert out["x"]["num_hunks"] == 7
        assert out["x"]["hunk_type"] == "multi-hunk"

    def test_missing_label_entry_is_unlabeled(self, synthetic_repo):
        """An instance absent from the labels JSON gets 'Unlabeled'."""
        _write_inputs(
            synthetic_repo,
            swe_records=[{"instance_id": "ghost"}],
            issue_labels={},  # no entry at all
            multihunk={},
        )
        classify_instances.main()
        out = json.loads(
            (synthetic_repo / "swe_bench_verified_issue_classification.json").read_text()
        )
        assert out["ghost"]["issue_type"] == "Unlabeled"

    def test_blank_lines_in_jsonl_are_skipped(self, synthetic_repo):
        """The reader strips empty lines; we replicate that contract."""
        jsonl = synthetic_repo / "swe_bench.jsonl"
        jsonl.write_text(
            json.dumps({"instance_id": "a"}) + "\n"
            + "\n"
            + json.dumps({"instance_id": "b"}) + "\n"
        )
        (synthetic_repo / "swe-bench_issue_labels.json").write_text("{}")
        (synthetic_repo / "multihunk_swe_bench_verified.json").write_text("{}")

        classify_instances.main()
        out = json.loads(
            (synthetic_repo / "swe_bench_verified_issue_classification.json").read_text()
        )
        assert set(out.keys()) == {"a", "b"}

    def test_cross_tabulation_counts(self, synthetic_repo, capsys):
        """Verify the printed cross-tab matches the data we provided."""
        swe = [
            {"instance_id": "sb"},   # single-hunk Bug
            {"instance_id": "sf"},   # single-hunk Feature
            {"instance_id": "su"},   # single-hunk Unlabeled
            {"instance_id": "mb"},   # multi-hunk Bug
            {"instance_id": "mf"},   # multi-hunk Feature
        ]
        labels = {
            "sb": ["bug"], "sf": ["enhancement"], "su": [],
            "mb": ["bug"], "mf": ["new feature"],
        }
        multi = {
            "mb": {"buggy_hunks": {"0": {}, "1": {}}},
            "mf": {"buggy_hunks": {"0": {}, "1": {}}},
        }
        _write_inputs(synthetic_repo, swe, labels, multi)

        classify_instances.main()
        printed = capsys.readouterr().out

        assert "Bug" in printed
        assert "Feature/Enhancement" in printed
        assert "single-hunk" in printed
        assert "multi-hunk" in printed
        # 3 single-hunk total, 2 multi-hunk total — verify totals appear
        assert "  3 " in printed or " 3 " in printed
        assert "  2 " in printed or " 2 " in printed


# ─── Tests pinned to actual instances in swe-bench_issue_labels.json ───────


# These instance_ids and their label lists are taken verbatim from the real
# swe-bench_issue_labels.json. They lock in the classifier's behavior for
# concrete cases the SWE-bench Verified harness sees in production.

REAL_BUG_INSTANCES = [
    ("astropy__astropy-11693", ["wcs", "Bug", "wcs.wcsapi"]),
    ("astropy__astropy-12318", ["Bug", "modeling"]),
    ("astropy__astropy-12825", ["table", "Bug"]),
    ("astropy__astropy-12842", ["io.ascii", "Bug", "unified-io", "timeseries"]),
    ("pylint-dev__pylint-4516", ["Bug :beetle:", "Bug :beetle:"]),
    ("pylint-dev__pylint-5859", ["False Negative 🦋"]),
    ("pylint-dev__pylint-7097", ["Crash 💥", "Needs PR"]),
    ("pylint-dev__pylint-7228",
     ["Crash 💥", "Needs investigation 🔬", "Needs PR"]),
]

REAL_FEATURE_INSTANCES = [
    ("astropy__astropy-12544", ["Feature Request", "table"]),
    ("astropy__astropy-12891", ["Feature Request", "units"]),
    ("astropy__astropy-12962",
     ["Feature Request", "io.fits", "nddata"]),
    ("pylint-dev__pylint-4330", ["Enhancement ✨"]),
    ("pylint-dev__pylint-4339",
     ["Enhancement ✨", "Help wanted 🙏", "Good first issue"]),
    ("pytest-dev__pytest-5413", ["type: proposal"]),
    ("pytest-dev__pytest-10442", ["type: proposal", "plugin: tmpdir"]),
]

REAL_UNLABELED_INSTANCES = [
    ("astropy__astropy-12057", ["nddata"]),
    ("astropy__astropy-13132", []),
    ("astropy__astropy-13572", ["coordinates"]),
    ("astropy__astropy-13803", []),
    ("astropy__astropy-14096", ["coordinates", "question"]),
    ("astropy__astropy-6938", []),
]

# Instances where Bug- and Feature-flavored labels co-occur on the same issue.
# These are the hardest real cases — the priority rule (Bug > Feature) is what
# determines the final classification.
REAL_BUG_FEATURE_CONFLICTS = [
    ("matplotlib__matplotlib-24431",
     ["New feature", "status: confirmed bug"]),
    ("matplotlib__matplotlib-24912",
     ["status: confirmed bug", "topic: contour", "New feature"]),
    ("pylint-dev__pylint-4604",
     ["Enhancement ✨", "False Positive 🦟"]),
    ("pylint-dev__pylint-8929",
     ["Bug :beetle:", "Enhancement ✨", "Breaking changes for 3.0 🦤"]),
    ("pytest-dev__pytest-10988",
     ["type: enhancement", "type: bug", "good first issue"]),
    ("scikit-learn__scikit-learn-14114",
     ["Enhancement", "Question", "Bug"]),
    ("sphinx-doc__sphinx-10614",
     ["type:enhancement", "extensions:graphviz", "extensions:graphviz",
      "type:bug", "extensions:graphviz"]),
]

# Instances tagged with any 'regression' variant — these are folded into Bug
# by BUG_LABELS, so the classifier should never call them Feature/Enhancement.
REAL_REGRESSION_INSTANCES = [
    ("pydata__xarray-6823", ["bug", "regression"]),
    ("pylint-dev__pylint-4175", ["Regression"]),
    ("pylint-dev__pylint-6357",
     ["Configuration", "Regression", "Crash 💥", "duplicate-code"]),
    ("pytest-dev__pytest-11125", ["type: regression"]),
    ("pytest-dev__pytest-7151", ["type: bug", "type: regression"]),
    ("scikit-learn__scikit-learn-12625",
     ["Bug", "Blocker", "Regression", "help wanted"]),
]


class TestRealInstancesBug:
    """Bug-classified instances pulled from the actual labels file."""

    @pytest.mark.parametrize("iid,tags", REAL_BUG_INSTANCES)
    def test_real_bug_instance_classifies_as_bug(self, iid, tags):
        assert classify_issue(tags) == "Bug", (
            f"{iid} with tags={tags} should classify as Bug"
        )


class TestRealInstancesFeature:
    """Feature/Enhancement instances pulled from the actual labels file."""

    @pytest.mark.parametrize("iid,tags", REAL_FEATURE_INSTANCES)
    def test_real_feature_instance_classifies_as_feature(self, iid, tags):
        assert classify_issue(tags) == "Feature/Enhancement", (
            f"{iid} with tags={tags} should classify as Feature/Enhancement"
        )


class TestRealInstancesUnlabeled:
    """Real instances with no Bug- or Feature-flavored labels."""

    @pytest.mark.parametrize("iid,tags", REAL_UNLABELED_INSTANCES)
    def test_real_unlabeled_instance_classifies_as_unlabeled(self, iid, tags):
        assert classify_issue(tags) == "Unlabeled", (
            f"{iid} with tags={tags} should classify as Unlabeled"
        )


class TestRealInstancesPriority:
    """Real instances carrying both Bug- and Feature-flavored labels.

    The Bug > Feature priority rule must classify every one of these as Bug.
    These are the cases most likely to surface a regression in `classify_issue`
    because they fail silently — a broken priority would still return *some*
    valid bucket, just the wrong one.
    """

    @pytest.mark.parametrize("iid,tags", REAL_BUG_FEATURE_CONFLICTS)
    def test_bug_wins_on_real_conflict(self, iid, tags):
        assert classify_issue(tags) == "Bug", (
            f"{iid} (Bug+Feature conflict) must resolve to Bug, not "
            f"{classify_issue(tags)}"
        )


class TestRealInstancesRegression:
    """Regression-tagged instances are routed through BUG_LABELS → Bug."""

    @pytest.mark.parametrize("iid,tags", REAL_REGRESSION_INSTANCES)
    def test_regression_classified_as_bug(self, iid, tags):
        assert classify_issue(tags) == "Bug", (
            f"{iid} (regression) should classify as Bug, got "
            f"{classify_issue(tags)}"
        )


class TestRealLabelsFileSanity:
    """Whole-file sanity checks against swe-bench_issue_labels.json."""

    @pytest.fixture
    def labels(self):
        path = Path(__file__).parent / "swe-bench_issue_labels.json"
        if not path.exists():
            pytest.skip("swe-bench_issue_labels.json missing")
        return json.loads(path.read_text())

    def test_every_instance_classifies_to_known_bucket(self, labels):
        """Every real instance must classify to one of the three buckets."""
        valid = {"Bug", "Feature/Enhancement", "Unlabeled"}
        for iid, tags in labels.items():
            assert classify_issue(tags) in valid, (
                f"{iid} produced unknown bucket"
            )

    def test_classification_is_deterministic_per_instance(self, labels):
        """classify_issue() must be a pure function — same input → same output."""
        sample = list(labels.items())[:200]
        for iid, tags in sample:
            assert classify_issue(tags) == classify_issue(tags), (
                f"{iid}: classify_issue is non-deterministic"
            )

    def test_at_least_one_instance_per_bucket(self, labels):
        """The real dataset is diverse enough to populate every bucket."""
        from collections import Counter
        counts = Counter(classify_issue(tags) for tags in labels.values())
        assert counts["Bug"] > 0
        assert counts["Feature/Enhancement"] > 0
        assert counts["Unlabeled"] > 0


# ─── Realistic data smoke test (skipped if real files absent) ───────────────


class TestAgainstRealData:
    """Optional integration smoke test against the actual JSON files in the
    repository. Skips when the environment isn't fully set up."""

    @pytest.fixture
    def real_dir(self):
        d = Path(__file__).parent
        required = [
            "swe_bench.jsonl",
            "swe-bench_issue_labels.json",
            "multihunk_swe_bench_verified.json",
        ]
        for fname in required:
            if not (d / fname).exists():
                pytest.skip(f"real data file missing: {fname}")
        return d

    def test_existing_classification_output_consistent_with_classifier(self, real_dir):
        """Every entry in swe_bench_verified_issue_classification.json must be
        re-derivable from classify_issue() and the multi-hunk JSON."""
        out_file = real_dir / "swe_bench_verified_issue_classification.json"
        if not out_file.exists():
            pytest.skip("classification output not yet generated")

        existing = json.loads(out_file.read_text())
        labels = json.loads((real_dir / "swe-bench_issue_labels.json").read_text())
        multihunk = json.loads(
            (real_dir / "multihunk_swe_bench_verified.json").read_text()
        )

        # Spot-check a sample of 50 instances to keep this test fast
        sample = list(existing.items())[:50]
        for iid, expected in sample:
            tags = labels.get(iid, [])
            assert classify_issue(tags) == expected["issue_type"], (
                f"{iid}: tags={tags} → {classify_issue(tags)} "
                f"!= {expected['issue_type']}"
            )
            expected_hunk = "multi-hunk" if iid in multihunk else "single-hunk"
            assert expected["hunk_type"] == expected_hunk


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
