# Reuse and extension audit

Audited on 2026-10-07 against [the pinned revisions](../upstream.lock.json).
The example executes the existing algorithms on generated data. This document
describes the additional contracts required for a real dataset.

## Ownership and extension points

| Component | Current interface | What is configurable | What needs implementation |
|---|---|---|---|
| Inventory scheduler | predictor `tools/phase1_inventory_orchestrator.py`, JSON config and `stdio-json-v1` | CSV inventory, feature ID field, population, hosts, command, retries, warehouse endpoints | Your reader/worker must implement the result envelope and availability policy |
| Numeric profiling | causal-inference `feature_selection_profile.profile_series(...)` | Series, timestamp column, fixed frequency, supported calendar | Other calendars or new metric families need code and tests |
| Causal ladder | causal-inference `feature-selection-column`, `feature_selection_unit.v1` | Column/resource definitions and declared studies within supported packs | The worker validates EURUSD/ETH packs; a new domain needs target, history, treatment and causal-model adapters |
| Pairwise metrics | predictor `feature_pairwise_worker.DEFAULT_PARAMS` and campaign `--param KEY=JSON` | Lags, support, MI bins, distance-correlation cap, tolerances and redundancy threshold | New estimators require metric slots, output identity and tests |
| Filter rankings | predictor `feature_filter_selection.METHOD_NAMES` | Population and target definitions; functions accept parameter dictionaries | The campaign fixes its nine methods, K grid and filter seed; these are not setuptools plugins |
| Extractibility | predictor FS4 campaign/worker plus feature-extractor artifacts | Versioned task plans, arms, folds and model settings | Another encoder requires compatible support/alignment and serialization tests |
| Predictive validation | predictor weekly campaign/wrapper | Trading plans and retained input bundles | A nontrading/static/retraining protocol needs its own validated evaluator |
| Analytical results | predictor `tools/fs_phase23_warehouse.py` | Local file or service URL; token environment name | New metric schemas/backend implementations need explicit migrations and readback parity |

The general predictor model plugin system does not automatically turn all these
selection components into plugins. `preprocessor` also has legacy feature
selector plugins; they do not implement this complete four-phase workflow.

## Input contract for a new population

1. Define the prediction target, horizon and decision time, including when the
   target becomes observable. For a hospital, machine or energy system, these
   definitions differ from a market's bar close.
2. Export numeric TRAIN features and targets separately, with exactly matching
   ordered row IDs and timestamps. Check this join before hashing. The current
   phase-3 loader reads both matrices positionally; a matching row count alone
   cannot prove alignment.
3. Record source, unit, transformation, earliest availability, calendar and
   coverage per feature. Do not backfill information that arrived later.
4. Create the real phase-1 profile/causal artifacts. Keep raw evidence and global
   multiple-testing correction. An unidentified causal effect remains unknown.
5. Build the phase-2/3 manifest with
   `tools.fs_phase23_manifest.build_manifest(...)` and `write_manifest(...)`.
   The synthetic adapter shows the API, but its `phase1: NOT_RUN` marker is
   strictly a demo marker and must not stand in for your completed study.

The builder's JSON-compatible keyword arguments are:

```json
{
  "population_id": "YOUR_POPULATION",
  "identity": "YOUR_IMMUTABLE_RUN_ID",
  "identity_source": {"file": "PHASE_1_COMPLETE.json", "field": "YOUR_IDENTITY_FIELD"},
  "phase1": {"plan_sha256": "YOUR_PHASE1_PLAN_SHA256"},
  "data": {
    "features_file": "features_train.parquet",
    "features_sha256": "SHA256_OF_ACTUAL_FEATURE_FILE",
    "targets_file": "targets_train.parquet",
    "targets_sha256": "SHA256_OF_ACTUAL_TARGET_FILE",
    "timestamp_column": "timestamp",
    "row_id_column": "row_id",
    "bar_hours": 1,
    "train_rows": 10000
  },
  "features": [{
    "feature_id": "sensor_temperature", "family": "sensor",
    "source": "YOUR_LAKE_RESOURCE", "transform": "identity", "unit": "degC",
    "clock": "OBSERVED", "availability_time": "timestamp",
    "support_h": 1, "train_coverage": 0.99, "source_bytes": 80000
  }],
  "targets": [{
    "target_id": "load_next_hour", "column": "load_next_hour",
    "family": "load", "head": "regression", "horizon_hours": 1
  }],
  "folds": [{"fold_id": "prefix_1", "train_rows": [0, 5000]}],
  "causal_supported": [],
  "contract_source": "YOUR_DATA_AND_TARGET_CONTRACT"
}
```

This is a field guide, not a runnable completed study. Supply all your features
(at least two for pair analysis), actual counts, hashes and truthful metadata.
Use real causal-supported feature/target/horizon triples only when supported by
the corrected phase-1 evidence. Empty means no supported triples were supplied,
not that no causal relationships exist.

After saving the filled dictionary as `population_inputs.json`, run from the
pinned predictor checkout:

