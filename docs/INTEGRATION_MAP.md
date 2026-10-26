# Integration map: keep the complete scientific workflow

The plugin package is the coordinator. It does not relocate these engines or
replace their detailed contracts with a single generic score.

| Responsibility | Owning implementation | Plugin boundary |
|---|---|---|
| Real acquisition, recovery, lake admission | financial-data, data-lake, data-gov | dataset + data_quality |
| Original and engineered features; parent/components | feature-eng, predictor timing producers | dataset/catalog + candidate_generation |
| Per-series profiles and causal studies | causal-inference | profiles + causal |
| Pairwise dependence, lagged metrics, mRMR/JMI/filter rankings | predictor tools/feature_pairwise_* and feature_filter_selection | relationships + candidate_generation |
| Measured contrasts, interaction rescue, coding alternatives | heuristic-strategy tools/pool_selection_v2.py and retained selection evidence | candidate_generation + encoding |
| Profile groups, extractor contrasts and combined representation | feature-extractor and the retained T1/T3 workflow | extractor_selection |
| Native policy, reward, simulator, training and trade metrics | agent-multi and its pinned trading engine | rl_model or independently installed evaluator |
| Expert-guided policy | heuristic-strategy expert lane | separate evaluator/run; no expert inputs in the unguided lane |
| Analytical persistence | data-warehouse and existing native collectors | native result artifacts/readback, extendable pipeline |

## What is added, not removed

Real-model floating wrapper selection follows the measured causal, relationship,
encoding and representation stages. It must use the actual intended architecture,
not the proxy model that generated preliminary rankings. Original-vs-component
tests, multiple feature families, nonlinear interactions, uncertainty and unknown
causal results remain visible. The output is model-specific, not a universal
feature list valid for every downstream task.

Feature/profile/encoding/representation artifacts are bound to the context digest
at each stage. Adapters must verify their native receipts before making a stage
envelope. `artifact` can reuse valid results without repeating expensive work;
`command` launches the same owning-engine CLI through a versioned thin bridge.
No missing scientific result may be filled with synthetic metadata.

## Real RL integration remaining

The package supplies the strict command evaluator and tests its protocol. The
native PPO runner still needs its production bridge mapping the incoming subset
to the actual recipe/branches/scaler, qualifying fresh training and exact reload,
and returning native artifacts/metrics. The separate execution/accounting audit
must be corrected first. Those are real implementation/verification tasks, not
configuration-only claims. No current market selection is promoted here.

Use the baseline architecture chosen in the separate temporal-model contrast;
freeze it for pruning. Prefix causality, full-window coverage and multichannel
group behavior need executable tests in that model repository. The wrapper
cannot infer these properties from the string `causal_tcn`.

## Legacy pins

`upstream.lock.json` remains the original public phase-2/3 example pin. It is NOT
a new source of accepted EURUSD inputs or a replacement for newer v5 receipts.
The old README and its historical caveats are retained in LEGACY_PHASE23.md.
Revising an engine pin requires its own compatibility/replay evidence.
