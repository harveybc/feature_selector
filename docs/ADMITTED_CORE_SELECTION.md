# Admitted EURUSD Core: Recomputed Filter Selection

2026-10-19: scoped selection on repaired, admitted EURUSD prices completed.
This does not restore retired rankings or claim that the external catalogue
has been admitted. It is a first genuinely selected input for the RL contrast,
not a replacement name for the eight-variable RAW control.

## Population And Procedure

financial-data's `core_selection_bundle` verifies actual admission/source and
closure hashes, then calls the existing feature-eng technical generator at
`d081d0f743218153f42fe461c41ccdea6e9dd310`. Eight deterministic RAW candidates
and22 existing technical/seasonal candidates form the30-variable population.
Only33 leading indicator-warmup observations are removed. No interpolation,
centered decomposition, smoothing/downsampling of prices, missing-weekend rows
or interior-row deletion is used. The prepared input has24862 TRAIN rows
over all48 months2020-2023 and6221 VALIDATION rows over12 months2024.

The independent transport attestation recomputes the source/recipe and checks
the entire prepared frame exactly before hashing TRAIN/VALIDATION transport.
This is distinct from merely recording a delivered file's hash.

The existing pinned engines compute individual metrics, all435 unordered
pairs over prefix TRAIN folds, and nine filters. Relevance targets are exact
elapsed4h/12h returns and absolute12h return as a risk proxy, not executable
strategy rewards. Labels use exact observed endpoints,12h operating buffers,
closure-crossing exclusion and TRAIN/fold-boundary purges. Validation values
are not used in selection.

Prospective filter recipe: union the mRMR k12 sets for those three targets,
then retain one representative per existing TRAIN Spearman redundancy cluster.
The redundancy rule is the engine's average-linkage, absolute Spearman0.9 cut.
This is a filtered experimental subset, not an optimized trading subset.
Different target sets can select different representatives; the final union
is therefore pruned again. A nonselected variable is not proven useless.

## Selected Inputs

`HIGH`, `RAW_LOG_RANGE`, `RAW_CLOSE_LOG_RETURN`, `RAW_ELAPSED_HOURS`, `ATR`,
`RSI`, `MACD_Histogram`, `ADX`, `DI_minus`, `Stochastic_D`, `WilliamsR`,
`rolling_std_24`, `hod_sin`, `hod_cos`, `dow_cos`.

Both RL arms must use these same15 ordered variables and identical causal
normalization; account/business context is common to both. Only the observation
representation differs: direct versus per-feature Conv1D, fusion and core.
No retired pretrained encoder weights are consumed.

## Evidence And Limits

Native warehouse exact readback:390 sampling-quality rows,2846 profiles,
630 information metrics,540 feature-target relations,23490 pair metrics,
7830 stability rows,435 pair gates,20 redundancy clusters,804 ranking rows,
123 subset rows and90 explicit selection decisions:37198 rows total.
No pending or mismatched rows.39 source/config/proof/analytical files are
hash-verified on both physical copies; metric databases are not put in Git.

Selection identity:
`553fc04707ee3d1d2d552a21af073bf942e3a1b880150f2b34245764446c09e2`.
Close state: `FILTER_SELECTION_OLAP_AND_TWO_PHYSICAL_COPIES_VERIFIED`.

`full_inventory_complete:false` and `causal_evidence_computed:false` are
intentional, mandatory fields. Profiles and dependency filters cannot identify
intervention/counterfactual effects without an identification design. Unknown
causal support does not reject a feature. The full external-source selection
and RL policy-value validation remain distinct unfinished work. TEST is not
used by this experiment. Neither this result nor a test count certifies profit.

Verification:55 selector tests pass, including changed-byte snapshots, live-WAL
refusal, malformed subsets, keyset readback pagination and stored-value tampering.
financial-data preparation has six focused tests and real exact-prefix checks
at512 and4096 observed rows. Full repository/literature reproduction is not
implied. The bounded source receipt uses its declared fixed closure filename;
generalizing that owner interface is separate from this accepted population.

## Reproduce And Monitor

First use financial-data's documented admitted-price recovery and preparation,
then its `attest_core_candidate_transport` command. Configure paths below to
that new immutable bundle and pinned upstream checkouts; no market data ships
in this repository. The existing `selection_rebuild.py render` is a no-dispatch
preflight. The finite high-level command continues all remaining stages:

```bash
CUDA_VISIBLE_DEVICES='' .venv/bin/python scripts/complete_core_selection.py complete \
  --predictor-root "$PREDICTOR_ROOT" --causal-root "$CAUSAL_ROOT" \
  --bundle "$PREPARED_BUNDLE" --run "$SELECTION_RUN" \
  --selected "$SELECTED_BUNDLE" --snapshot "$PHYSICAL_SNAPSHOT" \
  --warehouse-url "$WAREHOUSE_URL" --token-env DATA_GOV_LAKE_TOKEN \
  --mirror-host '<second-host>' --mirror-root '<absolute-snapshot-path>'

.venv/bin/python scripts/complete_core_selection.py status --selected "$SELECTED_BUNDLE"
.venv/bin/python scripts/complete_core_selection.py verify --snapshot "$PHYSICAL_SNAPSHOT"
```

The completed operation emits `DEPLOYMENT_RECEIPT.json`, pinned to `CLOSE.json`;
the RL consumer refuses an unpublished or unmirrored merely sealed selection.
Two additional deployment metadata files are copied and checked separately
from the39 scientific/input/database files in the frozen snapshot index.

To query this selected subset without mixing earlier engineering seals, filter
the native decision table by the exact active identity:

```sql
SELECT DISTINCT feature_id
FROM df_fact_feature_selection_decision
WHERE run_id = 'selected-core:553fc04707ee3d1d2d552a21af073bf942e3a1b880150f2b34245764446c09e2'
  AND decision = 'SELECTED'
ORDER BY feature_id;
```

Use a private EnvironmentFile/service for credentials, never command arguments
or a public JSON. The operation is finite and resumable, has no agent/log-watch
loop, and cannot close before native readback and the second hash verification.
The frozen export is small (about100MB including prepared inputs), distinct
from a live warehouse backup. Keep live DuckDB writers closed before copying.
Run the producer in a bounded CPU service; the scientific engines hide GPUs.
