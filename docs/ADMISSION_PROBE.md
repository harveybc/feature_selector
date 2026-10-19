# Candidate Inventory Handoff Probe

This closes one absent integration: a runnable, deterministic check of the
existing financial-data inventory envelope before selector handoff. It does
not implement admission, select features or launch a campaign. No admitted
manifest format was found in the inspected curation implementation; inventing
one here would bypass the data owner's unfinished acceptance procedure.

## Contract And Boundaries

The input is the actual output of financial-data
`_scripts/required_variable_inventory.py`, schema
`financial_data.required_variable_inventory.candidate.v1`. Inspected owner
revision: `28134675583d026e4292257cd28161bf6b8b7c4a`. The governing requirements
are its `work_plan/17_CANONICAL_INVENTORY_AND_CURATION.md`, sections 2, 5 and 7,
and `configs/curation_policy.v1.json`.

The current predictor `FEATURE_SELECTION_METHOD_STATE.json` requires actual
admission and population rebuilding, superseding the old phase-2/3 plan's
withdrawn population counts. Its downstream priority is RL, not forecasting or
NEAT. This probe neither modifies predictor nor changes `upstream.lock.json`.

Validated fields: the schema, `CANDIDATE_NOT_ADMITTED` state, literal false
`admitted` and `selection_complete` flags, empty `hardcoded_population_sizes`,
nonempty variables, unique nonblank `variable_id`, the producer's three groups,
optional PRESENT/MISSING file status, and all six denominator counts.
Counts follow the producer's per-record semantics, not unique physical files.
Missing and uninspected records remain in the denominator. No population size
is hardcoded. Both individual chunks and the existing merged candidate can be
probed; chunk or merge labels are not completeness certificates.

The probe checks self-consistency, not completeness against an independent
configured population. It does not validate every semantic field required by
the work plan, individual-column expansion of catalog records, raw dependency
closure, per-month coverage, source hashes, availability, calendars, prepared
windows or data quality. Extra evidence fields remain uninterpreted. Even a
candidate with every file present is blocked. New/unknown schemas and relabeled
admission flags are refused; there is no inferred admitted schema.

## Run Once

Dependency: Python 3.12 on Linux, standard library only. Set
`FINANCIAL_DATA_ROOT` to the separate curation checkout, then run from this
repository:

```bash
CUDA_VISIBLE_DEVICES="" python scripts/inventory_probe.py \
  --inventory "$FINANCIAL_DATA_ROOT/deliverables/data_closure_20261018/REQUIRED_VARIABLE_INVENTORY.candidate.json"
```

For a newly generated candidate, pass its explicit file instead. Input is one
regular JSON file of at most 16 MiB; no directories are scanned. The probe
does not read paths listed in the inventory, import numeric/selection engines,
access a service or create files. It prints sorted JSON with the SHA-256 of
the inventory bytes actually read, counts and a typed reason, without echoing
source paths or variable identifiers. Duplicate JSON keys and nonfinite JSON
numbers are rejected. FIFOs are refused without waiting for a writer.

| Exit | State | Meaning |
|---|---|---|
| 2 | `BLOCKED_ADMISSION` | Valid candidate envelope; upstream admission interface still required |
| 1 | `INVALID_INVENTORY` | Invalid, unsupported, oversized or unreadable input |

There is deliberately no exit 0. Never reinterpret exit 2 as permission to
launch selection. `may_launch_selection`, `data_admission_complete`,
`selection_complete` and `source_bytes_verified` are always false. The output
schema describes a diagnostic only, not an input to the scientific engines.

## Next Dependencies

1. Financial-data must publish its actual versioned admitted-variable interface
   with immutable canonical file hashes, per-variable quality evidence and
   complete required-population/dependency accounting under section 5. A
   candidate or `QUALITY_PUBLISHED_NOT_ADMITTED` terminal cannot substitute.
2. The owning preparation code must rebuild the decision-time-aligned TRAIN
   exports from those admitted bytes, validate monthly/window support and
   retain availability, target, calendar and split contracts. No old affected
   metrics or prepared features may be reused.
3. Only then bind that interface to the existing phase-1 inventory orchestrator
   and genuine phase-1 closure, followed by `fs_phase23_manifest.build_manifest`
   and the existing pairwise campaign. Preserve a new immutable identity and
   the pinned-engine compatibility checks described in `PORTABILITY.md`.
4. Reuse phase-1 warehouse submission/reconciliation and phase-2/3 campaign
   terminal/outbox and warehouse readback. Require real closures and verified
   physical copies; do not publish this probe as a selection result. Static RL
   remains owned by the main RL workflow after its data/selection gates.

No automatic admitted-inventory consumer or publication wiring is claimed by
this change. Those need the missing owner interface above, not another selector.

## Verification

2026-10-18: 23 focused CPU checks passed, comprising 22 probe cases and the
existing synthetic adapter's wrong-revision refusal. Tests were written first:
19 setup errors and one CLI failure before implementation; after implementation
one directory-input failure was corrected before the final passing run.

```bash
CUDA_VISIBLE_DEVICES="" OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  python -m pytest -q tests/test_inventory_probe.py \
  tests/test_selection_demo.py::test_wrong_revision_refused
```

A one-shot read of the owner's existing merged candidate returned exit 2,
`BLOCKED_ADMISSION`: 394 records (370 catalog, 5 trading-required, 19 model
candidates), 337 marked present, 33 marked missing, 24 without file status.
Input SHA-256:
`58077e32e968346628a55e9528ce09841ce9f365760d68f953f8057803a91109`.
These are observed candidate counts, not admitted features or an independent
quality audit. No source data was opened, no engine/model was run and no OLAP
rows were written. The full synthetic engine integration suite was not rerun.
