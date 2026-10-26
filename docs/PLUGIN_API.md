# Plugin API v1

Install packages normally with pip. The host discovers them through
`importlib.metadata.entry_points`; it never scans arbitrary directories.
Ambiguous names fail. Every plugin class declares:

```python
class Plugin:
    api_version = 1
    plugin_params = {"parameter": "default"}
```

Parameter dictionaries are namespaced in JSON. All accepted parameter names
must appear in `plugin_params`, including required values with empty defaults.
The plugin must validate types and required values before work. Instances are
constructed without arguments; effective params are passed to their method.

| Entry-point group | Method |
|---|---|
| `feature_selector.pipelines` | `run(config, plugins, witnesses, base)` |
| `feature_selector.methodologies` | `run(config, plugins, store, context, base, run_id)` |
| `feature_selector.selectors` | `select(dataset, evaluate, params)` |
| `feature_selector.evaluators` | `evaluate(request, context, params, work, base)` |
| `feature_selector.datasets` | `load(params, base)` |
| `feature_selector.stages` | `run(request, params, work, base)` |

`base` is the JSON configuration directory. `work` is a new per-attempt directory.
`store` provides immutable receipts, atomic writes and hash-checked caches.
Do not write to other campaigns or fit inside a selector's planning code.

## External package example

```toml
[project]
name = "my-selection-plugins"
version = "0.1.0"
dependencies = ["feature-selector>=0.2.0"]

[project.entry-points."feature_selector.selectors"]
my_selector = "my_package.selection:Plugin"
```

A complete independently installable example is in `examples/external_plugin`.
Use its packaging convention for a new methodology/pipeline/evaluator. The
`src/feature_selector` namespace avoids the `app` collisions among sibling repos.
This follows predictor's entry-point/configuration architecture, not its legacy
short-flag parsing bug. Source identities and distribution versions are recorded.
An external plugin is trusted installed code, not a sandboxed extension.

## Dataset manifest

`manifest` params: `path`, `sha256`. The referenced JSON must have:

```json
{
  "schema": "feature_selector.dataset.v1",
  "scope": "development",
  "features": ["f1", "hour_sin", "hour_cos"],
  "groups": [
    {"name": "temporal", "columns": ["f1"], "extractor": "causal_tcn"},
    {"name": "calendar", "columns": ["hour_sin", "hour_cos"], "extractor": "pointwise"}
  ],
  "blocks": [["f1"], ["hour_sin", "hour_cos"]],
  "support_hash": "<64-lowercase-hex>",
  "scaler_hash": "<64-lowercase-hex>",
  "representation": {"id": "<sealed-representation>", "window": 13, "stride": 2},
  "splits": {
    "train": ["2020-01-01", "2023-07-01"],
    "selection": ["2023-07-01", "2024-01-01"],
    "test_start": "2025-01-01"
  },
  "constraints": {
    "agent_state": "none", "scaling": "fixed_train", "clipping": false,
    "fit_scope": "train_only", "test_access": false
  },
  "files": [{"path": "admitted_inputs.parquet", "sha256": "<64-lowercase-hex>"}]
}
```

Placeholders are deliberately not runnable. The dates illustrate the current
internal development split, not a change to the owner's TRAIN/VALIDATION/TEST
contract. Supply the actual admitted split manifest, scaler, calendar and business
recipe. Additional descriptive metadata is retained in the context identity.
`blocks` are indivisible coding units. `groups` partition features, without
duplicates; a group and a block serve different purposes.

The paired support is fixed before selection. A smaller subset cannot silently
gain more dates because its missing-value requirements became easier. Distinct
coverage contrasts need distinct identities. All input files are rechecked.

## Stage adapters and full evidence

For each of `data_quality`, `profiles`, `causal`, `relationships`,
`candidate_generation`, `encoding`, `extractor_selection`, `confirmation`, choose
an installed stage plugin. Built-ins:

- `artifact`: `path` and `sha256` of an existing stage receipt.
- `command`: `command` argv, `source_pins` list and `timeout_seconds`.
- `synthetic`: refuses real-data scope; only an example adapter.

