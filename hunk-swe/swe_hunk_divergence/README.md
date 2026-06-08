# SWE-bench Hunk Divergence

Computes hunk divergence scores for multi-hunk bugs in SWE-bench Verified. Ported from the Defects4J (Java) pipeline, replacing `javalang`/JavaParser with Python's built-in `ast` module.

## Hunk Divergence Formula

For a bug with **n** hunks, divergence is computed over all pairwise combinations:

```
divergence = ln(n) * mean(normalised_pair_divergence)
```

Each pair (i, j) computes three sub-metrics:

| Metric | Symbol | Description |
|--------|--------|-------------|
| Lexical distance | `D_lex` | `1 - BLEU(patch_i, patch_j)` using NLTK tokenization |
| AST-node distance | `D_ast` | `log1p(path_dist) / log1p(diameter)` (same-file) or `1.0` (cross-file) |
| File distance | `D_dir` | `1 - (common_prefix_segments / max_segments)` (cross-file) or `0.0` (same-file) |

These combine into a per-pair divergence:

```
pairDiv    = D_lex * (D_ast + gamma * D_dir)
normalised = pairDiv / (1 + gamma)
```

Where `gamma = 1` for same-file pairs (the initial value in Algorithm 1) and `gamma = 2` for cross-file pairs (overwritten in the cross-file branch). This means same-file pair divergences are bounded above by 0.5 (`maxDiv = 1 + 1 = 2`) and cross-file pair divergences by 1.0 (`maxDiv = 1 + 2 = 3`) — the asymmetry the paper introduces to amplify file-level separation.

## AST-Node Distance Calculation

The AST distance measures how far apart two hunks are in the syntactic structure of a shared source file. This is the Python port of the JavaParser-based distance used for Defects4J.

### Step 1: Parse and build parent map

The source file is parsed with `ast.parse()`. A parent map (`id(child) -> parent`) is built by walking the tree, enabling upward traversal from any node.

### Step 2: Find each hunk's representative node

For each hunk with line range `[start_line, end_line]` (from the `@@ -start,count` diff header), we locate the smallest AST node that spans the entire hunk:

1. Traverse the tree in pre-order (DFS, children pushed in reverse so the left-most child is visited first — matching JavaParser pre-order).
2. For every visited node, check whether `node.lineno <= start_line` **and** `node.end_lineno >= end_line` (the node fully encloses the hunk).
3. Among all enclosing nodes, keep the one with the smallest line span (`end_lineno - lineno`). That tightest enclosing node is the hunk's representative subtree root.
4. If no node encloses the range, fall back to the whole module.

This tightest-enclosing-node rule yields a single deterministic representative per hunk and matches the JavaParser-based pipeline used for Defects4J, so AST distances are comparable across language ports.

### Step 3: Compute pairwise path distance

For two hunk representative nodes `u` and `v`:

1. Find their **Lowest Common Ancestor (LCA)** by walking up from `u` collecting ancestors, then walking up from `v` until an ancestor of `u` is found
2. Compute `path_distance = depth(u) + depth(v) - 2 * depth(LCA)`

### Step 4: Normalize by tree diameter

The tree diameter is the maximum pairwise path distance in the entire file's AST. We compute it **exactly** via the standard two-BFS algorithm (O(N)):

1. Build an undirected parent↔child adjacency map over the AST. Shared singleton marker nodes (`Load`, `Store`, `Add`, `Eq`, `Lt`, ...) are excluded — Python's `ast` module reuses one instance for these, which would otherwise create file-wide shortcuts that collapse BFS distances.
2. Run BFS from the root to find one farthest node `u`.
3. Run BFS from `u`; the farthest distance reached is the diameter.

```
D_ast = log1p(path_distance) / log1p(diameter)
```

This yields a value in `[0, 1]` representing how structurally separated the two hunks are relative to the file's total AST extent.

## Files

### Scripts

| File | Description |
|------|-------------|
| `hunk_divergence.py` | Main script. Parses SWE-bench patches, reads source files from checked-out workspaces, computes AST metrics with Python `ast`, and outputs per-bug and per-pair divergence CSVs. |
| `evaluate_bleu.py` | BLEU score utility using NLTK `word_tokenize` and `sentence_bleu` with method4 smoothing. Used for lexical distance (`D_lex`). |

### Output CSVs

| File | Description |
|------|-------------|
| `total_hunk_divergence_results.csv` | One row per bug: `bug_id, hunk_count, divergence` |
| `pairwise_hunk_divergence_results.csv` | One row per hunk pair: `bug_id, hunk_i, hunk_j, lexical_distance, ast_distance, file_distance, pair_divergence` |

## Usage

```bash
# Requires: NLTK (punkt_tab), checked-out SWE-bench instances in ~/WORK_DIR

python hunk_divergence.py \
  --multihunk-json ../swe_bench_verified/multihunk_bugs_swe_bench_verified_32.json \
  --swe-bench-jsonl ../swe_bench_verified/swe_bench.jsonl \
  --work-dir ~/WORK_DIR \
  --out total_hunk_divergence_results.csv \
  --pair-out pairwise_hunk_divergence_results.csv
```

### Input Requirements

- **`--multihunk-json`**: JSON keyed by `instance_id`, each with a `buggy_hunks` dict mapping hunk index strings to `{file, start_line, end_line, code}`. Produced by `swe_bench_verified/analyze_multihunk.py`.
- **`--swe-bench-jsonl`**: SWE-bench JSONL with `instance_id`, `repo`, `base_commit`, and `patch` fields.
- **`--work-dir`**: Directory containing checked-out instances as `{instance_id}/{file_path}`. Source files are read from here for AST parsing.

### Dependencies

- Python 3.8+ (uses `ast` module with `end_lineno` support)
- NLTK (`pip install nltk`)

## Testing

The test suite validates mathematical properties of the divergence metrics (bounds, normalization, AST distance computation, etc.).

See **[README_TESTS.md](README_TESTS.md)** for:
- Test structure and coverage
- How to run tests
- Mathematical invariants validated
- Interpreting test failures

**Quick start**:
```bash
python -m pytest test_comprehensive_divergence.py -v
```
