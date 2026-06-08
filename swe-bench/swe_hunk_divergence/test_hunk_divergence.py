#!/usr/bin/env python3
"""Test suite for hunk_divergence.py."""

import ast
import math
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))

from hunk_divergence import (
    _ast_node_distance,
    _build_parent_map,
    _buggy_subtree_root,
    _lca,
    _node_depth,
    _read_source_file,
    _subtree_diameter,
    compute_ast_metrics_for_file,
    compute_metrics_for_bug,
    parse_patch_hunks,
)


# ── Sample sources ──────────────────────────────────────────────────────────

SIMPLE_SRC = '''\
def foo(x):
    y = x + 1
    return y

def bar(x):
    z = x * 2
    return z
'''

CLASS_SRC = '''\
class A:
    def m1(self):
        a = 1
        return a

    def m2(self):
        b = 2
        return b
'''

NESTED_SRC = '''\
def outer():
    def inner():
        x = 1
        y = 2
        return x + y
    return inner()
'''

ASYNC_SRC = '''\
async def f():
    async for x in g():
        async with h() as y:
            await k(x, y)
'''

DECORATED_SRC = '''\
@dec1
@dec2(arg)
def decorated():
    return 1
'''

MULTILINE_CALL_SRC = '''\
result = some_function(
    arg_one,
    arg_two,
    arg_three,
)
'''

TRY_SRC = '''\
def f():
    try:
        risky()
    except ValueError:
        handle1()
    except KeyError:
        handle2()
    finally:
        cleanup()
'''

COMPREHENSION_SRC = '''\
def build(items):
    out = [x * 2 for x in items if x > 0]
    return out
'''

LAMBDA_SRC = '''\
add = lambda a, b: a + b
'''

DEEP_NESTED_SRC = '''\
def a():
    def b():
        def c():
            def d():
                def e():
                    return 1
                return e()
            return d()
        return c()
    return b()
'''


# ── 1. parent map / depth / LCA / distance ──────────────────────────────────

class TestParentMap:
    def test_module_has_no_parent(self):
        tree = ast.parse(SIMPLE_SRC)
        parents = _build_parent_map(tree)
        assert id(tree) not in parents

    def test_top_level_def_parent_is_module(self):
        tree = ast.parse(SIMPLE_SRC)
        parents = _build_parent_map(tree)
        foo = tree.body[0]
        assert parents[id(foo)] is tree

    def test_nested_node_parent_chain(self):
        tree = ast.parse(NESTED_SRC)
        parents = _build_parent_map(tree)
        outer = tree.body[0]
        inner = outer.body[0]
        assert parents[id(inner)] is outer
        assert parents[id(outer)] is tree

    def test_every_walked_node_except_module_has_parent(self):
        tree = ast.parse(CLASS_SRC)
        parents = _build_parent_map(tree)
        for node in ast.walk(tree):
            if node is tree:
                continue
            assert id(node) in parents, f"missing parent for {type(node).__name__}"

    def test_decorator_nodes_are_children_of_function(self):
        tree = ast.parse(DECORATED_SRC)
        parents = _build_parent_map(tree)
        fn = tree.body[0]
        for dec in fn.decorator_list:
            assert parents[id(dec)] is fn


class TestNodeDepth:
    def test_module_depth_zero(self):
        tree = ast.parse(SIMPLE_SRC)
        parents = _build_parent_map(tree)
        assert _node_depth(tree, parents) == 0

    def test_top_level_depth_one(self):
        tree = ast.parse(SIMPLE_SRC)
        parents = _build_parent_map(tree)
        assert _node_depth(tree.body[0], parents) == 1

    def test_nested_depth(self):
        tree = ast.parse(NESTED_SRC)
        parents = _build_parent_map(tree)
        outer = tree.body[0]
        inner = outer.body[0]
        assert _node_depth(inner, parents) == 2

    def test_deep_nesting_depth_strictly_increasing(self):
        tree = ast.parse(DEEP_NESTED_SRC)
        parents = _build_parent_map(tree)
        node = tree.body[0]
        depths = [_node_depth(node, parents)]
        while True:
            child = next(
                (c for c in node.body if isinstance(c, ast.FunctionDef)),
                None,
            )
            if child is None:
                break
            depths.append(_node_depth(child, parents))
            node = child
        assert depths == sorted(depths)
        assert depths == list(range(1, len(depths) + 1))


class TestLCA:
    def test_lca_self(self):
        tree = ast.parse(SIMPLE_SRC)
        parents = _build_parent_map(tree)
        foo = tree.body[0]
        assert _lca(foo, foo, parents) is foo

    def test_lca_siblings_is_module(self):
        tree = ast.parse(SIMPLE_SRC)
        parents = _build_parent_map(tree)
        foo, bar = tree.body[0], tree.body[1]
        assert _lca(foo, bar, parents) is tree

    def test_lca_ancestor_descendant(self):
        tree = ast.parse(NESTED_SRC)
        parents = _build_parent_map(tree)
        outer = tree.body[0]
        inner = outer.body[0]
        assert _lca(outer, inner, parents) is outer

    def test_lca_deep_siblings(self):
        tree = ast.parse(CLASS_SRC)
        parents = _build_parent_map(tree)
        cls = tree.body[0]
        m1, m2 = cls.body[0], cls.body[1]
        assert _lca(m1, m2, parents) is cls

    def test_lca_module_against_descendant(self):
        tree = ast.parse(SIMPLE_SRC)
        parents = _build_parent_map(tree)
        assert _lca(tree, tree.body[0], parents) is tree

    def test_lca_disjoint_trees_returns_none(self):
        t1 = ast.parse("x = 1")
        t2 = ast.parse("y = 2")
        # Parent map covers t1 only — t2's nodes have no parents recorded
        parents = _build_parent_map(t1)
        assert _lca(t1.body[0], t2.body[0], parents) is None


class TestASTNodeDistance:
    def test_distance_self_zero(self):
        tree = ast.parse(SIMPLE_SRC)
        parents = _build_parent_map(tree)
        foo = tree.body[0]
        assert _ast_node_distance(foo, foo, parents) == 0

    def test_distance_siblings(self):
        tree = ast.parse(SIMPLE_SRC)
        parents = _build_parent_map(tree)
        foo, bar = tree.body[0], tree.body[1]
        # both depth 1, LCA is module (depth 0) → 1 + 1 - 0 = 2
        assert _ast_node_distance(foo, bar, parents) == 2

    def test_distance_ancestor_descendant(self):
        tree = ast.parse(NESTED_SRC)
        parents = _build_parent_map(tree)
        outer = tree.body[0]
        inner = outer.body[0]
        # outer depth 1, inner depth 2, LCA outer depth 1 → 1 + 2 - 2 = 1
        assert _ast_node_distance(outer, inner, parents) == 1

    def test_distance_is_symmetric(self):
        tree = ast.parse(CLASS_SRC)
        parents = _build_parent_map(tree)
        cls = tree.body[0]
        m1, m2 = cls.body[0], cls.body[1]
        d_ab = _ast_node_distance(m1, m2, parents)
        d_ba = _ast_node_distance(m2, m1, parents)
        assert d_ab == d_ba
        assert d_ab > 0

    def test_distance_satisfies_triangle_inequality(self):
        tree = ast.parse(NESTED_SRC)
        parents = _build_parent_map(tree)
        outer = tree.body[0]
        inner = outer.body[0]
        ret_inner = inner.body[-1]
        d_oi = _ast_node_distance(outer, inner, parents)
        d_ir = _ast_node_distance(inner, ret_inner, parents)
        d_or = _ast_node_distance(outer, ret_inner, parents)
        assert d_or <= d_oi + d_ir


