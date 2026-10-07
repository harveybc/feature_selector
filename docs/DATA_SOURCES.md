# Data sources and reproduction

The public demo generates its inputs from the seed in `examples/synthetic.json`.
It needs no downloaded data. Real research inputs belong in your own lake or
local storage. This repository publishes the method and identities, not bulk
market data or analytical snapshots.

## Retained campaign contracts

The exact candidate lists, transformations, source identifiers, target horizons,
folds and TRAIN file hashes are in predictor at the pinned revision:

- [EURUSD manifest](https://github.com/harveybc/predictor/blob/25fcfe1c045dbd3449b8f65d695788bf049c8f90/fs_phase23/manifest/EURUSD_MANIFEST.json): 366 candidates, 14 targets, five TRAIN folds, 66,795 feature pairs.
- [ETH manifest](https://github.com/harveybc/predictor/blob/25fcfe1c045dbd3449b8f65d695788bf049c8f90/fs_phase23/manifest/ETH_MANIFEST.json): 83 candidates, six targets, three TRAIN folds, 3,403 feature pairs.
- [ETH development dataset contract](https://github.com/harveybc/predictor/blob/25fcfe1c045dbd3449b8f65d695788bf049c8f90/examples/data/project3/ethusdt_4h_tech_stat_full_model_ready.manifest.json): the original symbol is ETHUSDT, the contract asset label is ETHUSD, and the interval is 4h. These labels are retained, not silently treated as identical markets.
- [Bundle builder](https://github.com/harveybc/predictor/blob/25fcfe1c045dbd3449b8f65d695788bf049c8f90/tools/phase1_deployment/prepare.py): converts retained campaign inputs into independent population bundles.

EURUSD source IDs include FX prices, FRED observations, market indices, ETFs,
commodities, CFTC data and clock-derived features. They are lake identifiers,
not direct provider download URLs. The ETH phase-2 manifest labels its source
`git-pinned-development` and its availability clock `DEVELOPMENT_UNCERTIFIED`.
Do not infer certified point-in-time availability or a particular exchange
from that label. Its original provider/acquisition recipe is not fully resolved
by these manifests alone.

## Obtaining comparable data

These are acquisition entry points, not claims that every available subscription
was consumed in the retained experiment.

| Source | Acquisition documentation | Required provenance |
|---|---|---|
| FRED / ALFRED | [Official API](https://fred.stlouisfed.org/docs/api/fred/) and [observations](https://fred.stlouisfed.org/docs/api/fred/series_observations.html) | Series ID, requested date range, retrieval time, real-time/vintage interval, availability rule, original response hash |
| CFTC | [Historical compressed reports](https://www.cftc.gov/MarketReports/CommitmentsofTraders/HistoricalCompressed/index.htm) | Report family, market identifier, report date, publication/availability date, source archive hash |
| Yahoo Finance | [Provider](https://finance.yahoo.com/) and the acquisition workers in [financial-data](https://github.com/harveybc/financial-data/tree/ef0ba6612b2f161de59a58ee08f7bf61d69b8cec/_scripts/workers) | Ticker, interval, adjusted/unadjusted policy, timezone, retrieval time and file hash; a daily date alone is not a publication timestamp |
| Alpaca | [Historical market-data documentation](https://docs.alpaca.markets/us/docs/historical-stock-data-1) | Feed, symbol, entitlement, interval, adjustments and complete response pagination; own credentials |
| FXMacroData | [Provider](https://fxmacrodata.com/) | Event identity, release time, actual/consensus vintages, reception time and the fields available in your subscription |
| Existing FX price lake | [financial-data provenance and acquisition](https://github.com/harveybc/financial-data/tree/ef0ba6612b2f161de59a58ee08f7bf61d69b8cec) | Recover the actual provider from the resource's provenance; do not substitute another price feed under the old digest |

FRED series IDs such as `DGS30` and `VIXCLS` are identifiable from the manifest's
source paths. Request observations and retain the raw response before deriving
returns. The API documentation describes the required key and vintage fields.
Use an appropriate vintage for historical availability; downloading today's
revised values is a new input population.

Alpaca and FXMacroData access exists in the owner's environment, but access alone
does not prove usable history inside this TRAIN period. An unavailable or
out-of-period source remains an explicit disposition. Never put subscription
credentials or account identifiers in a public configuration.

## Rebuild sequence

1. Acquire raw files using your access and record provider, request parameters,
   retrieval time, version/vintage, license/access constraints and SHA-256.
2. Normalize timestamps and units; retain an availability timestamp or explicitly
   documented approximation. Record gaps and missing vintages.
3. Rebuild features using the declared transformations, physical windows and
   causal support. Fit transformations only on the permitted training rows.
4. Materialize features and future targets with identical row identities. Keep
   labels unavailable until their full horizon is observed. Preserve the
   train/validation/test contract and source lineage.
5. Compare output digests with the frozen manifest for exact replay. A mismatch
   creates a new study identity; comparable data is not byte-identical replay.
6. Run the profiles/causal study, then pairs and rankings, and finally the domain's
   predictive validation. Keep all metrics, dispositions and readback receipts.

Source links and scripts make the method adaptable. Exact historical replay
also requires the retained input versions. The current public manifests do not
yet provide a complete, verified download-to-final-parquet recipe for every
source. Publishing that recipe is an explicit portability follow-up; this
README does not claim it already exists.

## Storage policy

Keep the analytical database and a verified backup on your storage. Publish
small manifests, schema versions, source identifiers, configuration, code pins,
checksums and regeneration commands. Large `.duckdb`, compressed snapshots,
Parquet data and weights stay out of this repository. A source URL alone does
not establish permission to redistribute its downloaded data.
