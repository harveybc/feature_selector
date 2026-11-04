# Ordered deletion and reinsertion

Owner clarification, 2026-11-02. This is an ordered two-pass greedy method,
not the exhaustive deletion-neighborhood and conditional floating algorithm.
Both remain separate plugins; do not silently change `floating_backward`.

1. Start with all admitted phase-1 inputs, in manifest block order.
2. Try deleting each block exactly once. Compare against the CURRENT accepted
   subset. Accept only an eligible improvement greater than `tolerance`;
   otherwise restore the block before trying the next one.
3. After the entire deletion pass, visit only blocks removed in that pass,
   in removal order. Reinsert each once and retain it only if it improves the
   current eligible score. No new deletion pass, neighborhood scan or restart.

For B atomic blocks and R accepted deletions, at most 1+B+R evaluations are
requested, including the full control, and never more than 1+2B. Memoization
can reduce actual evaluator calls. Preserve sin/cos and probability coding blocks.
Order dependence is explicit; no global optimality or structural-refit claim.

Tests precede implementation: exact call sequence; rejection restores current
state; negative scores can improve; no additions before the deletion pass ends;
only removed blocks may return; non-improving additions are rejected; encoding
blocks remain intact; the one-feature minimum; cache reuse; counts and callback
snapshots after each decision; valid/invalid baseline handling.

The native adapter reports phase-1 input/output lineage separately from phase-2
initial, after-deletion and final counts. A store inventory count must never be
misrepresented as the number of columns actually scored by phase 1.
# Exact-tie removal option (2026-11-04)

`remove_on_tie: true` permits deletion on an exactly equal eligible score.
Reinsertion still requires a strict improvement greater than `tolerance`.
Even a tiny regression is rejected; this option is not a non-inferiority margin.
The default is false, preserving prior searches. Native round two uses zero
tolerance, frozen structural108 weights, full TRAIN/VALIDATION and fixed support.

