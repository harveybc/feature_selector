# feature_selector

Time-series feature selection with **external plugins**, JSON configuration,
retained evidence and model-specific evaluation. Simple methods and our complete
causal/profile/encoding/extractor workflow share one interface.

Canonical repository: [harveybc/feature_selector](https://github.com/harveybc/feature_selector).
`dataset_selection` was an old local checkout name, not another scientific engine.

## Available now

- Installed entry-point plugins for pipelines, methodologies, selectors,
  evaluators, datasets and stages, including independently maintained packages.
- Predictor-style config precedence and saved effective configuration/code identities.
- Sequential backward **floating** selection: deletion, conditional reinclusion,
  best subsets per size, deterministic tie handling and a finite evaluation budget.
- Full `causal_selection` orchestration, retaining every scientific stage.
  Existing algorithms stay in their owning repos, connected by artifact/command
  adapters rather than duplicated or replaced.
- `rl_model`: a real-training request/receipt bridge to the actual RL model.
  It does not substitute a classifier or MLP for the configured policy.
- Sequential execution, exclusive lock, atomic retained results, bounded attempts,
  identity-bound resume, explicit failure and partial-search status.

**Release scope:** package, contracts and runnable example. This does not close
the separate financial simulator audit or certify a newly selected market list.
The real-model runner must implement the [RL contract](docs/PLUGIN_API.md#real-rl-evaluator)
on the corrected simulator. No financial RL training is started by installation.

## Installation and first run

Python 3.10+ on Linux; verified on Python 3.12. The small example requires no GPU,
credentials, market data, database or remote service.

```bash
git clone https://github.com/harveybc/feature_selector.git
cd feature_selector
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[test]'

feature-selector --action plugins
feature-selector --action plan --load_config examples/plugin_demo.json
feature-selector --load_config examples/plugin_demo.json --output output/demo
feature-selector --action status --output output/demo
# Identical command resumes without repeating accepted evaluations.
feature-selector --load_config examples/plugin_demo.json --output output/demo
python -m pytest -q
```

Equivalent: `python -m feature_selector --load_config ...`.
The demo generates five inputs and actually fits a small regularized linear model
on synthetic TRAIN, evaluating synthetic chronological validation. It demonstrates
selection and installation, **not financial RL, causal discovery or TCN selection**.
Its solver is deterministic, so one demo seed suffices. `final_selection` is
always `false`; a synthetic run cannot release a market recipe.

| Output | Meaning |
|---|---|
| `effective_config.json` | Fully merged JSON |
| `RUN.json` | Dataset identity and installed plugin/code witnesses |
| `stages/` | Evidence for all methodology stages |
| `evaluations/` | Subset/seed results with hashes |
| `attempts/` | Requests, responses, logs and preserved failures |
| `SEARCH.json` | All evaluated subsets, deletion/reinclusion trace, best per size |
| `RESULT.json` | Methodology result and confirmation outcome |
| `STATUS.json` | Current unit, completion or failure |

`COMPLETE` means the driver finished, not profitability or scientific acceptance.
`search_complete=false` means the search exhausted its budget. Data, checkpoints,
logs and credentials are not committed.

## Copy/paste instructions for an AI agent

```text
Work in harveybc/feature_selector. Read AGENTS.md, README.md and docs/PLUGIN_API.md.
Create a Python virtual environment and install -e '.[test]'. List the plugins.
Plan examples/plugin_demo.json, then run it on CPU in a NEW output directory.
Do not use market data, GPU, TEST, credentials or production services for this check.

Read STATUS.json, SEARCH.json and RESULT.json. Report selected features, subset
count, termination reason and final_selection=false. Repeat the identical command;
verify evaluation files and RESULT.json remain byte-identical and no fits repeat.
Run pytest. Legacy tests need SELECTION_PREDICTOR_ROOT at upstream.lock.json's pin;
report their skips separately from package tests.

Install examples/external_plugin in this environment. Verify external_fixed is
discoverable and run a new synthetic experiment using it. Do not claim synthetic
acceptance establishes trading performance or a completed causal study.

For real RL, follow docs/PLUGIN_API.md and docs/INTEGRATION_MAP.md. Bind admitted
files, all scientific-stage evidence, real architecture/engine/training-budget
identities and an external runner implementing the request/receipt contract.
Never replace that runner with the synthetic model. Preserve fixed TRAIN scaling,
no account-feedback inputs, no arbitrary clipping and TEST closed. Use bounded
sequential execution and retain negative results, failed attempts and limitations.
```

## Configuration

Precedence: **plugin defaults < application defaults < JSON < explicit CLI**.
Parameters are namespaced by role; two plugins can have a `window` without
colliding. Unknown parameters/CLI options and ambiguous plugin names are errors.

```json
{
  "pipeline": {"plugin": "sequential", "params": {}},
  "methodology": {"plugin": "causal_selection", "params": {}},
  "selector": {
    "plugin": "floating_backward",
    "params": {"min_features": 10, "max_evaluations": 200, "tolerance": 0.0}
  },
  "evaluator": {"plugin": "rl_model", "params": {}},
  "seeds": [7, 19, 43]
}
```

This fragment is not a complete real run: add a pinned dataset, every stage and
the RL runner configuration. There is no silent demo/model/data fallback.

```bash
feature-selector --load_config examples/plugin_demo.json \
  --set selector.params.max_evaluations=12 \
  --set selector.params.tolerance=0.0001 \
  --output output/demo-budget12
```

`--set path=JSON` accepts typed numbers, booleans, lists, objects and strings.
Input paths resolve relative to the JSON file; output resolves relative to the
invocation directory. A different config, code or input requires a new output
directory. Budget changes are new identities, not identical replays.

## Complete causal_selection workflow

| Stage | Work preserved |
|---|---|
| Data quality | Inventory, source verification, coverage, outliers, publication clocks |
| Profiles | Stationarity, lags, temporal/spectral behavior, fold stability |
| Causal | Assumptions, association, multiplicity, controls/placebos, counterfactual limits |
| Relationships | Aliases, linear/nonlinear dependence, lags, redundancy groups |
| Candidate generation | Existing filters, parent/component contrasts, interaction rescue |
| Encoding | Per-column measured choices and TRAIN-only fitted transformations |
| Extractor selection | Profile groups, measured contrasts, receptive fields, combined representation |
| **Model wrapper** | Fresh fitting of the actual downstream model for every subset and seed |
| Confirmation | Independent confirmation evidence and adaptive selection-bias assessment |

No stage is optional in this methodology. `NOT_IDENTIFIED` remains unknown, not
proof of causal absence. Production evidence must cover every declared subject.
The artifact bridge verifies bindings and bytes; it is not a new scientific audit
of an upstream estimator. See the [integration map](docs/INTEGRATION_MAP.md).

### Groups, architecture and pruning

The manifest declares ordered columns, coherent encoding blocks, profile groups
and representation. Deleting an input reduces its branch's channels; deleting the
last removes the branch and its fusion connections. Reinclusion restores it.
The evaluator receives remapped indices and must rebuild/retrain the actual model.
Zero masking alone is not structural pruning.

Freeze profiles, extractor assignments, window/downsampling, reward, business
rules and training budget during subset comparisons. Record parameter counts.
Choose a different causal CNN/TCN architecture in a separate identified contrast,
not silently during feature search. No rolling z-score, arbitrary clipping or
agent-state feedback is allowed in this financial methodology.

### Selection and interpretation

The RL bridge supports declared native Sharpe or profit objectives. External
evaluators can implement other frozen objectives. Retain TRAIN/selection scores,
gap, drawdown, activity, long/short counts, win rates, early exits and costs.
The baseline requires at least two orders/week on average per seed, as eligibility,
not a bonus for forcing trades. An explicit maximum gap may also apply.

Floating search is a bounded heuristic, not global optimization. Its tolerance
can prefer a smaller near-best subset but is **not** a statistical noninferiority
certificate. Repeated selection makes internal validation part of development.
TEST is not used. A PPO result does not prove the same inputs are optimal for SAC
or the expert-guided lane; each needs its own model-specific evaluation.

## Install an external plugin

```bash
python -m pip install ./examples/external_plugin
feature-selector --action plugins
feature-selector --load_config examples/plugin_demo.json \
  --set selector.plugin=external_fixed \
  --set 'selector.params={"columns":["signal_a","signal_b"]}' \
  --output output/external-demo
```

Replacing a plugin discards the old plugin's file parameters. Each plugin is an
independently installed distribution with a `feature_selector.*` entry point.
JSON selects installed code; it does not install code. Duplicate names are rejected.
See [PLUGIN_API.md](docs/PLUGIN_API.md) and the separate example package.

## Existing engines and limits

- [Design/traceability](docs/PLUGIN_DESIGN.md), [verification](docs/PLUGIN_VERIFICATION.md).
- [Legacy phase-2/3 example](docs/LEGACY_PHASE23.md): retained pairwise/mRMR/JMI and
  DuckDB workflow. Its historical `upstream.lock.json` pins are not current market admission.
- [Legacy portability guide](docs/PORTABILITY.md): original scientific interfaces.

The package does not execute live trades, fix broker costs, delete campaigns or
move implementations out of their owning repos. Hashes detect accidental changes;
they are not signatures against a writer replacing a directory coherently.
Use governed environment credentials in external runners, never secrets in JSON.

MIT for this package; external engines and data retain their own licenses.
