# Runnable CPU Rebuild Handoff

This adapter actually executes the existing engines. It takes a prepared TRAIN
bundle, renders upstream configs, dispatches phase-1 PROFILE_ONLY work, verifies
publication, then automatically runs phase 2 and phase 3. It stops at candidate
filters, not final feature selection or RL readiness. It never trains a
predictor, causal model, encoder or policy.

## What Runs

| Step | Existing implementation called |
|---|---|
| Phase-1 planning and sequential dispatch | predictor `phase1_inventory_orchestrator.load_config`, `build_plan`, `run_host_once` |
| Actual individual and feature-target metrics | causal-inference `feature_selection_worker --stdio`, mode `PROFILE_ONLY`; its existing `profile_series` and envelope builders |
| Population merge | causal-inference `merge_profile_terminals`; adapter translates its verified `PROFILE_METRICS_COMPLETE` result into the orchestrator lifecycle finalizer envelope, retaining `mode: PROFILE_ONLY` |
| Phase-1 publication and gate | `PredictorDuckdbStore.write_feature_selection_envelope`, `reconcile_feature_selection`, orchestrator `finalize_if_ready` and `require_phase1_complete` |
| Manifest and pairs | predictor `fs_phase23_manifest.build_manifest`, `feature_pairwise_campaign.plan` and `run_worker` |
| Automatic phase-2/3 publication and closure | predictor `feature_pairwise_campaign.follow_once`, using `fs_phase23_warehouse.Warehouse`; its existing pairwise and nine filter methods |

Phase 1 requires small/large logical host classes; both execute sequentially in
one local process. Numeric threads are one and GPUs are hidden. No SSH, DOIN,
service, timer, watcher or external agent is started. Worker attempts and
timeouts are bounded by config. Each invocation processes its finite task
population, attempts closure once, and exits. It does not wait for admission or
poll for upstream files.

The default publication target is two new local DuckDB files in the run output,
using the existing production table/receipt implementations. Existing worker
outboxes, orchestrator publication-failure records and pairwise terminals are
retained. There is **no remote HTTP publication switch in this bounded adapter**;
no live OLAP service or physical second-host copy was touched. Wiring the
existing HTTP submit/reconcile adapters and verifying remote copies remains
deployment work, not a claimed acceptance result.

## Run And Resume

Use separate clean checkouts at `upstream.lock.json` revisions, unchanged:
predictor `25fcfe1c045dbd3449b8f65d695788bf049c8f90`, causal-inference
`08f44741d52a911e3855223f90c76021d5aefd88`. Predictor needs `tools`, `olap`,
`fs_phase23`; causal-inference needs `provider`. Both are imported by source path
and checked for the correct commit and unmodified engine files.

Python 3.12 and the observed direct dependencies are listed in
`examples/rebuild-requirements.txt`. Use an isolated environment; the verification
environment inherited existing scientific packages and added DuckDB packages,
so a completely fresh dependency installation has not been exercised. Actual
numeric versions and Python version enter the immutable run binding.

Working commands in this sidecar, using its ignored pinned runtime checkouts:

```bash
.venv/bin/python scripts/selection_rebuild.py demo \
  --predictor-root output/predictor-runtime --causal-root output/causal-runtime \
  --output output/verified-rebuild-20261018

.venv/bin/python scripts/selection_rebuild.py status \
  --predictor-root output/predictor-runtime --causal-root output/causal-runtime \
  --output output/verified-rebuild-20261018/run
```

`demo` generates the existing five-variable, fixed-seed sensor fixture, adds
explicit availability and target-boundary masks **before hashing**, and runs
all three engine stages. It never emits an ADMITTED fixture. Repeat the same
command to resume and verify readback without recomputing accepted work.

For a real, owner-approved prepared bundle, use its explicit handoff path:

```bash
.venv/bin/python scripts/selection_rebuild.py render \
  --predictor-root "$PREDICTOR_ROOT" --causal-root "$CAUSAL_ROOT" \
  --input "$BUNDLE_ROOT/REBUILD_INPUT.json" \
  --config "$REBUILD_CONFIG" --output "$SELECTION_RUN"

.venv/bin/python scripts/selection_rebuild.py run \
  --predictor-root "$PREDICTOR_ROOT" --causal-root "$CAUSAL_ROOT" \
  --input "$BUNDLE_ROOT/REBUILD_INPUT.json" \
  --config "$REBUILD_CONFIG" --output "$SELECTION_RUN"
```

`render` performs checks and writes configs only. `run` revalidates, locks its
output, dispatches, publishes and advances automatically. Exit 0 from `run`
means `PROFILE_FILTERS_COMPLETE` with both local readbacks, not final selection;
exit 2 means an unfinished stage with retained work; exit 1 means a refusal or
execution error. Publication retries use retained science on the next identical
invocation. Changed manifest bytes, config, adapter code, Python or numeric
versions require a new output directory. Status is a read-only snapshot, not a
fresh warehouse audit; `run` performs the warehouse readback again.

The example config's ETH target-pack ID is an upstream interface discriminator:
the PROFILE_ONLY worker accepts only ETH/EURUSD IDs even for its generic numeric
profiler. The demo population and target remain synthetic sensor data. For a
financial handoff choose the actual configured pack and a reviewed calendar;
the default 24x7 sensor config is **not an FX calendar approval**. `weekday_24h`
and `observed_only` are upstream diagnostic modes, not certified sessions.

## Minimal Selector Contract

`feature_selector.rebuild_input.v1` is a **selector-owned adapter contract**,
not a financial-data admission schema. `ADMITTED` plus evidence hashes is a
trusted operator/owner attestation. The adapter does not authenticate its issuer,
interpret an authoritative admission receipt, or establish source quality.
Arbitrary evidence bytes with a matching hash do not prove admission. Both
`source_admission_verified` and `source_admission_issued` remain false in the
run report. The main workflow must verify source admission before supplying a
production handoff. No current financial input has been declared eligible.

The complete generated example is
`output/verified-rebuild-20261018/fixture/bundle/REBUILD_INPUT.json`. All files
are direct members of its directory; absolute names, traversal and escaping
symlinks are refused. Fields are:

| Field | Required meaning |
|---|---|
| `schema`, `scope` | `feature_selector.rebuild_input.v1`; `ADMITTED_TRAIN` or `SYNTHETIC` |
| `created_at` | Fixed campaign timestamp passed unchanged to upstream workers |
| `target_clock` | Exactly `HOURLY_ELAPSED`: label endpoint and assumed label availability are UTC decision time plus horizon hours, not business/market time |
| `train_period` | UTC start-inclusive/end-exclusive interval |
| `expected_monthly_rows` | Independent prepared decision-grid denominator for every month in that interval; positive integer counts must exactly match actual rows |
| `admission` | `disposition: ADMITTED`, `authority: financial-data`, exact feature `variable_ids`, and nonempty `evidence` list of `{file, sha256}` supplied after external approval. Synthetic uses `SYNTHETIC_NOT_ADMITTED`, never `ADMITTED` |
| `availability` | `{file, sha256}` for aligned per-feature UTC availability Parquet |
| `population` | Existing manifest builder arguments: `population_id`, `data`, `features`, `targets`, `folds`, `contract_source`, as documented in `PORTABILITY.md` |

The adapter creates new `identity`, `identity_source`, `phase1` and empty
`causal_supported`; supplying those fields from old results is refused.
`data` uses existing `features_file`, `features_sha256`, `targets_file`,
`targets_sha256`, `row_id_column`, `timestamp_column`, `train_rows`, `bar_hours`.
Only `bar_hours: 1` and prefix folds `[0, stop)` are supported.