# ── 2. _buggy_subtree_root (THE BUG-FIX) ────────────────────────────────────

class TestBuggySubtreeRoot:
    """Verify the smallest-enclosing-node logic matches the JavaParser
    implementation in MethodLineExtractor.java (BIRCH/Defects4J pipeline).

    Algorithm pinned by these tests:
      - candidate = any AST node with `lineno <= start AND end_lineno >= end`
      - winner    = candidate with smallest (end_lineno - lineno) span
      - tie-break = first node visited in DFS pre-order
      - fallback  = whole Module if no candidate exists
    """

    def test_single_line_returns_smallest_enclosing(self):
        # Range covering exactly the body of foo (line 2)
        tree = ast.parse(SIMPLE_SRC)
        parents = _build_parent_map(tree)
        root = _buggy_subtree_root(tree, 2, 2, parents)
        # Line 2 holds `y = x + 1`. Multiple nodes have range [2, 2]
        # (Assign, Name y, BinOp, Name x, Constant 1) — all span 0.
        # DFS pre-order visits the parent Assign first, so it wins ties.
        assert isinstance(root, ast.Assign)

    def test_range_covering_two_siblings_falls_back_to_module(self):
        # Lines 1..6 cover both `def foo` and `def bar`. Neither
        # FunctionDef encloses [1, 6] on its own → no enclosing candidate
        # → fall back to Module.
        tree = ast.parse(SIMPLE_SRC)
        parents = _build_parent_map(tree)
        root = _buggy_subtree_root(tree, 1, 6, parents)
        assert isinstance(root, ast.Module)

    def test_range_inside_one_function_returns_function(self):
        # Lines 2..3 = body of foo. Smallest node fully enclosing [2, 3]
        # is FunctionDef foo (range [1, 3], span 2). Its children Assign
        # at [2, 2] and Return at [3, 3] each span 0 but neither encloses
        # the full [2, 3] range.
        tree = ast.parse(SIMPLE_SRC)
        parents = _build_parent_map(tree)
        root = _buggy_subtree_root(tree, 2, 3, parents)
        assert isinstance(root, ast.FunctionDef)
        assert root.name == "foo"

    def test_range_covering_two_methods_returns_class(self):
        # Lines 2..7 span m1 body + m2 def. Only ClassDef A encloses.
        tree = ast.parse(CLASS_SRC)
        parents = _build_parent_map(tree)
        root = _buggy_subtree_root(tree, 2, 7, parents)
        assert isinstance(root, ast.ClassDef)

    def test_no_enclosing_node_returns_tree(self):
        # A line range past EOF — no node encloses
        tree = ast.parse(SIMPLE_SRC)
        parents = _build_parent_map(tree)
        root = _buggy_subtree_root(tree, 999, 1000, parents)
        assert root is tree

    def test_nested_function_range_returns_inner(self):
        # Lines 3..5 = body of inner(). FunctionDef inner [2, 5] (span 3)
        # is tighter than FunctionDef outer [1, 6] (span 5).
        tree = ast.parse(NESTED_SRC)
        parents = _build_parent_map(tree)
        root = _buggy_subtree_root(tree, 3, 5, parents)
        assert isinstance(root, ast.FunctionDef)
        assert root.name == "inner"

    def test_uses_smallest_enclosing_node(self):
        """Pin the smallest-enclosing-node rule (matches Java).

        Range [3,3] hits `return y` (line 3). Both FunctionDef foo
        ([1,3], span 2) and Return ([3,3], span 0) enclose [3,3];
        Return wins by smaller span.
        """
        tree = ast.parse(SIMPLE_SRC)
        parents = _build_parent_map(tree)
        root = _buggy_subtree_root(tree, 3, 3, parents)
        assert isinstance(root, ast.Return)

    def test_blank_line_between_functions_falls_back_to_module(self):
        # Line 4 is blank between foo [1,3] and bar [5,7] — neither
        # function encloses [4, 4] → fall back to Module.
        tree = ast.parse(SIMPLE_SRC)
        parents = _build_parent_map(tree)
        root = _buggy_subtree_root(tree, 4, 4, parents)
        assert root is tree

    def test_class_definition_line_returns_class(self):
        # ClassDef A [1, 8] is the only enclosing node for [1, 1] in
        # CLASS_SRC (its sub-functions start at line 2).
        tree = ast.parse(CLASS_SRC)
        parents = _build_parent_map(tree)
        root = _buggy_subtree_root(tree, 1, 1, parents)
        assert isinstance(root, ast.ClassDef)
        assert root.name == "A"

    def test_async_function_def_line(self):
        # AsyncFunctionDef [1, 4] is the only node enclosing [1, 1] in
        # ASYNC_SRC (AsyncFor starts at line 2).
        tree = ast.parse(ASYNC_SRC)
        parents = _build_parent_map(tree)
        root = _buggy_subtree_root(tree, 1, 1, parents)
        assert isinstance(root, ast.AsyncFunctionDef)

    def test_async_for_line_returns_smallest_span_zero_node(self):
        # Range [2, 2] in ASYNC_SRC. Multiple line-2-only nodes enclose
        # (Name x target, Call iter, Name g) — all span 0. DFS pre-order
        # under AsyncFor visits target Name x first, so it wins.
        tree = ast.parse(ASYNC_SRC)
        parents = _build_parent_map(tree)
        root = _buggy_subtree_root(tree, 2, 2, parents)
        assert isinstance(root, ast.Name)
        assert root.id == "x"

    def test_async_with_line_returns_smallest_span_zero_node(self):
        # Range [3, 3] in ASYNC_SRC. AsyncWith [3, 4] (span 1) encloses,
        # but its child Call h() at [3, 3] (span 0) is tighter.
        tree = ast.parse(ASYNC_SRC)
        parents = _build_parent_map(tree)
        root = _buggy_subtree_root(tree, 3, 3, parents)
        assert isinstance(root, ast.Call)

    def test_decorator_line_only(self):
        # Line 1 = `@dec1`. The decorator Name `dec1` ([1, 1], span 0)
        # is the only enclosing node — Python's FunctionDef.lineno is the
        # `def` line (3), not the decorator line, so FunctionDef does not
        # enclose [1, 1].
        tree = ast.parse(DECORATED_SRC)
        parents = _build_parent_map(tree)
        root = _buggy_subtree_root(tree, 1, 1, parents)
        assert isinstance(root, ast.Name)
        assert root.id == "dec1"

    def test_range_covering_decorators_and_def_falls_back_to_module(self):
        # Lines 1..3: @dec1, @dec2(arg), def decorated():
        # NOTE: Python's FunctionDef.lineno == the `def` line (3), not
        # the first decorator. So FunctionDef [3, 4] does NOT enclose
        # [1, 3]. Decorator nodes at lines 1 and 2 don't enclose the
        # full [1, 3] either. Result: fall back to Module.
        # (This differs from JavaParser, where MethodDeclaration's range
        # starts at the first annotation line.)
        tree = ast.parse(DECORATED_SRC)
        parents = _build_parent_map(tree)
        root = _buggy_subtree_root(tree, 1, 3, parents)
        assert isinstance(root, ast.Module)

    def test_multiline_call_continuation_lines_returns_assign(self):
        # MULTILINE_CALL_SRC: lines 1..5. Range [2, 4] encloses by both
        # Assign [1, 5] and Call [1, 5] — both span 4. DFS pre-order
        # visits Assign (parent) before Call (child), so Assign wins.
        tree = ast.parse(MULTILINE_CALL_SRC)
        parents = _build_parent_map(tree)
        root = _buggy_subtree_root(tree, 2, 4, parents)
        assert isinstance(root, ast.Assign)

    def test_try_line_returns_try(self):
        # Range [2, 2]. Try [2, 9] (span 7) is tighter than FunctionDef
        # f [1, 9] (span 8). No tighter enclosing node exists (children
        # of Try are at lines 3+).
        tree = ast.parse(TRY_SRC)
        parents = _build_parent_map(tree)
        root = _buggy_subtree_root(tree, 2, 2, parents)
        assert isinstance(root, ast.Try)

    def test_except_handler_line_returns_type_name(self):
        # Range [4, 4] = `except ValueError:` line. ExceptHandler [4, 5]
        # (span 1) encloses, but its `type` Name ValueError [4, 4]
        # (span 0) is tighter and wins.
        tree = ast.parse(TRY_SRC)
        parents = _build_parent_map(tree)
        root = _buggy_subtree_root(tree, 4, 4, parents)
        assert isinstance(root, ast.Name)
        assert root.id == "ValueError"

    def test_range_covering_two_except_branches_returns_try(self):
        # Range [4, 7] spans both ExceptHandlers. Neither handler alone
        # encloses → Try [2, 9] is the smallest enclosing.
        tree = ast.parse(TRY_SRC)
        parents = _build_parent_map(tree)
        root = _buggy_subtree_root(tree, 4, 7, parents)
        assert isinstance(root, ast.Try)

    def test_list_comprehension_line_returns_assign(self):
        # Range [2, 2] = `out = [x * 2 for x in items if x > 0]`.
        # Assign, Name out, ListComp all have range [2, 2] (span 0).
        # DFS pre-order picks the parent Assign first.
        tree = ast.parse(COMPREHENSION_SRC)
        parents = _build_parent_map(tree)
        root = _buggy_subtree_root(tree, 2, 2, parents)
        assert isinstance(root, ast.Assign)

    def test_lambda_line_returns_assign(self):
        # Single-line file `add = lambda a, b: a + b`. Multiple span-0
        # candidates; Assign is parent → wins by DFS-first.
        tree = ast.parse(LAMBDA_SRC)
        parents = _build_parent_map(tree)
        root = _buggy_subtree_root(tree, 1, 1, parents)
        assert isinstance(root, ast.Assign)

    def test_deeply_nested_innermost_only_returns_return(self):
        # `return 1` is on line 6. Return [6, 6] (span 0) beats every
        # enclosing FunctionDef.
        tree = ast.parse(DEEP_NESTED_SRC)
        parents = _build_parent_map(tree)
        root = _buggy_subtree_root(tree, 6, 6, parents)
        assert isinstance(root, ast.Return)

    def test_deeply_nested_two_levels_returns_innermost_function(self):
        # Range [5, 6]. FunctionDef e [5, 7] (span 2) is the tightest
        # enclosing node; its body's Return [6, 6] doesn't enclose [5, 6].
        tree = ast.parse(DEEP_NESTED_SRC)
        parents = _build_parent_map(tree)
        root = _buggy_subtree_root(tree, 5, 6, parents)
        assert isinstance(root, ast.FunctionDef)
        assert root.name == "e"

    def test_negative_lines_no_match(self):
        # AST nodes have lineno >= 1, so `lineno <= -5` never holds.
        tree = ast.parse(SIMPLE_SRC)
        parents = _build_parent_map(tree)
        root = _buggy_subtree_root(tree, -5, -1, parents)
        assert root is tree

    def test_zero_line_no_match(self):
        # Predicate `lineno <= 0` never holds for AST nodes (1-indexed).
        tree = ast.parse(SIMPLE_SRC)
        parents = _build_parent_map(tree)
        root = _buggy_subtree_root(tree, 0, 0, parents)
        assert root is tree

    def test_empty_module(self):
        tree = ast.parse("")
        parents = _build_parent_map(tree)
        root = _buggy_subtree_root(tree, 1, 10, parents)
        assert root is tree

    def test_comments_only_module(self):
        # ast.parse strips comments → empty body, no candidates.
        tree = ast.parse("# only a comment\n# another\n")
        parents = _build_parent_map(tree)
        root = _buggy_subtree_root(tree, 1, 2, parents)
        assert root is tree

    def test_returned_root_actually_encloses_the_hunk_range(self):
        """Property: the returned node's [lineno, end_lineno] must fully
        enclose the requested [start, end]. (Trivially holds for the
        Module fallback since by convention it represents the whole file.)
        """
        tree = ast.parse(CLASS_SRC)
        parents = _build_parent_map(tree)
        start, end = 2, 4
        root = _buggy_subtree_root(tree, start, end, parents)
        ns = getattr(root, "lineno", None)
        ne = getattr(root, "end_lineno", None)
        if ns is not None and ne is not None:
            assert ns <= start and ne >= end, (
                f"Returned root {type(root).__name__} [{ns},{ne}] does not "
                f"enclose hunk [{start},{end}]"
            )
        else:
            # Module fallback path
            assert isinstance(root, ast.Module)

    def test_returned_root_is_smallest_among_enclosing_candidates(self):
        """Property: no other enclosing AST node has a strictly smaller
        line span than the returned root."""
        tree = ast.parse(CLASS_SRC)
        parents = _build_parent_map(tree)
        start, end = 3, 3   # body of m1: `a = 1`
        root = _buggy_subtree_root(tree, start, end, parents)

        ns = getattr(root, "lineno", None)
        ne = getattr(root, "end_lineno", None)
        # If we got the Module fallback, the property is vacuous
        if ns is None or ne is None:
            return
        root_span = ne - ns

        for n in ast.walk(tree):
            cs = getattr(n, "lineno", None)
            ce = getattr(n, "end_lineno", None)
            if cs is None or ce is None:
                continue
            if cs <= start and ce >= end:
                cand_span = ce - cs
                assert cand_span >= root_span, (
                    f"{type(n).__name__} [{cs},{ce}] (span {cand_span}) "
                    f"is tighter than returned {type(root).__name__} "
                    f"(span {root_span})"
                )


