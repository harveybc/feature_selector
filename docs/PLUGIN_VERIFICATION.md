# Package 0.2 verification

Verified 2026-10-25 (America/Bogota). This is software acceptance, not a market
selection result or a new causal certification.

## Environments and installation

- Python 3.12; isolated virtual environment created without system site packages.
- Installed with `python -m pip install -e '.[test]'`.
- Clean environment: NumPy 2.5.4, pytest 9.1.1; feature-selector 0.2.0.
- The first clean test run exposed missing setuptools/wheel in the test extra.
  Declared both dependencies, reinstalled using the documented command and reran.
- A separate external distribution (`feature-selector-example-plugin` 0.1.0)
  was built, installed, discovered and used by the real CLI.

## Tests

`python -m pytest -q`: **34 passed, 4 skipped** in the clean environment.
The four skips are the preserved legacy cross-repository phase-2/3 integration
tests; they require `SELECTION_PREDICTOR_ROOT` at the historical pinned revision.
They were not rerun or represented as passing in this package release.

Coverage includes config precedence and plugin replacement, external discovery
and duplicate rejection, coherent blocks, empty-branch structural descriptions,
backward search and actual floating reinclusion, bounds, unscorable candidates,
forbidden transforms, temporal split checks, every mandatory stage, real-RL
request/model/seed/support mismatches, count consistency, artifact mutation,
no-trade undefined metrics, timeout, single writer, cache tampering, atomic-write
cleanup, duplicate JSON rejection and restart reuse.

These tests authenticate the real-model bridge's protocol with synthetic
receipts. They do NOT train the native PPO policy or certify its structural
subset adapter, GPU behavior or business simulator.

## Installed example and replay

Executed `scripts/verify_plugin_release.py` from the installed clean environment.

| Observation | Result |
|---|---|
| Synthetic input columns | 5 |
| Evaluated subsets | 18 |
| Selected | signal_b, redundant_a |
| Termination | MIN_SIZE |
| Methodology stages | All seven pre-wrapper stages plus confirmation |
| Retained files checked on replay | 19 |
| Bytes AND modification times on replay | Identical |
| Scientific/market release | false |

The redundant signal is a near-copy of signal_a, not evidence of financial
usefulness. The deterministic linear example is installation evidence only.
The separately installed external_fixed plugin selected the requested
signal_a/signal_b pair in a distinct run, also with no scientific release.

Measured local result digest:
`cca12879343faf5005267a8ed707ae2ab48c816870a4d586d9f733f0249214f8`.
Output paths form part of the effective config identity, so another output
location is expected to have a different run/result digest. Exact replay is
checked within the same run, not claimed across arbitrary paths/environments.

## Traceability and next integration

P01-P10 from PLUGIN_DESIGN.md have package-level tests and the installed CPU
example. Native-model semantic equivalence is still a separate integration task.
No market dataset, GPU, TEST, paid service, live trading process or historical
campaign was modified. No remote history was rewritten. Existing engines and
the historical demo remain available.

Next scientific work: correct the native simulator findings; implement/verify
the actual PPO subset-to-recipe bridge against this request/receipt protocol;
adapt retained upstream stage evidence with exact identities; then run the
bounded model-specific search. The complete methodology remains mandatory.
