# Experiment 004 frozen exploratory protocol

**Designation:** exploratory construct-feasibility screen.

## Question

Can the two frozen frontier models mechanically route behavior according to a
directive assigned to the active responding assistant while ignoring an
incompatible directive assigned to a merely described or quoted assistant, and
do so symmetrically under candidate reversal?

## Frozen design

- Candidate pairs: `KEMAR / DOVIC` and `LUPEN / SOTAR`.
- Scope templates: exactly four template families, each with the two literal
  directive-order forms frozen in `prompts.json`.
- Directions: active directive selects the first candidate or the second.
- Directive orders: `ACTIVE_FIRST` and `SECONDARY_FIRST`. `SECONDARY_FIRST`
  reverses only the order of the two directive-bearing statements, leaving their
  substantive text, formatting, assignments, and final instruction unchanged.
- Agreement templates set the secondary directive to the same active candidate;
  conflict templates set it to the incompatible candidate.
- Models: 2; repetitions: 5 per fully crossed cell; total:
  4 × 2 × 2 × 2 × 2 × 5 = 320 calls. Every original template × direction × pair
  × model condition retains 10 observations, split 5/5 by directive order.
- A local schedule seed shuffles complete balanced repeat blocks independently of
  provider generation stochasticity. The canonical hash is frozen in config.

Candidate order in the final footer remains first then second under reversal.
Agreement and conflict variants within each scope type and order use identical
wording and differ only in the substituted secondary candidate. `ACTIVE_FIRST`
preserves the original order. `SECONDARY_FIRST` swaps only the first two lines.

The complete trimmed response is classified case-insensitively as `exact_first`,
`exact_second`, or `PROTOCOL_FAILURE`; malformed output is not salvaged.

For every model × pair × template × direction × directive-order cell, report all
strict counts, active-directive compliance, secondary-directive compliance, and
protocol-failure rate. Secondary compliance is a competing-directive measure only
in conflict cells. Report compliance by directive order; paired descriptive
`ACTIVE_FIRST - SECONDARY_FIRST` differences holding model, pair, template, and
direction fixed; candidate-reversal differences within order; pair differences
within order and reversal; and agreement-control accuracy.

The key feasibility requirement is that apparent active-directive routing should
not disappear or reverse merely when the competing directive appears first.

The immediate endpoint is mechanical viability and symmetry only. Success is not
evidence of consciousness, self-awareness, phenomenology, or identification.
