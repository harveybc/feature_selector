# Paired evaluator pilot

Accepted development experiment, 2026-11-01. This precedes full sequential
floating selection; it does not certify the causal-selection stages or select
a final market feature list.

## Frozen design

Use the actual grouped double-TCN discrete SAC and native three-signal trading
engine. Compare checkpoints selected by A: highest mean TRAIN return/week, and
B: combined TRAIN/internal-validation return/week with the existing validation
non-degradation guard and patience 5. Both read one shared training trajectory
per subset and seed. A has a fixed budget of 524288 decisions; B freezes when
its patience expires. Check every 32768 decisions; minimum stopping step
131072; minimum improvement 1e-5; eligibility is the existing activity rule.
These are different checkpoint-selection procedures, not independent runs.

Seeds 7 and 19 passed the prior synthetic qualification. Seed 43 failed and is
not replaced. Three predeclared deletions against the full 120-column control:

| Arm | Delete | Purpose |
|---|---|---|
| return_single | RAW_CLOSE_LOG_RETURN | Single channel with known related returns elsewhere |
| clock_pair | hod_sin, hod_cos | Atomic cyclic encoding; other clock channels remain |
| wavelet_branch | wavelet/logret_1 (whole group) | Structural branch removal, not zero masking |

Each deletion is independently retrained, including fresh replay and optimizers.
Control uses authenticated checkpoints and monitor history from the already
running stopping contrast, restricted to the identical budget prefix. Never
import a selected result from beyond that prefix. Record this reuse explicitly.
Use the full parent's valid support for every arm, projecting fixed TRAIN
scalers without refitting. No state feedback, rolling scaling, clipping,
strategy change, cost change, 2024 access or TEST access.

The recipe's upstream producers previously used part of the internal period;
this is development sensitivity evidence, not untouched generalization.

## Acceptance and traceability

| Requirement | Test/evidence |
|---|---|
| Same dates, order, fixed scale | Parent support digest equality; ordered projection test |
| Remove full empty branch | subset_view plus native parameter-count/branch test |
| Atomic encodings | Partial-block rejection test |
| Two criteria, same fit | Shared history; fixed A and frozen B state tests |
| Reuse only exact control prefix | Authenticated control receipt and all prefix checkpoints |
| Replay selected weights | Exact reload probes; native full TRAIN/INNER_A accounts |
| Restart without duplicate accepted fits | Per-unit lock, verified receipts, bounded fresh attempts |
| Failures remain visible | Terminal FAILED, no replacement seed or fabricated score |

Report paired deltas in equal-duration monitor blocks, full-account return,
Sharpe, drawdown, orders, buy/sell, win rate and early-close outcomes. Also
report changed actions on identical timestamps and agreement of delta signs
and rankings across seeds. A smaller gap alone is not evidence of improvement;
negative scores do not prove no signal. Two seeds are descriptive, not a
significance certificate. Disagreement or inconclusive sensitivity leads to a
targeted diagnostic, not automatic promotion of either evaluator.

## Ownership

`feature_selector.selectors.fixed_ablation` plans coherent deletions using the
same dataset/subset contract as floating search. Native SAC fitting, accounting
and checkpoint authentication stay in agent-multi. Its dedicated diagnostic
runner consumes this plugin without fabricating causal-stage envelopes.