Commands contain `{request}` and `{response}` placeholders. They run without a
shell. Supply absolute executables or PATH names and paths relative to the config
directory. Command source pins are `{path, sha256}` records and must be nonempty.
Use pinned virtual environments; record engine dependencies in the native receipt.

Request fields: `schema=feature_selector.stage_request.v1`, `stage`, `run_id`,
`context_sha256`, and the complete `context`. The command writes:

```json
{
  "schema": "feature_selector.stage_result.v1",
  "stage": "causal",
  "context_sha256": "<exact request context digest>",
  "status": "COMPLETE",
  "scope": "development",
  "evidence": {
    "assumptions": {"status": "MEASURED", "detail": "<artifact reference>"},
    "conditional_association": {"status": "MEASURED", "detail": "<artifact reference>"},
    "multiplicity": {"status": "MEASURED", "detail": "<artifact reference>"},
    "placebos": {"status": "MEASURED", "detail": "<artifact reference>"},
    "counterfactuals": {"status": "NOT_IDENTIFIED", "detail": "<reason and scope>"},
    "unidentified": {"status": "MEASURED", "detail": "<complete list and scope>"}
  },
  "files": [{"path": "causal_evidence.json", "sha256": "<actual hash>"}]
}
```

The exact required fields per stage are `EVIDENCE_FIELDS` in
`src/feature_selector/stages.py`. Each item has `status` and nonempty `detail`.
Allowed states: MEASURED, NOT_IDENTIFIED, NOT_APPLICABLE (reason required).
These reflect retained evidence, not proof manufactured by a status string.

Stage results can update only `features`, `groups`, `blocks`, `representation`,
`feature_metadata`, `support_hash`, `scaler_hash`. All dependent fields must be
consistent. They cannot change scope, time partitions or the no-feedback/fixed-
scaling contract. A stage adapter maps existing engine results into this envelope;
do not duplicate upstream algorithms or invent results for a missing stage.

Confirmation receives `selected` and `search_sha256`; it returns that identical
`selected`, an `accepted` boolean, and evaluation/selection_bias/activity/
subset_identity evidence. It must use the declared confirmation protocol, not
reselect on TEST. No confirmation acceptance can promote a synthetic or
budget-incomplete search.

## Real RL evaluator

Configure `evaluator.plugin=rl_model` with:

```json
{
  "command": ["<python-in-model-environment>", "<model-wrapper-bridge.py>",
              "--request", "{request}", "--response", "{response}"],
  "source_pins": [{"path": "<bridge.py>", "sha256": "<actual hash>"}],
  "timeout_seconds": 7200,
  "model_id": "<actual grouped temporal PPO variant>",
  "model_sha256": "<actual model code/config identity>",
  "engine_sha256": "<corrected simulator identity>",
  "training_budget": {"total_timesteps": 102400},
  "score_metric": "sharpe",
  "minimum_orders_per_week": 2.0,
  "max_gap": null,
  "cost_mode": "configured",
  "selection_use": "cost_aware",
  "cost_profile": {
    "spread": {"rates": [0.0001], "settings": {"unit": "price", "charge": "half_per_fill"}},
    "slippage": {"rates": [0.00002, 0.00005], "settings": {"unit": "price", "order": ["market", "stop"]}},
    "commission": {"rates": [3.5], "settings": {"unit": "USD_per_lot_per_side", "lot_units": 100000}},
    "financing": {"rates": [-7.0, 2.5], "settings": {"unit": "USD_per_lot_per_rollover", "order": ["long", "short"], "lot_units": 100000, "triple_index": 3}}
  }
}
```

This is a contract template, not a launched or scientifically approved campaign.
Example cost rates are illustrative, NOT broker-verified. The bridge must export
the complete actual profile, including every spread-schedule interval/clock in
`settings` and its rates in the matching declared order. Never summarize a
time-dependent profile into its mean. Each of the four components requires a
nonempty finite `rates` list and nonempty `settings` mapping with units. Signed
financing rates allow credits. This normalized contract does not replace the
native simulator config; the native adapter must verify their exact agreement.