# ── 3. _subtree_diameter ────────────────────────────────────────────────────

class TestSubtreeDiameter:
    """The diameter is computed via the two-BFS algorithm — exact O(N)
    port of MethodLineExtractor.java's subtreeDiameter."""

    def test_trivial_tree(self):
        tree = ast.parse("")
        parents = _build_parent_map(tree)
        # Empty module has 1 node and no children → diameter 1 (clamp)
        assert _subtree_diameter(tree, parents) == 1

    def test_simple_tree_positive(self):
        tree = ast.parse(SIMPLE_SRC)
        parents = _build_parent_map(tree)
        assert _subtree_diameter(tree, parents) >= 2

    def test_diameter_grows_with_depth(self):
        shallow = ast.parse("x = 1\ny = 2\n")
        deep = ast.parse(DEEP_NESTED_SRC)
        ds = _subtree_diameter(shallow, _build_parent_map(shallow))
        dd = _subtree_diameter(deep, _build_parent_map(deep))
        assert dd > ds

    def test_diameter_at_least_max_pair_seen(self):
        tree = ast.parse(NESTED_SRC)
        parents = _build_parent_map(tree)
        outer = tree.body[0]
        ret_inner = outer.body[0].body[-1]
        d = _ast_node_distance(outer, ret_inner, parents)
        assert _subtree_diameter(tree, parents) >= d

    def test_diameter_is_deterministic(self):
        # Two-BFS is a pure deterministic algorithm — no random seed,
        # no sampling — repeated calls must agree exactly.
        big_src = "\n".join(f"x{i} = {i}" for i in range(2000))
        tree = ast.parse(big_src)
        parents = _build_parent_map(tree)
        d1 = _subtree_diameter(tree, parents)
        d2 = _subtree_diameter(tree, parents)
        assert d1 == d2

    @staticmethod
    def _exhaustive_diameter(tree, parents):
        """Reference implementation: pairwise max over every distinct
        structural node pair. Excludes shared singleton marker nodes
        (Load/Store/Add/Eq/...) — they are not part of the structural
        tree (one shared instance is reused across the whole file)."""
        from hunk_divergence import _AST_SHARED_SINGLETONS
        nodes = [
            n for n in ast.walk(tree)
            if not isinstance(n, _AST_SHARED_SINGLETONS)
        ]
        exhaustive = 0
        for i in range(len(nodes)):
            for j in range(i + 1, len(nodes)):
                exhaustive = max(
                    exhaustive,
                    _ast_node_distance(nodes[i], nodes[j], parents),
                )
        return max(exhaustive, 1)

    def test_diameter_matches_exhaustive_on_nested(self):
        """Two-BFS must equal the exact pairwise max over every node pair.

        This is the property the previous (sampled) implementation could
        violate on large trees.
        """
        tree = ast.parse(NESTED_SRC)
        parents = _build_parent_map(tree)
        assert _subtree_diameter(tree, parents) == \
            self._exhaustive_diameter(tree, parents)

    def test_diameter_matches_exhaustive_on_class_tree(self):
        tree = ast.parse(CLASS_SRC)
        parents = _build_parent_map(tree)
        assert _subtree_diameter(tree, parents) == \
            self._exhaustive_diameter(tree, parents)

    def test_diameter_matches_exhaustive_on_try(self):
        tree = ast.parse(TRY_SRC)
        parents = _build_parent_map(tree)
        assert _subtree_diameter(tree, parents) == \
            self._exhaustive_diameter(tree, parents)

    def test_diameter_matches_exhaustive_on_decorated(self):
        tree = ast.parse(DECORATED_SRC)
        parents = _build_parent_map(tree)
        assert _subtree_diameter(tree, parents) == \
            self._exhaustive_diameter(tree, parents)

    def test_diameter_exact_on_large_file(self):
        """No 500-leaf cap → large files no longer under-estimate.

        Under the old sampled implementation, files with > 500 leaves
        could miss the true diameter. With the two-BFS port the result
        is exact regardless of file size.
        """
        # 600 top-level assignments — well past the old 500 cap.
        big_src = "\n".join(f"x{i} = {i}" for i in range(600))
        tree = ast.parse(big_src)
        parents = _build_parent_map(tree)
        diam = _subtree_diameter(tree, parents)
        # Structural shape per assignment: Module → Assign → {Name, Constant}
        # (Store is a shared singleton, filtered out). So leaves are at
        # depth 2; two leaves in different assignments share Module as
        # their LCA, distance = 2 + 2 = 4.
        assert diam == 4
        # And the two-BFS result must equal the exhaustive maximum.
        assert diam == self._exhaustive_diameter(tree, parents)


