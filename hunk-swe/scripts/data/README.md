# Figure Data — Hunk-SWE

Raw per-instance data underlying the SWE-bench figures in the thesis.
Each file covers all 32 Hunk-SWE instances and uses the same
`is_resolved` source-of-truth as the headline accuracy tables (the
official SWE-bench harness `report.json` verdict).

## Files

### `overlap_data.json`

Underlying data for the UpSet plot of resolved-set overlap across the
four coding agents (Fig. 3.2).

Schema (list of 32 objects):

```json
{
  "instance_id": "astropy__astropy-13033",
  "resolved_by": {
    "qwen":   true,
    "gemini": true,
    "codex":  true,
    "claude": true
  }
}
```

To reproduce the plot, enumerate the non-empty exact-membership
intersections across the four boolean columns of `resolved_by`.

### `divergence_data.json`

Underlying data for the faceted violin plot of hunk divergence by
agent and harness outcome (Fig. 3.3).

Schema (list of 32 objects):

```json
{
  "instance_id": "astropy__astropy-13033",
  "hunk_count":  2,
  "divergence":  0.122,
  "resolved_by": {
    "qwen":   true,
    "gemini": true,
    "codex":  true,
    "claude": true
  }
}
```

To reproduce the plot, for each agent split the 32 `divergence`
values into Pass / Fail subsets according to that agent's
`resolved_by` flag and draw the two distributions side by side.

## Provenance

Both files are produced from the same primitives that drive the
thesis's headline tables:

- `is_resolved` ← official SWE-bench harness `report.json` verdict
- `hunk_count`, `divergence` ← `hunk-swe/swe_hunk_divergence/total_hunk_divergence_results.csv`

If the underlying CSV / harness output changes, regenerate these
JSONs to keep the figure data in sync.
