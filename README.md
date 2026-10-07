# feature_selection

Time-series feature selection with retained evidence: individual profiles,
causal diagnostics, pairwise dependence, candidate rankings and predictive
validation. Start with the small CPU example, then adapt the input contracts
to your data and evaluation schedule.

This repository is the public entry point to the existing selection engines.
It contains instructions, JSON examples and an executable adapter, while the
scientific implementations remain in their owning repositories. Versions are
pinned in [upstream.lock.json](upstream.lock.json); no market datasets, trained
weights or large analytical databases are bundled here.

## What is available

| Phase | Purpose | Implementation and reuse status |
|---|---|---|
| 1: individual evidence | Missing observations, outliers, stationarity, temporal/spectral profiles and target-specific causal evidence | Generic numeric profiler; causal worker currently supports the EURUSD and ETH target packs. A new causal domain needs an explicit adapter. |
| 2: relationships | Aliases, linear/nonlinear dependence, lagged relationships and redundancy clusters | Manifest-configured numeric time series; executable in the local example below. |
| 3: candidate subsets | Clustering, mRMR, JMI, causal variants and controls across subset sizes | Nine built-in methods; candidate sets await predictive validation. |
| 4: predictive selection | Raw/random/trained encoders and paired validation of candidate sets | Existing campaign in predictor, with trading-specific weekly evaluation. General domain validation remains an integration task. |

The ongoing trading campaign has closed phases 1-3 for its declared populations.
Phase 4 and its final selected-feature manifest are still in progress as of
2026-10-07. Those results do not establish performance in another domain.

## Quickstart: local CPU example

Requirements: Linux, Git, Python 3.12 and about 1 GiB of available RAM for this
small example. Installation needs Internet access; running the example does
not use a feed, GPU, API key or remote warehouse.

```bash
git clone https://github.com/harveybc/dataset_selection.git
cd dataset_selection
git init ../predictor-selection-runtime
git -C ../predictor-selection-runtime remote add origin https://github.com/harveybc/predictor.git
git -C ../predictor-selection-runtime fetch --depth 1 --filter=blob:none origin 25fcfe1c045dbd3449b8f65d695788bf049c8f90
git -C ../predictor-selection-runtime sparse-checkout set tools olap fs_phase23
git -C ../predictor-selection-runtime checkout --detach FETCH_HEAD
python3.12 -m venv .venv
source .venv/bin/activate
cd ../predictor-selection-runtime
python -m pip install -r tools/fs_phase23_deploy/requirements.lock
cd ../dataset_selection
python scripts/selection_demo.py run \
  --predictor-root ../predictor-selection-runtime \
  --config examples/synthetic.json --output output/sensor
```

The fixed-seed sensor example generates five features and one future target,
computes all ten feature pairs, builds nine methods' candidate subsets and
verifies the saved metrics by reading them back from `output/sensor/metrics.duckdb`.
It includes a duplicate, a nonlinear transform, noise and insufficient support.
Its causal-supported set is empty: no phase-1 causal result is fabricated for
the demo. Success prints `DEMO_FILTERS_COMPLETE`, with `final_selection: false`.

Run the same command to resume. Accepted pairwise terminals are reused. Changed
configuration requires a new output directory; changed input bytes are rejected.
Inspect progress at any time:

```bash
python scripts/selection_demo.py status \
  --predictor-root ../predictor-selection-runtime --output output/sensor
```

The JSON status includes work counts and the engine's measured ETA when enough
tasks have completed. Short examples may finish before an ETA is useful.

| Output | Meaning |
|---|---|
| `MANIFEST.json`, `PREPARED.json` | Feature/target definitions, seed, configuration and input hashes |
| `campaign/terminals/` | Retained pairwise results, including unavailable metrics |
| `campaign/PHASE2_MATRICES.npz` | Matrices used by the filter methods |
| `campaign/PHASE_2_COMPLETE.json` | Complete pairwise population plus local warehouse readback |
| `campaign/CANDIDATES_FOR_VALIDATION.json` | Candidate subsets, with no predictive winner |
| `campaign/PHASE_3_FILTER_COMPLETE.json` | Ranking coverage and local warehouse readback |
| `metrics.duckdb`, `REPORT.json`, `STATUS.json` | Local analytical file, scoped result and status generated on request |

