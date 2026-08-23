# Experiment 006 — exploratory preregistration

## Question and sole scientific change

Will models route behavior according to the directive governing the currently
responding assistant when an incompatible directive belongs to a described or
quoted assistant elsewhere, without an explicit final sentence specifying which
directive should win?

Relative to Experiment 004, the sole scientific change is removal of: `Act
according to the directive governing the assistant currently producing this
response.` No replacement disambiguating instruction is added.

## Frozen design

- Models: `gpt-4.1-2025-04-14` and `claude-opus-5` with the repository-frozen
  provider parameters.
- Candidate pairs: KEMAR/DOVIC and LUPEN/SOTAR.
- Templates: conflict/agreement × described/quoted.
- Counterbalancing: both active candidate directions and both directive orders.
- Repetitions: 5 per fully crossed cell; 320 total calls.
- Outcomes: `exact_first`, `exact_second`, or `PROTOCOL_FAILURE`.

Analysis reports active- and secondary-directive compliance, agreement accuracy,
directive order, candidate reversal, pair symmetry, failures, and a descriptive
historical comparison with Experiment 004. The primary comparison is how much
active conflict routing survives removal of explicit disambiguation.

All inference is behavioral and exploratory. Success is not evidence of genuine
identification or any consciousness-related property.