For an easy-mode search use `cost_mode=zero_cost, selection_use=diagnostic`.
Retain the configured profile digest to identify the paired costly control;
the zero-cost engine zeros every charge and credit. Such a run always has
`final_selection=false`. Configured-cost diagnostics are also allowed. Only
cost-aware configured runs can become final selections, subject to all other
checks. Requests/cache identities include these options; old receipts lacking
cost provenance must be regenerated by the bridge, never silently adopted.
Training budget is passed unchanged; there are no hidden epoch or patience
defaults in the selector. `max_evaluations` counts subsets. Maximum attempted
model fits is subsets x seeds x max_attempts, plus the external stages' budgets.

The native runner MUST:

1. Read and verify the request and the pinned inputs; reject unknown fields it
   cannot implement. Use its real policy factory, action outputs and simulator.
2. Rebuild active multichannel groups and fusion inputs from `features/groups`,
   including empty-branch removal and reinclusion. Preserve all other frozen
   settings and record parameter count. Do not merely mask unused features.
3. Start fresh model/optimizer/rollout state for every subset and seed. For SAC,
   also start a fresh replay buffer. No cross-subset checkpoint reuse.
4. Fit only TRAIN with the declared budget; use its fixed TRAIN scaler projected
   to the ordered columns. Score TRAIN and selection on identical frozen support
   across candidates. Do not inspect TEST or expert labels for our RL lane.
5. Save native weights, full effective config, tensor/branch mapping, support,
   scaler, metrics and trading ledger. Return hashes for those actual artifacts.

Response schema `feature_selector.rl_result.v1` echoes `request_sha256`
(`feature_selector.io.digest(request)`), `features`, `groups`, `seed`,
`support_hash`, `scaler_hash`, `splits`, `model_id`, `model_sha256`, `engine_sha256`,
`training_budget`; also `fresh_training=true`, `test_access=false`,
`observation_contract` exactly equal to request constraints, `parameter_count`,
and nonempty `artifacts` (`path`, `sha256`). Relative artifacts resolve against
the config directory.

Also require `cost_mode`, `cost_profile_sha256=digest(cost_profile)` and
`cost_components`, keyed by `train` and `selection`, each with currency totals
for `spread`, `slippage`, `commission`, `financing`. Totals must sum to that
split's `costs`; negative financing is a credit. In zero-cost mode every
component must be exactly zero, not merely a net sum of zero.

`metrics` has exactly `train` and `selection`, each containing:

| Fields | Units |
|---|---|
| `profit`, `costs` | Account currency, same initial capital across arms |
| `sharpe` | Native declared annualization, immutable across arms |
| `max_drawdown` | Fraction in [0,1] |
| `orders`, `buy_orders`, `sell_orders`, `early_closes` | Nonnegative integer counts |
| `orders_per_week` | Average over the declared full evaluation interval |
| `win_rate`, `buy_win_rate`, `sell_win_rate` | Fractions, not percentages; null exactly when the corresponding order count is zero |

The bridge checks subset/model/engine/budget identity, artifact bytes, finite
defined metrics and direction counts. Undefined Sharpe is retained as null,
never zero. An undefined chosen score makes the arm ineligible without dropping
that seed or erasing its trading ledger. Scores are higher-is-better;
gap = max(0, TRAIN score - selection score), when both are defined.
All seeds must meet the activity/gap conditions for eligibility. Native metrics
remain in receipts, not just the scalar used to choose subsets.

An external evaluator can replace this command bridge. It must declare
`production_rl=True`, implement `evaluate(...)`, and `verify(native,request,
params,base)` returning the same score record on replay. That marker is a
capability declaration, NOT a security boundary. Audit the installed evaluator.

## Resume, provenance and operation

One process owns the run lock. Identical completed evaluations are reused only
after hash and native-receipt verification. Partial attempts stay on disk; a new
attempt starts fresh. The default maximum is two, configurable up to three.
Exhaustion is explicit, not an endless retry. External commands have timeouts;
admission/VRAM checks belong to the native runner because it owns the device.

The CLI itself runs through the full sequence without intermediate approvals.
For reboot persistence, supervise that SAME command through your existing timer
or service; do not launch a second writer. Status is a single read, not a monitor.
No scheduler, GPU process or live campaign is installed automatically.

Hashes detect inconsistencies, not malicious coherent replacement by an owner
of all files. Library/runtime identity and exact replay remain the model runner's
responsibility. The included protocol tests are synthetic, not financial training.