Feature and availability columns must be exactly `[row_id, timestamp, feature
IDs in declared order]`. Target columns must be exactly `[row_id, timestamp,
declared target columns]`. Keys must match in ordered rows across all three
files; row IDs and UTC decision timestamps must be nonnull and individually
unique, and times strictly increasing. Membership, byte hashes, bounded Parquet
dimensions, numeric columns, coverage fractions and all monthly counts are
checked. For each feature, existing metadata is required and
`availability_time` names its matching availability column. Every availability
value must be nonnull UTC and no later than the row's decision time.

For each target, a finite label is forbidden when `t + horizon >= TRAIN end`.
Within each prefix fold it is also forbidden when `t + horizon >= fold cutoff`.
The fold cutoff is the first excluded decision timestamp (`timestamp[stop]`),
or the global TRAIN end if `stop == train_rows`. Equality is rejected. Producers
must materialize missing labels at **all** these boundaries before hashing; the
same matrix is consumed by the existing engines, so those masks also remain in
the full TRAIN view. The runner never fills, masks or rewrites labels. Targets
with delayed publication, market-time maturity or richer endpoint semantics
need another reviewed contract and are not supported by this one.

These checks do not certify native monthly source completeness, source clock
correctness, raw lineage, calendar validity, actual label availability, or
point-in-time correctness of derived features. That remains data-owner and
preparation acceptance. They detect consistency violations in the declared
handoff, including target leakage at its global and fold boundaries.

## Retained Evidence

`BINDING.json`, `INVENTORY.csv`, `DEPLOYMENT.json`, `PHASE1_CONFIG.json` and
`INPUT.json` identify the run. Phase-1 workers retain their outbox/evidence;
the orchestrator retains attempts, terminals, receipts, reconciliation and
`PHASE_1_COMPLETE.json`. This gate closes the PROFILE_ONLY lifecycle, not a
causal study. `MANIFEST.json` binds that gate to the new pairwise population.
`phase23/` contains both closures and `CANDIDATES_FOR_VALIDATION.json`.
`REPORT.json` retains local readback counts/digests; `STATUS.json` records stage
transitions and the latest existing engine snapshot.

No affected old selection, adopted causal result, learned representation or
financial input is used. Causal-supported is empty (unknown, not causal absence).
Policy usefulness, predictive validation, final subset choice and static RL
remain outside this profile/filter passage and belong to the main workflow.

## Verification Record

2026-10-18, Python 3.12, pinned owner revisions above. Initial rebuild tests
failed because the adapter did not exist. The added target-boundary tests
initially failed because validation accepted future labels; the corrected
contract rejects global/fold equality and crossing, and rejects market-time
semantics. The full sidecar suite includes the old synthetic engine tests and
the candidate probe tests, not only mocks of the new adapter.
Final verification: **42 passed in 23.92 seconds**.

```bash
CUDA_VISIBLE_DEVICES="" OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
SELECTION_PREDICTOR_ROOT=output/predictor-runtime \
SELECTION_CAUSAL_ROOT=output/causal-runtime \
  .venv/bin/python -m pytest -q tests
```

Independent CLI result: `PROFILE_FILTERS_COMPLETE`, five completed profile
terminals, all ten unique pairs, both phase-2/3 closures and nine filter methods.
Merged phase-1 readback: 65 sampling-quality, 444 variable-profile, 34
information-metric and 20 feature-target relation rows; zero causal/selection
decision rows. Phase-2/3 readback: 540 pair metrics, 180 stability, ten gates,
one alias group, four redundancy clusters, 34 rankings and nine subsets.
These counts describe synthetic evidence, not selected financial variables.
An identical CLI restart computed zero shards and submitted zero new pairwise
payloads, with identical readback counts/digests. The read-only status command
reported five completed profiles, no failures and complete phases 2 and 3.

The worker reported peak RSS 1,183,002,624 bytes for this process, which includes
the preceding phase-1 publisher imports/work; this is not a per-pair estimate
or an enforced process memory cap. Do not extrapolate to a real population
without separate memory/disk admission. Numeric threads and table dimensions
are bounded, but no production host resource reservation is implemented here.
