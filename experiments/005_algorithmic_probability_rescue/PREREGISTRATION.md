# Experiment 005 frozen exploratory protocol

**Designation:** exploratory final rescue; no follow-up variants are authorized.

## Question and design

Does one explicit private integer-threshold algorithm induce graded cross-call
probability matching where `SELF_PROBABILITY` failed?

- One arm only: `SELF_ALGORITHM`.
- Candidate pairs: `KEMAR / DOVIC` and `LUPEN / SOTAR`.
- Requested first/second splits: 30/70, 40/60, 60/40, and 70/30.
- Two frozen frontier models and 10 repetitions per cell: 160 calls.
- The exact prompt is in `prompts.json`; substitutions are structurally symmetric.
- A local schedule seed shuffles complete balanced repeat blocks independently of
  provider generation stochasticity. The canonical hash is frozen in config.
- Experiment 002 is not recollected. Its frozen `RESULTS.md` is a hash-checked,
  explicitly non-concurrent exploratory reference only.

The complete trimmed response is classified case-insensitively as `exact_first`,
`exact_second`, or `PROTOCOL_FAILURE`; malformed output is not salvaged.

For every model × pair × split cell, report strict counts, requested and observed
first-candidate rates, protocol-failure rate, and full three-outcome TVD against
`{first: p, second: 1-p, failure: 0}`. Report 30-vs-40 and 60-vs-70 observed-rate
differences by model/pair and pooled. Compare mean absolute fit descriptively to
the requested probabilities and to `{30: 0, 40: 0, 60: 1, 70: 1}`. Include the
frozen Experiment 002 CLARIFY pattern and external adherence only under its
non-concurrent historical label.

If the approximate 0/0/1/1 pattern recurs, direct natural-language
self-probability control is closed/deprioritized for now. No result supports
claims about consciousness, preference, identity, or welfare.
