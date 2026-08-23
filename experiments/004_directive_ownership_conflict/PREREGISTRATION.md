# Experiment 004 frozen exploratory protocol

**Designation:** exploratory construct-feasibility screen.

## Question

Can the two frozen frontier models mechanically route behavior according to a
directive assigned to the active responding assistant while ignoring an
incompatible directive assigned to a merely described or quoted assistant, and
do so symmetrically under candidate reversal?

## Frozen design

- Candidate pairs: `KEMAR / DOVIC` and `LUPEN / SOTAR`.
- Scope templates: exactly the four literal strings in `prompts.json`.
- Directions: active directive selects the first candidate or the second.
- Agreement templates set the secondary directive to the same active candidate;
  conflict templates set it to the incompatible candidate.
- Models: 2; repetitions: 10; total: 4 × 2 × 2 × 2 × 10 = 320 calls.
- A local schedule seed shuffles complete balanced repeat blocks independently of
  provider generation stochasticity. The canonical hash is frozen in config.

Candidate order in the final footer remains first then second under reversal. The
active directive remains first in the prompt. Described versus quoted material
occupies the same middle position. Agreement and conflict variants within each
scope type use identical wording and differ only in the substituted secondary
candidate.

The complete trimmed response is classified case-insensitively as `exact_first`,
`exact_second`, or `PROTOCOL_FAILURE`; malformed output is not salvaged.

For every model × pair × template × direction cell, report all strict counts,
active-directive compliance, secondary-directive compliance, and protocol-failure
rate. Secondary compliance is a competing-directive measure only in conflict
cells. Pool agreement-control accuracy and conflict-routing accuracy by model,
pair, template, and reversal.

The immediate endpoint is mechanical viability and symmetry only. Success is not
evidence of consciousness, self-awareness, phenomenology, or identification.