# ── 4. parse_patch_hunks ────────────────────────────────────────────────────

PATCH_SINGLE_FILE = """diff --git a/pkg/a.py b/pkg/a.py
index 1234567..89abcde 100644
--- a/pkg/a.py
+++ b/pkg/a.py
@@ -1,3 +1,3 @@
 def f():
-    return 1
+    return 2
"""

PATCH_TWO_HUNKS = """diff --git a/pkg/a.py b/pkg/a.py
--- a/pkg/a.py
+++ b/pkg/a.py
@@ -1,3 +1,3 @@
 def f():
-    return 1
+    return 2
@@ -10,3 +10,3 @@
 def g():
-    return 3
+    return 4
"""

PATCH_TWO_FILES = """diff --git a/pkg/a.py b/pkg/a.py
--- a/pkg/a.py
+++ b/pkg/a.py
@@ -1,2 +1,2 @@
-old
+new
diff --git a/pkg/b.py b/pkg/b.py
--- a/pkg/b.py
+++ b/pkg/b.py
@@ -5,2 +5,2 @@
-foo
+bar
"""


class TestParsePatchHunks:
    def test_empty_patch(self):
        assert parse_patch_hunks("") == []
        assert parse_patch_hunks("   ") == []

    def test_single_hunk(self):
        hunks = parse_patch_hunks(PATCH_SINGLE_FILE)
        assert len(hunks) == 1
        h = hunks[0]
        assert h["file"] == "pkg/a.py"
        assert h["start_line"] == 1
        assert h["end_line"] == 3
        assert h["buggy"] == ["    return 1"]
        assert h["fixed"] == ["    return 2"]

    def test_two_hunks_same_file(self):
        hunks = parse_patch_hunks(PATCH_TWO_HUNKS)
        assert len(hunks) == 2
        assert all(h["file"] == "pkg/a.py" for h in hunks)
        assert hunks[0]["start_line"] == 1
        assert hunks[1]["start_line"] == 10

    def test_two_files(self):
        hunks = parse_patch_hunks(PATCH_TWO_FILES)
        assert len(hunks) == 2
        assert hunks[0]["file"] == "pkg/a.py"
        assert hunks[1]["file"] == "pkg/b.py"

    def test_single_line_hunk_no_count(self):
        patch = (
            "diff --git a/x.py b/x.py\n"
            "--- a/x.py\n"
            "+++ b/x.py\n"
            "@@ -5 +5 @@\n"
            "-a\n"
            "+b\n"
        )
        hunks = parse_patch_hunks(patch)
        assert len(hunks) == 1
        # No count → defaults to 1, so end_line == start_line
        assert hunks[0]["start_line"] == 5
        assert hunks[0]["end_line"] == 5

    def test_excludes_diff_header_lines(self):
        # `+++` / `---` lines must NOT be picked up as +/- content
        hunks = parse_patch_hunks(PATCH_SINGLE_FILE)
        assert "+++ b/pkg/a.py" not in hunks[0]["fixed"]
        assert "--- a/pkg/a.py" not in hunks[0]["buggy"]


