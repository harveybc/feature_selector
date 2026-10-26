# Plugin architecture and acceptance design

Owner: feature_selector. The former local directory name dataset_selection was
an alias for THIS repository, not a second scientific engine. Keep upstream
implementations in their owning repositories; this package owns orchestration,
configuration, plugin contracts and subset search.

## Requirements before implementation

| ID | Requirement | Test/evidence |
|---|---|---|
| P01 | Installed external entry points; reject ambiguous names | resolver tests and separate wheel smoke |
| P02 | plugin defaults < application defaults < JSON < explicit CLI | merge, types, unknown options tests |
| P03 | Complete causal methodology, no stage silently omitted | order and missing-stage tests |
| P04 | SBFS: backward elimination and conditional reintroduction | deterministic oracle including reversal |
| P05 | Real-model evaluator, not proxy substitution | request/receipt identity, subset, model and support checks |
| P06 | Structural branch pruning, order and coherent blocks | subset/remap/empty-group tests |
| P07 | No TRAIN/validation mixing or TEST selection | split and receipt guards |
| P08 | No rolling z-score, clipping or account feedback | contract rejection tests |
| P09 | Bounded sequential work, atomic results, exclusive run lock, resume | subprocess failure/restart/cache tamper tests |
| P10 | Complete readable installation and AI-agent example | installed CLI smoke, replay and final reports |

## Scientific workflow, not a reduced filter

Mandatory ordered stages: data_quality, profiles, causal, relationships,
candidate_generation, encoding, extractor_selection, model_wrapper, confirmation.
The first seven and the final confirmation use stage plugins: authenticated
existing artifacts, a bounded command bridge, or an installed external plugin.
They preserve inventory, availability clocks, missing/outlier decisions, TRAIN
profiles, causal assumptions/unknowns, pairwise and lagged dependence, parent vs
decomposition components, interaction rescue, encoding contrasts, grouping and
extractor comparisons. A schema receipt is NOT a fresh scientific audit.

model_wrapper runs the configured selector with the configured actual-model
evaluator. Existing supervised proxy methods remain candidate generators, not
certification of downstream RL utility. No inference of causal absence from
NOT_IDENTIFIED. No automatic removal for weak proxy importance. Confirmation is
required for production release; an interrupted/budget-limited search remains
explicitly incomplete. A synthetic demonstration can NEVER release a market recipe.

## Interfaces

- Entry point namespaces: feature_selector.pipelines, methodologies, selectors,
  evaluators, stages. Classes expose api_version=1 and plugin_params defaults.
- JSON has separate role names and params, avoiding parameter collisions.
- Pipeline orchestrates; methodology owns ordered stages; selector proposes
  subsets; evaluator owns real fresh training and native scoring; stages adapt
  existing engines rather than duplicate their mathematics.
- Evaluator request: run identity, ordered columns, active groups, representation,
  support/scaler identities, TRAIN/internal validation, seed, model/engine hashes,
  training budget and constraints. Response echoes request hash and identities,
  train/validation scores, activity, native trading statistics and artifact hashes.
- Production receives no demonstration targets as observations. No state feedback,
  rolling normalization, arbitrary clipping, synthetic price fill or TEST reads.
- Profiles/group assignments and representation are frozen within one wrapper.
  Dropping the last feature removes that group. Architecture changes are declared
  in a new run, never hidden in subset search.

## Search and cost

Implement backward floating search with best subset per cardinality, conditional
reinclusions only when improving that cardinality, deterministic tie handling,
visited-state cycle prevention and a hard evaluation budget. Scores are paired
across fixed seeds and support. Use development mean score, explicit activity and
gap constraints, and a declared simplification tolerance. Tolerance alone is NOT
a statistical equivalence certificate. Preserve per-seed metrics and require
external confirmation, not an assertion of globally optimal or noise-free inputs.

Regression tests use deterministic oracles to isolate search behavior. The public
numeric demo genuinely fits a small linear model to synthetic data; this is only
an installation/contract example, never the evaluator for the financial RL lane.

## Release boundary

Package/API/example acceptance is separate from financial scientific acceptance.
The real PPO adapter, corrected simulator and admitted receipts must be supplied
and verified before a new RL campaign. Do not claim these are repaired by
packaging. Existing upstream.lock.json describes the legacy example only, not
admission of its historical EURUSD artifacts.

## Cost-mode extension (P11)

The real evaluator must bind cost mode and the complete cost-profile digest in
every request/result and cached identity. `zero_cost` is diagnostic only: it
can search subsets but cannot emit a final cost-aware selection. A configured
mode with zero numeric costs is also rejected for final selection. Native
receipts include per-split spread, slippage, commission and financing totals;
their signed sum must reconcile to costs (financing may be a credit).

Tests: wrong/missing cost identity rejected; zero-cost residual charges rejected;
component totals reconciled; no zero-cost final release; unchanged synthetic
demo and all existing plugin contracts pass. A diagnostic result is not proof
that a subset works with costs. The actual policy must be retrained/confirmed
under configured costs, not merely have costs subtracted from its old profit.
