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

## Curation Admission Probe (2026-10-18)

Scope: validate the existing financial-data candidate inventory interface before
any selector handoff. No admitted schema or scientific engine is added. The
upstream admission contract is still missing; a structurally valid candidate
must block execution. Tests below precede implementation.

| Requirement | Behavior | Evidence |
|---|---|---|
| AP1 | Preserve all configured groups, missing files and dynamic counts; reject duplicates and denominator drift | `test_population_checks`, `test_population_not_hardcoded_and_missing_files_retained` |
| AP2 | Candidate, file presence and quality labels never authorize selection; reject forged admission and unknown schema | `test_actual_candidate_shape_is_valid_but_never_admitted`, `test_forged_admission_and_unknown_contracts_refused`, `test_observed_evidence_and_all_present_do_not_confer_admission` |
| AP3 | Bounded strict JSON input, byte identity, deterministic read-only CLI; nonzero exit prevents automatic chaining | `test_bad_json_refused`, `test_size_bound_and_unreadable_input`, `test_changed_bytes_change_identity`, `test_cli_is_deterministic_read_only_and_blocks_chaining` |

Architecture: one standard-library probe reads one explicitly supplied inventory,
validates only the documented candidate envelope and population accounting, and
prints a path-free diagnostic. It never opens listed datasets or imports the
selector. Owner dependencies and execution commands: `docs/ADMISSION_PROBE.md`.

## Rebuild Adapter (2026-10-18)

User-authorized extension: execute a verified TRAIN handoff through pinned
PROFILE_ONLY phase 1, then phases 2/3, with sequential local CPU dispatch and
existing durable receipts/outboxes. It is not source admission or causal closure.
Tests are defined before implementation in `tests/test_selection_rebuild.py`.

| Requirement | Acceptance |
|---|---|
| RB1 | Owner schemas render from exact dynamic variables and pinned input/config/code identities; changed identities cannot resume |
| RB2 | Hash, availability, unique aligned rows, monthly TRAIN coverage and variable membership fail before dispatch |
| RB3 | Actual profiler, pairwise and nine filter engines publish into existing DuckDB tables and close automatically |
| RB4 | Publication failure prevents successors; rerun retains science and retries publication; status is read-only |
| RB5 | Hourly-elapsed finite targets cannot reach/cross global TRAIN or containing prefix-fold cutoffs; masks are materialized before hashing, not silently changed by execution |

RB1: `test_render_uses_owner_schemas_and_dynamic_denominator`; RB2:
`test_contract_refuses_bad_handoff_before_any_work`; RB3:
`test_real_profile_pairwise_filter_passage_and_restart`; RB4: restart/status
assertions in RB3 plus `test_publication_failure_stops_successor_and_resumes_without_refitting`.
RB5: `test_future_labels_refused_before_render`,
`test_declared_boundary_masks_are_preserved_not_rewritten`. RB3 also mutates
retained metric values without changing digest labels and requires readback refusal.
The source-admission attestation is an external trust boundary, not an authenticated
owner receipt verifier. Executable contract and commands: `docs/REBUILD_HANDOFF.md`.

Test design precedes adapter implementation. The output reports its synthetic
scope, configuration and input identities, upstream revision, seed, pairwise
and filter closures, local readback and `final_selection: false`.