# ── 5. compute_ast_metrics_for_file ─────────────────────────────────────────

class TestComputeASTMetricsForFile:
    def test_syntax_error_returns_safe_defaults(self):
        diam, pairs = compute_ast_metrics_for_file("def (((", [(0, 1, 1)])
        assert diam == 1
        assert pairs == {}

    def test_pair_distance_same_function(self):
        # Two hunks both in foo's body → small distance
        diam, pairs = compute_ast_metrics_for_file(
            SIMPLE_SRC, [(0, 2, 2), (1, 3, 3)]
        )
        assert "0_1" in pairs
        assert pairs["0_1"] >= 0

    def test_pair_distance_two_methods_same_class(self):
        # Hunks in m1 body (line 3) and m2 body (line 7) → LCA is class
        diam, pairs = compute_ast_metrics_for_file(
            CLASS_SRC, [(0, 3, 3), (1, 7, 7)]
        )
        # Distance between two Assign nodes inside sibling FunctionDefs
        # under the same ClassDef should be > 0
        assert pairs["0_1"] > 0

    def test_no_pairs_for_single_hunk(self):
        diam, pairs = compute_ast_metrics_for_file(SIMPLE_SRC, [(0, 1, 1)])
        assert pairs == {}

    def test_three_hunks_yield_three_pairs(self):
        diam, pairs = compute_ast_metrics_for_file(
            CLASS_SRC, [(0, 3, 3), (1, 4, 4), (2, 7, 7)]
        )
        assert set(pairs.keys()) == {"0_1", "0_2", "1_2"}

    def test_pair_keys_use_hunk_ids_not_positions(self):
        # Hunk IDs 5 and 9 — keys must be "5_9", not "0_1"
        diam, pairs = compute_ast_metrics_for_file(
            SIMPLE_SRC, [(5, 2, 2), (9, 6, 6)]
        )
        assert "5_9" in pairs

    def test_two_hunks_resolving_to_same_root_have_zero_distance(self):
        diam, pairs = compute_ast_metrics_for_file(
            SIMPLE_SRC, [(0, 2, 2), (1, 2, 2)]
        )
        assert pairs["0_1"] == 0

    def test_intra_function_smaller_than_inter_function(self):
        # Two hunks inside foo vs one in foo + one in bar
        _, pairs_inside = compute_ast_metrics_for_file(
            SIMPLE_SRC, [(0, 2, 2), (1, 3, 3)]
        )
        _, pairs_across = compute_ast_metrics_for_file(
            SIMPLE_SRC, [(0, 2, 2), (1, 6, 6)]
        )
        assert pairs_inside["0_1"] < pairs_across["0_1"]

    def test_out_of_range_hunk_falls_back_to_module(self):
        # First hunk inside foo, second beyond EOF → second resolves to Module
        diam, pairs = compute_ast_metrics_for_file(
            SIMPLE_SRC, [(0, 2, 2), (1, 999, 1000)]
        )
        # Module ↔ Assign-inside-foo distance must be > 0
        assert pairs["0_1"] > 0

    def test_pair_distance_bounded_by_diameter(self):
        diam, pairs = compute_ast_metrics_for_file(
            NESTED_SRC, [(0, 2, 2), (1, 3, 5), (2, 7, 7)]
        )
        for d in pairs.values():
            assert d <= diam


# ── 6. compute_metrics_for_bug ──────────────────────────────────────────────

class TestComputeMetricsForBug:
    def test_single_hunk_zero_divergence(self):
        hunks = [{"file": "a.py", "patch_lines": ["x"], "hunk_id": 0}]
        div, rows = compute_metrics_for_bug("bug", hunks, {})
        assert div == 0.0
        assert rows == []

    def test_same_file_uses_ast_distance(self):
        hunks = [
            {"file": "a.py", "patch_lines": ["return 1"], "hunk_id": 0},
            {"file": "a.py", "patch_lines": ["return 2"], "hunk_id": 1},
        ]
        ast_metrics = {"a.py": {"diameter": 10, "pairs": {"0_1": 4}}}
        div, rows = compute_metrics_for_bug("bug", hunks, ast_metrics)
        # Single pair, n=2 → divergence = ln(2) * normalised
        assert len(rows) == 1
        # Same-file: γ stays at initial 1, D_dir = 0 (Algorithm 1 line 15);
        # row[4] is D_dir
        assert rows[0][4] == "0.0000"
        # D_ast = log1p(4)/log1p(10)
        expected_dast = math.log1p(4) / math.log1p(10)
        assert float(rows[0][3]) == pytest.approx(expected_dast, abs=1e-3)

    def test_cross_file_uses_directory_distance(self):
        hunks = [
            {"file": "pkg/a.py", "patch_lines": ["x"], "hunk_id": 0},
            {"file": "other/b.py", "patch_lines": ["y"], "hunk_id": 1},
        ]
        div, rows = compute_metrics_for_bug("bug", hunks, {})
        # Cross-file → D_ast forced to 1.0, gamma=2
        assert rows[0][3] == "1.0000"
        # Different top-level dirs → common = 0; maxlen=2
        # D_dir = 1 - (0/2) = 1.0  (paper bound: D_dir ∈ [0, 1])
        assert float(rows[0][4]) == pytest.approx(1.0, abs=1e-4)

    def test_n_hunks_scaling(self):
        # 3 identical-file hunks: divergence = ln(3) * mean(normalised)
        hunks = [
            {"file": "a.py", "patch_lines": ["x"], "hunk_id": i}
            for i in range(3)
        ]
        ast_metrics = {
            "a.py": {
                "diameter": 5,
                "pairs": {"0_1": 1, "0_2": 1, "1_2": 1},
            }
        }
        div, rows = compute_metrics_for_bug("bug", hunks, ast_metrics)
        assert len(rows) == 3
        # All identical patch_lines → BLEU=1 → D_lex=0 → divergence=0
        assert div == pytest.approx(0.0, abs=1e-6)