```python
import json
from pathlib import Path
import pandas as pd
from tools.fs_phase23_manifest import build_manifest, sha256_file, write_manifest

root = Path("/your/exported/train")
spec = json.loads(Path("population_inputs.json").read_text())
keys = [spec["data"]["row_id_column"], spec["data"]["timestamp_column"]]
x_ids = pd.read_parquet(root / spec["data"]["features_file"], columns=keys)
y_ids = pd.read_parquet(root / spec["data"]["targets_file"], columns=keys)
if not x_ids.equals(y_ids) or x_ids.duplicated().any():
    raise ValueError("feature/target row identities do not match uniquely")
for kind in ("features", "targets"):
    actual = sha256_file(root / spec["data"][f"{kind}_file"])
    if actual != spec["data"][f"{kind}_sha256"]:
        raise ValueError(f"{kind} digest differs from your acquisition record")
write_manifest(build_manifest(**spec, data_root=root), Path("MANIFEST.json"))
```

Current limitations matter when adapting: the pairwise implementation uses
integer elapsed-hour lags and numeric columns, and its inner fold reader uses
prefixes `[0, end)`. Use zero fold starts here. Arbitrary rolling fold starts,
sub-hour horizons, categorical/text feature estimators and grouped-panel
semantics need adapters and validation; do not encode those as if they were
already supported. Expanding TRAIN profiles are distinct from weekly rolling
model training in phase 4.

## Run the existing engines

From the pinned predictor checkout in the numeric environment, replace the
three local paths below with your actual manifest, exported data and a new
state directory. No running service is needed for the local DuckDB path.

```bash
python -m tools.feature_pairwise_campaign plan \
  --manifest MANIFEST.json --state-root selection-run \
  --n-shards 8 --host local:small --param 'dcor_max_rows=1000'
python -m tools.feature_pairwise_campaign run-worker \
  --plan selection-run/PLAN.json --state-root selection-run \
  --data-root /your/exported/train --host-id local --threads 1
python -m tools.feature_pairwise_campaign follow \
  --plan selection-run/PLAN.json --state-root selection-run \
  --terminals selection-run/terminals --data-root /your/exported/train \
  --warehouse selection-run/metrics.duckdb --once --phase3-workers 1
python -m tools.feature_pairwise_campaign status \
  --plan selection-run/PLAN.json --state-root selection-run \
  --terminals selection-run/terminals --out selection-run/STATUS.json
```

Inspect the returned errors and require both closure records and warehouse
readback before declaring the filters complete. The follower can retain a
failed submission for retry rather than crash; process exit alone is not a
scientific closure. The demo adapter checks this explicitly.

For distributed execution, the same plan declares logical hosts and disjoint
shards, with exclusive claims and optional work stealing. Existing systemd
units and deployment scripts are under `tools/fs_phase23_deploy/`. Their
machine setup, SSH and credentials are deployment concerns. Inspect and bind
them to your own hosts instead of copying the research deployment literally.
Measure a small block first: each worker holds the feature matrix, and pair
counts grow as `p * (p - 1) / 2`. Two workers can duplicate that memory.

## Causal results and what they mean

The pinned implementation uses three distinct stages:

1. Conditional association with the future target, chronological out-of-fold
   diagnostics and population-wide multiple-testing correction.
2. Historical threshold-crossing episodes versus eligible control episodes,
   adjustment on pre-event history, declared causal graph/assumptions,
   overlap/balance, placebo and sensitivity checks, and effect estimators.
3. A fitted temporal structural causal model: infer an episode's disturbances,
   alter the treatment inside historical support, propagate the model, and
   compare reconstruction and historical analogs.

An analog is another observed episode; it is not the unobserved outcome of the
same episode. Counterfactual estimates depend on the fitted model and its
assumptions. Each rung records support, contradiction or `NOT_IDENTIFIED`.
The last state cannot eliminate a feature by itself. The current ranking
variants add declared causal support as a factor alongside predictive
relevance/redundancy; they do not certify universal absence of causality.

Source: [pinned causal ladder](https://github.com/harveybc/causal-inference/blob/08f44741d52a911e3855223f90c76021d5aefd88/provider/src/causal_inference_provider/fs_causal.py)
and [column worker](https://github.com/harveybc/causal-inference/blob/08f44741d52a911e3855223f90c76021d5aefd88/provider/src/causal_inference_provider/feature_selection_worker.py).

## Query and export the analytical results

All phase-2/3 result schemas live in
`olap/store/src/predictor_olap_store/fs_phase23_store.py`, including
`feature_pair_metrics`, `feature_pair_stability`, `feature_pair_gate`,
`feature_alias_groups`, `feature_redundancy_clusters`,
`feature_filter_rankings` and `feature_filter_subsets`. Inspect the schema
before writing downstream SQL. Keep metric name, state, method, parameters,
feature identities, target/horizon, fold, support and input/run digests.

```bash
python -m tools.fs_phase23_warehouse readback \
  --duckdb selection-run/metrics.duckdb --out selection-run/READBACK.json
```

The warehouse API uses the same storage implementation. Other lakes can export
the same admitted file contract; other analytical backends must implement
submit, readback and reconciliation with equivalent identity semantics. A new
metric needs a declared estimator/version, units, direction, population and
typed undefined states, plus a schema change where necessary. An arbitrary
JSON field does not automatically become a supported OLAP dimension.

## Follow-up packaging work

After the current feature-selection milestone, extract a stable Python API and
entry-point registry for profilers, causal studies, filters, evaluators and
storage adapters. Keep their scientific implementations in their owners and
require equivalence tests when moving them. Add a second real nonfinancial
domain and a fully pinned data-acquisition recipe before advertising one-command
cross-domain causal selection. This is planned work, not a feature of this
initial documentation release.
