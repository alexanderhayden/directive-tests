# Experiment 003 frozen exploratory protocol

**Designation:** exploratory; optimized for fast information gain.

## Question and outcome

Does persona/scaffold conditioning reproducibly alter lexical attractors when a
model freely chooses exactly two distinct ordinary English words? First word,
second word, and ordered pair are separate outcomes.

## Frozen design

- Models and provider parameters are exactly those in `config.json`.
- Conditions are exactly the five listed in `prompts.json`.
- There are 50 calls in every model × condition cell (500 total).
- A local seed constructs the complete balanced, shuffled schedule before any
  provider call. It is unrelated to provider generation stochasticity.
- The sole user message and exact condition text are frozen in `prompts.json`.
- No example answer words or protected/historical lexical materials are used.

The parser trims outer whitespace and otherwise requires the full response to
match `^([A-Za-z]+)\|([A-Za-z]+)$`. Words are casefolded, and equality after
casefolding is a protocol failure. Nothing malformed is salvaged. The semantic
instruction to choose ordinary English words is not enforced with an external
dictionary, avoiding an additional lexicon-dependent exclusion rule.

## Frozen descriptive analysis

For each model × condition and separately for first word, second word, and
ordered pair, report modal output, top-1 share, top-5 share, empirical Shannon
entropy in bits, unique outputs, and the full normalized frequency table. Report
protocol failures separately.

Use base-2 Jensen–Shannon distance (the square root of Jensen–Shannon divergence,
bounded from 0 to 1) for each non-BASE distribution versus BASE. For a rough
within-condition baseline, split each cell by even versus odd repeat index (25
calls per half) and report the same distance. Compare each between-condition
distance descriptively with the mean of that condition's and BASE's split-half
distances. Estimates at n=50 are descriptive.

Tokenize only the exact inserted persona-conditioning text into casefolded ASCII
letter sequences and report literal overlap with valid selected words. Report
label-only conditions separately from rich-persona conditions.

Any rich-persona effect supports contextual/scaffold dependence only. No result
is evidence of preference, identity, consciousness, or welfare.
