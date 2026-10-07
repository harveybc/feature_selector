# Verification record

2026-10-07, Linux, Python 3.12, predictor
`25fcfe1c045dbd3449b8f65d695788bf049c8f90`.

Numeric packages observed: numpy 2.4.3, pandas 3.0.1, scipy 1.17.1,
scikit-learn 1.8.0, pyarrow 23.0.1 and duckdb 1.5.6. The existing environment
matches the pinned numeric versions. Fresh installation was not remeasured.
The adapter forces source imports for the pinned warehouse and refuses an
unexpected engine revision or modified engine files.

## Acceptance

- Before the adapter existed: three setup errors and one failed test, all due
  to the absent `scripts/selection_demo.py`.
- Initial implementation: three passed, one failed. Re-closing the same phase
  could emit identical receipt identities inside the same timestamp resolution.
- Correction: restart adopts existing closures and verifies stored row counts
  and digests, without re-emitting closure receipts.
- Four acceptance tests passed in 4.41 seconds under a 1 GiB / 120 s process
  scope. This is the small synthetic example, not a memory bound for real data.
- The documented sparse checkout was then fetched from GitHub at the pinned
  revision. All four tests passed against that clean checkout in 4.53 seconds,
  including nonlinear dependence and the duplicate-feature assertion.

The CLI was also executed independently. Observed local readback:

| Table | Rows |
|---|---:|
| feature_pair_metrics | 360 |
| feature_pair_stability | 120 |
| feature_pair_gate | 10 |
| feature_alias_groups | 1 |
| feature_redundancy_clusters | 4 |
| feature_filter_rankings | 36 |
| feature_filter_subsets | 9 |

Pairwise worker time: 1.18 s; worker-reported peak RSS: 188,895,232 bytes.
These are worker measurements, not end-to-end runtime or cgroup peak. Both
phases closed against the local analytical file. `final_selection` and
`causal_evidence_computed` are false. No model was trained.

Small retained artifacts: [demo report](evidence/DEMO_REPORT.json) and
[demo manifest](evidence/DEMO_MANIFEST.json). The generated Parquet files and
DuckDB database stay outside Git. The separate `status` CLI returned
`PHASE_3_COMPLETE`, both shards complete, one target complete, zero failed and
ETA zero. These are synthetic-example counts.

## Audit limits and follow-up

The upstream receipt collision on repeated writes remains an upstream issue;
this adapter's restart path uses readback rather than unnecessary writes.
The initial public example demonstrates phases 2/3 only. The full causal
worker is limited to its declared target packs; no universal plugin loader or
complete acquisition recipe for all financial inputs is claimed.

Live jobs, trained-model artifacts and production warehouses were not modified
by these tests. This documentation does not replace the current research plan
or declare the live feature-selection campaign complete.