Verification: four acceptance tests passed using the pinned engines and numeric
stack in an existing Python 3.12 environment. A fresh dependency installation
was not measured in this audit. See [verification](docs/VERIFICATION.md).

```bash
SELECTION_PREDICTOR_ROOT=../predictor-selection-runtime python -m pytest -q tests
```

## Use your own data

Follow [the portability guide](docs/PORTABILITY.md) for the exact interfaces and
limits. Export your lake's admitted TRAIN data to two aligned Parquet files:
features and targets, with identical ordered row IDs and UTC decision times.
Record when each input was actually available, its units, transformations,
missingness and source identity. Define the target, its horizon and the intended
retraining schedule before ranking features.

The phase-2/3 manifest supports other population names and feature columns;
hour-based lags and prefix TRAIN folds are assumptions of the current engine.
The example generator is synthetic-only. For real data, use the existing
manifest builder and the CLI sequence in the portability guide. Phase-1
provenance must come from your actual profiles and causal study.

JSON configuration is available at several layers. The complete workflow is
**not yet a single installable feature-selection plugin package**: phase-1
workers use a JSON subprocess protocol, pairwise parameters use manifests,
filter methods are an explicit built-in list, and warehouse schemas are typed.
Adding a new estimator currently requires code and tests in its owner; changing
a JSON name alone cannot install a new method. The guide lists each extension
point and the remaining packaging work.

## Our trading example

EURUSD has 366 candidates, ETH 83, with separate targets and denominators.
The frozen manifests and source identifiers are linked in
[data sources and reproduction](docs/DATA_SOURCES.md). Data is acquired with
your own provider access and stored outside Git. Re-downloading a revisable
dataset can produce different bytes; reproducing an old number requires the
matching vintage, preprocessing and input digests.

Our business evaluation retrains before each validation week using the declared
preceding training window. Static literature comparisons retain the original
paper's protocol. Changing retraining frequency, target or market creates a
different experiment that needs its own configuration and validation.

## Results and storage

Individual metrics, causal evidence, pairwise results and ranking records have
versioned schemas in the existing warehouse. Local DuckDB and the warehouse
HTTP adapter share the phase-2/3 storage implementation. A service URL requires
your service deployment and token from its configured environment variable.

Keep a physical analytical snapshot and a second verified copy. Commit the
code, effective configs, manifests, checksums and regeneration instructions;
keep large database files, private data and credentials outside Git. Backups
must be made after writers close/checkpoint the database, not by copying a live
file while it is being changed.

## Run with your AI agent

> Read this README, upstream.lock.json and docs/PORTABILITY.md. Run the pinned
> synthetic example in a new directory. Verify both closures, the candidate
> file, local warehouse readback and restart reuse. Report the exact outputs,
> unsupported domain requirements and failed checks. For my own data, first
> define targets, timestamps, availability, TRAIN boundaries and validation
> schedule; use the source adapters and existing engines. Keep failures and
> NOT_IDENTIFIED explicit. Use batch scripts and status commands rather than
> continuous log polling. Do not call a ranking a final selection.

## Components

- [predictor](https://github.com/harveybc/predictor): campaign drivers, pairwise/ranking engines and weekly validation.
- [causal-inference](https://github.com/harveybc/causal-inference): column profiling, causal studies and complete-population correction.
- [feature-eng](https://github.com/harveybc/feature-eng): engineered inputs and target construction.
- [feature-extractor](https://github.com/harveybc/feature-extractor): learned representations.
- [preprocessor](https://github.com/harveybc/preprocessor): independent preprocessing and legacy feature-selector plugins.
- [financial-data](https://github.com/harveybc/financial-data), [data-lake](https://github.com/harveybc/data-lake), [data-gov](https://github.com/harveybc/data-gov): source metadata, storage and governed access.
- [data-warehouse](https://github.com/harveybc/data-warehouse): analytical integration; the pinned phase-2/3 DuckDB schema currently lives in predictor's `olap/store` package.

## License

The new documentation and adapter in this repository use the MIT license.
External engines and datasets retain their own licenses and access conditions.
