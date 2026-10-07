# Public reproducibility acceptance

This task packages existing engines for discovery and a small executable
example. It does not change scientific algorithms or the live campaign.

| Requirement | Behavior to verify | Evidence |
|---|---|---|
| R1 | Five generated features produce all ten pairs, real nonlinear metrics, an alias and typed missing-support results in local DuckDB | `test_real_engines_and_local_warehouse` |
| R2 | Restart reuses terminals and rows without recomputation | `test_restart_reuses_terminals` |
| R3 | Changed configuration or input bytes cannot reuse the old experiment | `test_changed_inputs_and_config_refused` |
| R4 | An upstream revision different from the lock is refused | `test_wrong_revision_refused` |
| R5 | Documentation distinguishes synthetic phases 2/3 from causal phase 1, final selection and weekly model evaluation | README and `docs/PORTABILITY.md` |

Architecture: a bounded synthetic-data adapter builds the existing manifest;
the pinned predictor owns pairwise computation, ranking, persistence and
readback. One process and one numeric thread are used. The example owns a new
local directory and never discovers production stores, services or credentials.
The causal implementation is documented by source revision; the example does
not invent a causal phase-1 completion or causal-supported features.

Test design precedes adapter implementation. The output reports its synthetic
scope, configuration and input identities, upstream revision, seed, pairwise
and filter closures, local readback and `final_selection: false`.
