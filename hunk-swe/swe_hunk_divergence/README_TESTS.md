# Hunk Divergence Test Suite

## Purpose

This test suite validates the mathematical properties of hunk divergence metrics as described in the ASE'25 paper "Characterizing Multi-Hunk Patches: Divergence, Proximity, and LLM Repair Challenges".

## Test Structure

### Test Classes (22 tests total)

1. **TestDirectoryDistanceBugs** (6 tests)
   - Validates D_dir ∈ [0, 1] for all file path combinations
   - Tests specific D_dir values for known path patterns
   - Validates boundary cases (no common path, same directory, nested paths)

2. **TestNormalizedDivergenceBugs** (3 tests)
   - Validates normalized divergence ∈ [0, 1]
   - Tests worst-case scenarios
   - Validates all pairwise combinations

3. **TestMetricBounds** (4 tests)
   - Validates D_lex ∈ [0, 1]
   - Validates D_ast ∈ [0, 1]
   - Validates D_dir ∈ [0, 1]
   - Tests cross-file AST distance = 1.0

4. **TestASTDistanceEdgeCases** (4 tests)
   - AST node distance for same node = 0
   - Tree diameter is positive
   - AST normalization stays within [0, 1]
   - Syntax error handling

5. **TestOverallDivergenceFormula** (3 tests)
   - Single hunk → divergence = 0
   - Divergence is non-negative
   - Logarithmic scaling with ln(n)

6. **TestPatchParsing** (2 tests)
   - Line number extraction from @@ headers
   - Buggy/fixed line separation

## Mathematical Invariants Tested

### Distance Metric Properties

All distance metrics must satisfy:
- **Non-negativity**: d(x, y) ≥ 0
- **Bounded**: d(x, y) ∈ [0, 1]
- **Identity**: d(x, x) = 0
- **Maximum distance**: d_max = 1.0

### Component Metrics

**D_lex** (Lexical Distance):
- Formula: `D_lex = 1 - BLEU(patch_i, patch_j)`
- Invariant: D_lex ∈ [0, 1]

**D_ast** (AST Distance):
- Formula: `D_ast = ln(1 + ASTDIST(n1,n2)) / ln(1 + TREEDIAMETER(T_f))`
- Same file: D_ast ∈ [0, 1]
- Cross-file: D_ast = 1.0

**D_dir** (Directory Distance):
- Formula: `D_dir = 1.0 - (common_segments / max_segments)`
- Same file: D_dir = 0
- Cross-file: D_dir ∈ [0, 1]

### Normalized Pair Divergence

Formula: `normalized = (D_lex × (D_ast + γ × D_dir)) / (1 + γ)`

Where (per Algorithm 1 of the paper):
- γ = 1 (same file — initial value, unchanged in the same-file branch)
- γ = 2 (cross-file — overwritten on Line 21)

**Invariants**: normalized ∈ [0, 1]; same-file pairs ≤ 0.5; cross-file pairs ≤ 1.0.

### Overall Divergence

Formula: `divergence = ln(n) × mean(normalized_pairs)`

Where n = number of hunks

**Invariants**:
- divergence ≥ 0
- Single hunk → divergence = 0
- Uses natural logarithm scaling

## Test Resources

The `resources/` directory contains synthetic AST-pattern fixtures and real SWE-bench Verified bug fixtures:

**Synthetic patterns:**
- `same_function.py` - Hunks in same function (D_ast ≈ 0)
- `sibling_methods.py` - Hunks in sibling methods (medium D_ast)
- `different_classes.py` - Hunks in different classes (larger D_ast)
- `complex_hierarchy.py` - Complex class hierarchy (large diameter)
- `syntax_error.py` - Error handling (diameter = 1, pairs = {})

**Real SWE-bench bug fixtures** (used by `test_comprehensive_divergence.py` to validate end-to-end behaviour against actual multi-hunk patches):
- `real_astropy_13033_core.py`
- `real_astropy_13579_sliced_wcs.py`
- `real_astropy_7606_core.py`
- `real_astropy_8707_card.py`, `real_astropy_8707_header.py` (cross-file pair, γ = 2)
- `real_django_10554_compiler.py`, `real_django_10554_query.py` (cross-file pair, γ = 2)

## How to Run

### Prerequisites

```bash
conda activate llm-code-repair-env
cd hunk-swe/swe_hunk_divergence
```

### Run All Tests

```bash
python -m pytest test_comprehensive_divergence.py -v
```

### Run Specific Test Class

```bash
# Directory distance tests
python -m pytest test_comprehensive_divergence.py::TestDirectoryDistanceBugs -v

# Normalized divergence tests
python -m pytest test_comprehensive_divergence.py::TestNormalizedDivergenceBugs -v

# Metric bounds tests
python -m pytest test_comprehensive_divergence.py::TestMetricBounds -v

# AST distance tests
python -m pytest test_comprehensive_divergence.py::TestASTDistanceEdgeCases -v
```

### Run Specific Test

```bash
python -m pytest test_comprehensive_divergence.py::TestDirectoryDistanceBugs::test_d_dir_must_not_exceed_one -v
```

### Show Test Output

```bash
python -m pytest test_comprehensive_divergence.py -v -s
```

## Interpreting Results

### Test Failures

When a test fails, examine:
1. **Assertion message** - shows expected vs actual value
2. **Test docstring** - explains what mathematical property is violated
3. **Stack trace** - shows where in the implementation the incorrect value originates

### Example Failure Analysis

```
FAILED test_d_dir_must_not_exceed_one
AssertionError: D_dir must be in [0,1], got 2.0
```

This indicates:
- The distance metric D_dir violated the bounded property
- D_dir = 2.0 exceeds the theoretical maximum of 1.0
- Investigation needed in directory distance computation logic

## Test Coverage

The test suite validates:

✓ **Metric bounds**: All metrics stay within [0, 1]
✓ **Specific values**: Known inputs produce expected outputs
✓ **Edge cases**: Syntax errors, empty files, single hunks
✓ **AST computation**: Node selection, distance, diameter
✓ **Patch parsing**: Line numbers, buggy/fixed separation
✓ **Formula correctness**: Logarithmic scaling, normalization

## Implementation Under Test

**File**: `hunk_divergence.py`

**Key Functions**:
- `compute_metrics_for_bug()` - Overall divergence computation
- `compute_ast_metrics_for_file()` - AST distance and diameter
- `_ast_node_distance()` - LCA-based node distance
- `_subtree_diameter()` - Maximum pairwise distance in tree
- `_buggy_subtree_root()` - Representative node selection
- `parse_patch_hunks()` - Unified diff parsing

## References

- **Paper**: https://nashid.github.io/resources/papers/hunk-divergence-ase25.pdf
- **Implementation**: `hunk_divergence.py`
- **Test suite**: `test_comprehensive_divergence.py`
