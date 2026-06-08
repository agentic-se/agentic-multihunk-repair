"""
Tests for PythonSearchManager — exercises all nine MCP-facing search APIs
against a small sample-repo fixture in resources/sample_repo/.

Each section maps to one of the nine maple_* tools exposed by
mcp_server/python_analysis_server*.py:

    1. search_class            (maple_find_class)
    2. search_class_in_file    (maple_find_class_in_file)
    3. search_method           (maple_find_method)
    4. search_method_in_class  (maple_find_method_in_class)
    5. search_method_in_file   (maple_find_method_in_file)
    6. search_code             (maple_find_code)
    7. search_code_in_file     (maple_find_code_in_file)
    8. extract_class_skeleton  (maple_extract_class_skeleton)
    9. get_repo_structure      (maple_repo_structure)

Run from the progctx-mcp-swe-bench/ directory:

    python -m pytest test_python_search_manager.py -v
"""

import os
import pytest

from context.search.python_search_manager import PythonSearchManager


SAMPLE_REPO = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "resources",
    "sample_repo",
)


@pytest.fixture(scope="module")
def manager() -> PythonSearchManager:
    """Build one PythonSearchManager for the whole module — indexing is O(N)."""
    return PythonSearchManager(SAMPLE_REPO)


# ---------------------------------------------------------------------------
# 1. search_class (maple_find_class)
# ---------------------------------------------------------------------------

def test_search_class_finds_base_class(manager):
    tool_output, _, success = manager.search_class("Mammal")
    assert success is True
    assert "Mammal" in tool_output


def test_search_class_finds_subclass(manager):
    _, _, success = manager.search_class("Dog")
    assert success is True


def test_search_class_returns_false_when_missing(manager):
    _, _, success = manager.search_class("DoesNotExist")
    assert success is False


# ---------------------------------------------------------------------------
# 2. search_class_in_file (maple_find_class_in_file)
# ---------------------------------------------------------------------------

def test_search_class_in_file_finds(manager):
    _, _, success = manager.search_class_in_file("Dog", "mammals.py")
    assert success is True


def test_search_class_in_file_wrong_file(manager):
    _, _, success = manager.search_class_in_file("Dog", "birds.py")
    assert success is False


def test_search_class_in_file_missing_file(manager):
    _, _, success = manager.search_class_in_file("Dog", "no_such_file.py")
    assert success is False


# ---------------------------------------------------------------------------
# 3. search_method (maple_find_method)
# ---------------------------------------------------------------------------

def test_search_method_finds_top_level_function(manager):
    _, _, success = manager.search_method("normalize_name")
    assert success is True


def test_search_method_finds_when_overridden_across_classes(manager):
    # `speak` is defined in Mammal, Dog, and Bird
    tool_output, _, success = manager.search_method("speak")
    assert success is True
    # Summary mentions the count
    assert "Found" in tool_output


def test_search_method_returns_false_when_missing(manager):
    _, _, success = manager.search_method("does_not_exist")
    assert success is False


# ---------------------------------------------------------------------------
# 4. search_method_in_class (maple_find_method_in_class)
# ---------------------------------------------------------------------------

def test_search_method_in_class_finds(manager):
    tool_output, _, success = manager.search_method_in_class("fetch", "Dog")
    assert success is True
    assert "fetch" in tool_output


def test_search_method_in_class_wrong_class(manager):
    # `fly` is in Bird, not Mammal
    _, _, success = manager.search_method_in_class("fly", "Mammal")
    assert success is False


def test_search_method_in_class_missing_class(manager):
    _, _, success = manager.search_method_in_class("speak", "NoSuchClass")
    assert success is False


# ---------------------------------------------------------------------------
# 5. search_method_in_file (maple_find_method_in_file)
# ---------------------------------------------------------------------------

def test_search_method_in_file_finds(manager):
    _, _, success = manager.search_method_in_file("fly", "birds.py")
    assert success is True


def test_search_method_in_file_wrong_file(manager):
    _, _, success = manager.search_method_in_file("fly", "mammals.py")
    assert success is False


def test_search_method_in_file_missing_file(manager):
    _, _, success = manager.search_method_in_file("speak", "no_such_file.py")
    assert success is False


# ---------------------------------------------------------------------------
# 6. search_code (maple_find_code)
# ---------------------------------------------------------------------------

def test_search_code_finds_distinctive_string(manager):
    _, _, success = manager.search_code("warm-blooded")
    assert success is True


def test_search_code_returns_false_when_missing(manager):
    _, _, success = manager.search_code("zzz_nonexistent_pattern_xyz")
    assert success is False


# ---------------------------------------------------------------------------
# 7. search_code_in_file (maple_find_code_in_file)
# ---------------------------------------------------------------------------

def test_search_code_in_file_finds(manager):
    _, _, success = manager.search_code_in_file("wingspan", "birds.py")
    assert success is True


def test_search_code_in_file_wrong_file(manager):
    # `wingspan` lives in birds.py, not mammals.py
    _, _, success = manager.search_code_in_file("wingspan", "mammals.py")
    assert success is False


# ---------------------------------------------------------------------------
# 8. extract_class_skeleton (maple_extract_class_skeleton)
# ---------------------------------------------------------------------------

def test_extract_class_skeleton_emits_classes_and_signatures(manager):
    tool_output, _, success = manager.extract_class_skeleton("mammals.py")
    assert success is True
    # Class headers
    assert "class Mammal" in tool_output
    assert "class Dog" in tool_output
    # Method def lines
    assert "def speak" in tool_output
    assert "def fetch" in tool_output
    assert "def list_traits" in tool_output


def test_extract_class_skeleton_elides_method_bodies(manager):
    tool_output, _, success = manager.extract_class_skeleton("mammals.py")
    assert success is True
    # Body string literals should NOT appear — bodies are replaced by `...`
    assert "Woof!" not in tool_output
    assert "warm-blooded" not in tool_output
    assert "fetches the" not in tool_output


def test_extract_class_skeleton_preserves_top_level_imports(manager):
    tool_output, _, success = manager.extract_class_skeleton("mammals.py")
    assert success is True
    assert "from typing import List" in tool_output


def test_extract_class_skeleton_missing_file(manager):
    _, _, success = manager.extract_class_skeleton("no_such_file.py")
    assert success is False


# ---------------------------------------------------------------------------
# 9. get_repo_structure (maple_repo_structure)
# ---------------------------------------------------------------------------

def test_get_repo_structure_default_shows_full_tree(manager):
    tool_output, _, success = manager.get_repo_structure()
    assert success is True
    # Directory and file names should be present
    assert "animals" in tool_output
    assert "mammals.py" in tool_output
    assert "birds.py" in tool_output
    assert "utils.py" in tool_output


def test_get_repo_structure_summary_counts_files(manager):
    _, summary, success = manager.get_repo_structure()
    assert success is True
    # parsed_files has 5 entries (3 .py + 2 __init__.py)
    assert "Python files" in summary


def test_get_repo_structure_with_low_max_depth(manager):
    # max_depth=0 means don't recurse past the root level
    tool_output, _, success = manager.get_repo_structure(max_depth=0)
    assert success is True
    # animals/ appears as a directory entry but its contents do not
    assert "animals" in tool_output
    assert "mammals.py" not in tool_output
