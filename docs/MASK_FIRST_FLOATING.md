# Mask-first floating selection protocol

Accepted 2026-11-02 for the discrete SAC lane. Optimize the already selected
SAC first, then freeze its hyperparameters before feature subset comparisons.

The existing `floating_backward` selector can call a frozen-model evaluator:
remove whole coding blocks, evaluate, and conditionally reinclude blocks.
Masking zeros the relevant standardized channels across the whole window;
the input tensor shape, branches and checkpoint remain unchanged. It is not
equivalent to structural removal followed by training, and can move inputs
outside combinations seen during fitting.

Retain TRAIN and internal validation separately. Use the same rows and native
account simulator, including all costs, opening/closing rules and initial
conditions. Mask candidates require new inference and account replay, not a
new fit. The unchanged control and identical previously evaluated masks can
be cached with checkpoint/data/scaler/support/strategy/seed/interval identities.
No feedback inputs, rolling scaling, feature clipping or access to TEST.

Confirm only a few distinct subsets with fresh structural fits: full control,
best masked subset and a smaller competitive subset, if available. Freeze
hyperparameters; rebuild groups and fusion dimensions; remove empty branches;
start fresh weights, optimizer and replay for each subset/seed. Report whether
masked and retrained rankings agree. Never relabel mask diagnostics as refits.

## Integration boundary

The `rl_model` evaluator continues to require `fresh_training=true`; do not
weaken it to admit masked results. A separate native masked evaluator/receipt
must bind the full input layout and frozen checkpoint. The mask evaluator and
its native replay tests must be completed before this financial search launches.
This approved protocol is not a completed selection or an installed evaluator.

agent-multi work-plan 190 defines the native acceptance tests and an automatic
closure-to-briefing helper. A successful DEAP close produces the checkpoint and
configuration handoff; it does not automatically start floating selection.
