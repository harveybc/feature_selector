# Timing-target selection: where it lives (2026-10-19)

The timing extension selects features whose target is the sealed ZigZag hindsight expert (heuristic-strategy
`app/short_horizon/zigzag.py`, sha256 `b30788e6...`, choice Depth 3 / Deviation 36.3 / Backstep 2), i.e.
pivot/entry-exit TIMING for RL and heuristic strategies, not price prediction. It is implemented in the
owning repositories and only documented here; nothing in the pinned engines was modified.

| Component | Owner | Branch (not yet pinned in upstream.lock.json) |
|---|---|---|
| Targets `timing_pivot` family (T1 pivot within k, T2 confirmed-timing action, T3 expert leg P&L), price pool, availability gate, driver, sealed manifest | predictor `tools/timing_pivot_targets.py`, `tools/timing_price_pool.py`, `tools/timing_selection.py`, docs `docs/TIMING_SELECTION.md` | `satoshi/timing-selection-20261019` |
| Causal adapter: pack `EURUSD_TIMING` (HAC lag screen, PCMCI+ wrapper, matched-control contrast) | causal-inference `provider/src/causal_inference_provider/fs_timing_pack.py`; `feature_selection_worker.py` extended append-only | `satoshi/timing-target-pack-20261019` |
| Predictive validation (pivot-detector harness, owner's early-stopping rule, decision 2023 / confirmation 2024, identical rows) | heuristic-strategy `tools/short_horizon_timing_eval.py` | `satoshi/timing-selection-eval-20261019` |
| Candidate sources | financial-data `_scripts/core_selection_bundle.py` @41f5af170 + feature-eng `normalize_phase1b.py` @d081d0f (30 inventory candidates, loaded by path); feature-eng causal fractal store (manifest sha256 `906578e1...`) | as cited |

The full map of the pre-existing tooling (phase 1-4 engines, FS4, predictive validation, causal stage,
expert and harness, plugin conventions) is in predictor `docs/TIMING_SELECTION.md` section 1.

Example configuration: [`examples/timing_pivot_eurusd.json`](../examples/timing_pivot_eurusd.json)
(placeholders for private paths; every input pinned by sha256). The lock pins are updated only after the
owners merge and the real integration test passes (repository rule).

## Revision 2 results (2026-10-19)

Revision 2 incorporates the plan audit (REVISE_BEFORE_FINAL_SEAL). Sealed object: predictor
`docs/timing_selection/eurusd_h1_v2/SELECTION_MANIFEST.json` (`TIMING_PROXY_SELECTION`, manifest
sha256 `4fd6710e...`, status pending an independent decision). Results audit request:
`docs/timing_selection/eurusd_h1_v2/AUDIT_REQUEST_TIMING_SELECTION_FOR_MUSASHI.md` on the same branch.
Selected inputs (proxy usefulness only): RAW_BAR_LOG_RETURN, cal.hod_sin, cal.session_europe,
px.atr_ratio_14_120, px.close_loc_2, px.logret_24, variogram_hurst_w96.

## Revision 3 results (2026-10-19, expert v2)

Revision 2 is superseded by the ZigZag v2 expert (heuristic-strategy abbfaa6). Sealed object: predictor
`docs/timing_selection/eurusd_h1_v3/SELECTION_MANIFEST.json` (`TIMING_PROXY_SELECTION`, manifest sha256
`b4da1012...`, pending an independent decision), with its v3 results audit request in the same
directory. Selected inputs (proxy usefulness only): RAW_BAR_LOG_RETURN, RAW_ELAPSED_HOURS, cal.hod_cos,
px.atr_ratio_14_120, px.close_loc_2, variogram_hurst_w96.