# ── 7. Hand-verifiable AST scenarios ────────────────────────────────────────
#
# Each test pins the *exact* expected AST shape, hunk-root resolution,
# raw_ast distance, diameter, and D_ast so a reader can verify the value
# manually against the documented tree.
#
# All hunks here are SINGLE-LINE ([L, L]) so a span-0 leaf node always
# wins _buggy_subtree_root's smallest-enclosing-span tie-break — this is
# the cleanest scenario where each hunk maps to one obvious AST node.

def _load_manual_case(filename: str) -> str:
    """Load a hand-crafted Python source from resources/manual_testing/
    for the TestManualAstVerification cases.

    Each case keeps its source in its own file so the line numbers
    referenced inside the test docstrings match the file 1:1, making
    the AST shape easy to verify by eye.
    """
    return (
        Path(__file__).parent / "resources" / "manual_testing" / filename
    ).read_text(encoding="utf-8")


class TestManualAstVerification:

    def test_case1_two_assigns_same_function(self):
        """
        Source:                                Tree (Store ctx singletons skipped):
            1: def f():                        Module
            2:     a = 1                       └─ FunctionDef f          [1,3]
            3:     b = 2                          ├─ arguments
                                                  ├─ Assign              [2,2]
                                                  │   ├─ Name a          [2,2]
                                                  │   └─ Constant 1      [2,2]
                                                  └─ Assign              [3,3]
                                                      ├─ Name b          [3,3]
                                                      └─ Constant 2      [3,3]

        Hunk [2,2]: candidates with lineno≤2 ∧ end_lineno≥2 →
            FunctionDef (span 2), Assign (span 0), Name a (span 0),
            Constant 1 (span 0). Best span = 0; DFS pre-order under
            FunctionDef visits Assign before its children → Assign wins.
        Hunk [3,3]: same logic → Assign at line 3 wins.

        Depth(Assign@2) = 2, Depth(Assign@3) = 2, LCA = FunctionDef (depth 1).
        raw_ast = 2 + 2 - 2*1 = 2.

        Diameter (deepest two leaves): Name a (depth 3) and Name b
        (depth 3); LCA = FunctionDef (depth 1). diameter = 3 + 3 - 2 = 4.

        D_ast = ln(1+2) / ln(1+4) = ln(3) / ln(5) ≈ 0.6826.
        """
        src = _load_manual_case("manual_case1_two_assigns_same_function.py")
        tree = ast.parse(src)
        parents = _build_parent_map(tree)

        r2 = _buggy_subtree_root(tree, 2, 2, parents)
        r3 = _buggy_subtree_root(tree, 3, 3, parents)
        assert isinstance(r2, ast.Assign)
        assert isinstance(r3, ast.Assign)

        raw = _ast_node_distance(r2, r3, parents)
        assert raw == 2

        diameter = _subtree_diameter(tree, parents)
        assert diameter == 4

        diam, pairs = compute_ast_metrics_for_file(src, [(0, 2, 2), (1, 3, 3)])
        assert diam == 4
        assert pairs["0_1"] == 2

        expected_dast = math.log1p(2) / math.log1p(4)
        assert expected_dast == pytest.approx(0.6826, abs=1e-3)

    def test_case2_two_top_level_functions(self):
        """
        Source:                              Tree:
            1: def foo():                    Module
            2:     return 1                  ├─ FunctionDef foo         [1,2]
            3:                               │   ├─ arguments
            4: def bar():                    │   └─ Return              [2,2]
            5:     return 2                  │       └─ Constant 1      [2,2]
                                             └─ FunctionDef bar         [4,5]
                                                 ├─ arguments
                                                 └─ Return              [5,5]
                                                     └─ Constant 2      [5,5]

        Hunk [2,2]: FunctionDef foo (span 1), Return (span 0),
            Constant 1 (span 0). Best span 0; DFS visits Return before
            Constant. → Return wins.
        Hunk [5,5]: same logic → Return wins.

        Depth(Return@2) = 2, Depth(Return@5) = 2, LCA = Module (depth 0).
        raw_ast = 2 + 2 - 0 = 4.

        Diameter: deepest leaves Constant 1 (depth 3) and Constant 2
        (depth 3); LCA = Module. diameter = 3 + 3 = 6.

        D_ast = ln(1+4) / ln(1+6) = ln(5) / ln(7) ≈ 0.8271.
        """
        src = _load_manual_case("manual_case2_two_top_level_functions.py")
        tree = ast.parse(src)
        parents = _build_parent_map(tree)

        r2 = _buggy_subtree_root(tree, 2, 2, parents)
        r5 = _buggy_subtree_root(tree, 5, 5, parents)
        assert isinstance(r2, ast.Return)
        assert isinstance(r5, ast.Return)

        raw = _ast_node_distance(r2, r5, parents)
        assert raw == 4

        diameter = _subtree_diameter(tree, parents)
        assert diameter == 6

        diam, pairs = compute_ast_metrics_for_file(src, [(0, 2, 2), (1, 5, 5)])
        assert diam == 6
        assert pairs["0_1"] == 4

        expected_dast = math.log1p(4) / math.log1p(6)
        assert expected_dast == pytest.approx(0.8271, abs=1e-3)

    def test_case3_two_methods_one_class(self):
        """
        Source:                              Tree:
            1: class C:                      Module
            2:     def m1(self):             └─ ClassDef C              [1,5]
            3:         return 1                  ├─ FunctionDef m1      [2,3]
            4:     def m2(self):                 │   ├─ arguments
            5:         return 2                  │   │   └─ arg self    [2,2]
                                                 │   └─ Return          [3,3]
                                                 │       └─ Constant 1  [3,3]
                                                 └─ FunctionDef m2      [4,5]
                                                     ├─ arguments
                                                     │   └─ arg self    [4,4]
                                                     └─ Return          [5,5]
                                                         └─ Constant 2  [5,5]

        Hunk [3,3] → Return at line 3 (span 0 wins; visited in DFS
            pre-order before its child Constant).
        Hunk [5,5] → Return at line 5 (same logic).

        Depth(Return@3) = 3, Depth(Return@5) = 3, LCA = ClassDef (depth 1).
        raw_ast = 3 + 3 - 2*1 = 4.

        Diameter path (length 6, edge-by-edge):
            Constant(1) ─ Return ─ FuncDef m1 ─ ClassDef
                         ─ FuncDef m2 ─ Return ─ Constant(2)
        Both leaves at depth 4, LCA at depth 1 → 4 + 4 - 2 = 6.

        Identical to case 2: wrapping the methods in ClassDef pushes
        both leaves down by 1 *and* pushes the LCA down by 1, so the
        two effects cancel.

        D_ast = ln(1+4) / ln(1+6) = ln(5) / ln(7) ≈ 0.8271.
        """
        src = _load_manual_case("manual_case3_two_methods_one_class.py")
        tree = ast.parse(src)
        parents = _build_parent_map(tree)

        r3 = _buggy_subtree_root(tree, 3, 3, parents)
        r5 = _buggy_subtree_root(tree, 5, 5, parents)
        assert isinstance(r3, ast.Return)
        assert isinstance(r5, ast.Return)

        raw = _ast_node_distance(r3, r5, parents)
        assert raw == 4

        diameter = _subtree_diameter(tree, parents)
        assert diameter == 6

        diam, pairs = compute_ast_metrics_for_file(src, [(0, 3, 3), (1, 5, 5)])
        assert diam == 6
        assert pairs["0_1"] == 4

        expected_dast = math.log1p(4) / math.log1p(6)
        assert expected_dast == pytest.approx(0.8271, abs=1e-3)

    def test_case4_three_hunks_class_with_three_methods(self):
        """
        Source:                              Tree (per-method shape same as case 3):
            1: class C:                      Module
            2:     def m1(self):             └─ ClassDef C              [1,7]
            3:         return 1                  ├─ FunctionDef m1      [2,3]
            4:     def m2(self):                 │   └─ Return          [3,3]
            5:         return 2                  │       └─ Constant 1  [3,3]
            6:     def m3(self):                 ├─ FunctionDef m2      [4,5]
            7:         return 3                  │   └─ Return          [5,5]
                                                 │       └─ Constant 2  [5,5]
                                                 └─ FunctionDef m3      [6,7]
                                                     └─ Return          [7,7]
                                                         └─ Constant 3  [7,7]

        Three hunks at the three return lines. By the same reasoning as
        case 3, each pair of Return nodes is at depth 3 with LCA
        ClassDef (depth 1) → raw_ast = 4 for every pair.
        """
        src = _load_manual_case("manual_case4_three_methods_one_class.py")
        diam, pairs = compute_ast_metrics_for_file(
            src, [(0, 3, 3), (1, 5, 5), (2, 7, 7)]
        )
        assert diam == 6
        assert pairs["0_1"] == 4
        assert pairs["0_2"] == 4
        assert pairs["1_2"] == 4

    def test_case5_nested_function_inner_vs_outer_body(self):
        """
        Source:                              Tree:
            1: def outer():                  Module
            2:     x = 1                     └─ FunctionDef outer       [1,5]
            3:     def inner():                  ├─ arguments
            4:         y = 2                     ├─ Assign              [2,2]
            5:         return y                  │   ├─ Name x          [2,2]
                                                 │   └─ Constant 1      [2,2]
                                                 └─ FunctionDef inner   [3,5]
                                                     ├─ arguments
                                                     ├─ Assign          [4,4]
                                                     │   ├─ Name y      [4,4]
                                                     │   └─ Constant 2  [4,4]
                                                     └─ Return          [5,5]
                                                         └─ Name y      [5,5]

        Hunk [2,2]: span-0 winner under FunctionDef outer → Assign at 2.
        Hunk [4,4]: span-0 winner under FunctionDef inner → Assign at 4.

        Depth(Assign@2) = 2 (Module → FunctionDef outer → Assign).
        Depth(Assign@4) = 3 (Module → FunctionDef outer → FunctionDef inner → Assign).
        LCA = FunctionDef outer (depth 1).
        raw_ast = 2 + 3 - 2*1 = 3.

        Diameter path (length 5, edge-by-edge):
            Name(x) ─ Assign(x=1) ─ FuncDef outer
                    ─ FuncDef inner ─ Assign(y=2) ─ Name(y)
        Name x at depth 3, Name y (in inner's Assign) at depth 4,
        LCA = FunctionDef outer (depth 1) → 3 + 4 - 2 = 5.
        """
        src = _load_manual_case("manual_case5_nested_function.py")
        tree = ast.parse(src)
        parents = _build_parent_map(tree)

        r2 = _buggy_subtree_root(tree, 2, 2, parents)
        r4 = _buggy_subtree_root(tree, 4, 4, parents)
        assert isinstance(r2, ast.Assign)
        assert isinstance(r4, ast.Assign)
        assert _ast_node_distance(r2, r4, parents) == 3

        assert _subtree_diameter(tree, parents) == 5

        diam, pairs = compute_ast_metrics_for_file(
            src, [(0, 2, 2), (1, 4, 4)]
        )
        assert diam == 5
        assert pairs["0_1"] == 3

    def test_case6_lca_is_control_flow_node(self):
        """
        Source:                              Tree:
            1: def outer():                  Module
            2:     if True:                  └─ FunctionDef outer       [1,4]
            3:         a = 1                     ├─ arguments
            4:         b = 2                     └─ If                  [2,4]
                                                     ├─ Constant True   [2,2]
                                                     ├─ Assign          [3,3]
                                                     │   ├─ Name a      [3,3]
                                                     │   └─ Constant 1  [3,3]
                                                     └─ Assign          [4,4]
                                                         ├─ Name b      [4,4]
                                                         └─ Constant 2  [4,4]

        The LCA here is the `If` node — neither the Module root nor a
        FunctionDef/ClassDef. Confirms the LCA-walk works for arbitrary
        intermediate structural nodes.

        Hunk [3,3] → Assign at line 3 (depth 3, span 0 wins).
        Hunk [4,4] → Assign at line 4 (depth 3, span 0 wins).
        LCA = If (depth 2).
        raw_ast = 3 + 3 - 2*2 = 2.

        Diameter path (length 4, edge-by-edge):
            Name(a) ─ Assign(a=1) ─ If ─ Assign(b=2) ─ Name(b)
        Both leaves at depth 4, LCA = If (depth 2) → 4 + 4 - 4 = 4.
        """
        src = _load_manual_case("manual_case6_lca_control_flow.py")
        tree = ast.parse(src)
        parents = _build_parent_map(tree)

        r3 = _buggy_subtree_root(tree, 3, 3, parents)
        r4 = _buggy_subtree_root(tree, 4, 4, parents)
        assert isinstance(r3, ast.Assign)
        assert isinstance(r4, ast.Assign)

        # Pin the LCA explicitly — it must be the If, not the FunctionDef
        # or the Module.
        lca = _lca(r3, r4, parents)
        assert isinstance(lca, ast.If)

        assert _ast_node_distance(r3, r4, parents) == 2
        assert _subtree_diameter(tree, parents) == 4

        diam, pairs = compute_ast_metrics_for_file(
            src, [(0, 3, 3), (1, 4, 4)]
        )
        assert diam == 4
        assert pairs["0_1"] == 2

    def test_case7_method_root_with_while_descendant(self):
        """Multi-line hunks where each hunk's smallest enclosing node
        is a *block* (not a single statement), and the two roots stand
        in an ancestor-descendant relationship.

        Source:                                    Tree (depths shown):
            1: def method_a():                     Module                  d=0
            2:     a = 1            ┐ h1           └─ FunctionDef method_a d=1  [1,8]
            3:     b = 2            │ [2,4]            ├─ arguments        d=2
            4:     c = 3            ┘                  ├─ Assign  (a=1)    d=2  [2,2]
            5:     while index <= length:               ├─ Assign  (b=2)    d=2  [3,3]
            6:         d = 4        ┐ h2                ├─ Assign  (c=3)    d=2  [4,4]
            7:         e = 5        │ [6,8]             └─ While            d=2  [5,8]
            8:         f = 6        ┘                       ├─ Compare      d=3  [5,5]
                                                            │   ├─ Name index  d=4
                                                            │   └─ Name length d=4
                                                            ├─ Assign (d=4) d=3  [6,6]
                                                            ├─ Assign (e=5) d=3  [7,7]
                                                            └─ Assign (f=6) d=3  [8,8]

        Hunk 1 = lines [2, 4]: each individual Assign is on a *single*
            line, so no Assign encloses the 3-line span. The only
            enclosing structural node is FunctionDef [1, 8]. → root = FunctionDef.

        Hunk 2 = lines [6, 8]: candidates are FunctionDef [1, 8] (span 7)
            and While [5, 8] (span 3). The While's body Assigns are each
            on a single line so they don't enclose [6, 8]. While wins.
            → root = While.

        Distance: FunctionDef (depth 1) is an ancestor of While (depth 2),
        so LCA = FunctionDef itself. raw_ast = 1 + 2 - 2*1 = 1.

        Diameter (length 5): top-level Assign leaf at depth 3
        (e.g. Name a) ↔ While-body Assign leaf at depth 4 (e.g. Name d).
        LCA = FunctionDef (depth 1) → 3 + 4 - 2 = 5.
        """
        src = _load_manual_case("manual_case7_method_and_while_descendant.py")
        tree = ast.parse(src)
        parents = _build_parent_map(tree)

        h1 = _buggy_subtree_root(tree, 2, 4, parents)
        h2 = _buggy_subtree_root(tree, 6, 8, parents)
        assert isinstance(h1, ast.FunctionDef)
        assert h1.name == "method_a"
        assert isinstance(h2, ast.While)

        # Ancestor-descendant: LCA must be the FunctionDef itself.
        assert _lca(h1, h2, parents) is h1

        assert _ast_node_distance(h1, h2, parents) == 1
        assert _subtree_diameter(tree, parents) == 5

        diam, pairs = compute_ast_metrics_for_file(
            src, [(0, 2, 4), (1, 6, 8)]
        )
        assert diam == 5
        assert pairs["0_1"] == 1

    def test_case8_two_hunks_resolving_to_same_method(self):
        """Both hunks span sibling statements at the *method* level,
        bracketing an unrelated for-loop. Neither hunk has a tighter
        enclosing block than the FunctionDef itself, so both roots
        collapse to the same node → AST distance = 0.

        Source:                                    Tree (depths shown):
            1: def method_a():                     Module                  d=0
            2:     a = 1            ┐ h1           └─ FunctionDef method_a d=1  [1,8]
            3:     b = 2            ┘ [2,3]            ├─ arguments        d=2
            4:     for x in items:                      ├─ Assign  (a=1)    d=2  [2,2]
            5:         c = 3                            ├─ Assign  (b=2)    d=2  [3,3]
            6:         d = 4                            ├─ For              d=2  [4,6]
            7:     e = 5            ┐ h2                │   └─ ...
            8:     f = 6            ┘ [7,8]             ├─ Assign  (e=5)    d=2  [7,7]
                                                        └─ Assign  (f=6)    d=2  [8,8]

        Hunk 1 = lines [2, 3]: no single Assign encloses both lines, the
            For loop [4, 6] doesn't include them. → root = FunctionDef.

        Hunk 2 = lines [7, 8]: same logic — no single Assign covers both,
            For loop ended at line 6. → root = FunctionDef.

        Both roots point to the *same* FunctionDef object, so:
            raw_ast = depth + depth - 2*depth = 0.

        This is a critical edge case: the implementation must return 0
        (not crash, not return some "minimum 1") when both hunks resolve
        to the same enclosing node.
        """
        src = _load_manual_case("manual_case8_two_hunks_same_method.py")
        tree = ast.parse(src)
        parents = _build_parent_map(tree)

        h1 = _buggy_subtree_root(tree, 2, 3, parents)
        h2 = _buggy_subtree_root(tree, 7, 8, parents)
        assert isinstance(h1, ast.FunctionDef)
        assert isinstance(h2, ast.FunctionDef)
        assert h1 is h2                          # same node, not just same type
        assert _ast_node_distance(h1, h2, parents) == 0

        diam, pairs = compute_ast_metrics_for_file(
            src, [(0, 2, 3), (1, 7, 8)]
        )
        assert pairs["0_1"] == 0

    def test_case9_dast_formula_matches_log1p_ratio(self):
        """End-to-end pin of D_ast = log1p(raw) / log1p(diameter)
        as it appears in compute_metrics_for_bug for same-file pairs.

        Reuses case 1's numbers (raw=2, diameter=4) and feeds them
        through compute_metrics_for_bug. Picks disjoint patch_lines so
        BLEU=0 and D_lex=1, giving:
            divergence = ln(2) * (1.0 * D_ast) / (1+1)
                       = ln(2) * D_ast / 2.
        """
        ast_metrics = {
            "f.py": {"diameter": 4, "pairs": {"0_1": 2}},
        }
        hunks = [
            {"file": "f.py",
             "patch_lines": ["alpha beta gamma delta"],
             "hunk_id": 0},
            {"file": "f.py",
             "patch_lines": ["zeta eta theta iota"],
             "hunk_id": 1},
        ]
        div, rows = compute_metrics_for_bug("bug", hunks, ast_metrics)

        expected_dast = math.log1p(2) / math.log1p(4)
        assert float(rows[0][3]) == pytest.approx(expected_dast, abs=1e-4)
        assert rows[0][4] == "0.0000"          # D_dir for same-file pair
        assert float(rows[0][2]) == pytest.approx(1.0, abs=1e-4)  # D_lex

        expected_div = math.log(2) * expected_dast / 2.0
        assert div == pytest.approx(expected_div, abs=1e-4)


# ── 8. _read_source_file ────────────────────────────────────────────────────

class TestReadSourceFile:
    def test_reads_existing_file(self, tmp_path):
        inst = tmp_path / "instance"
        (inst / "pkg").mkdir(parents=True)
        (inst / "pkg" / "a.py").write_text("x = 1\n")
        assert _read_source_file(tmp_path, "instance", "pkg/a.py") == "x = 1\n"

    def test_missing_file_returns_none(self, tmp_path):
        assert _read_source_file(tmp_path, "instance", "nope.py") is None


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
