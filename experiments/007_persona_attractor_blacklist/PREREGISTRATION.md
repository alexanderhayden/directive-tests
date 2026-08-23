# Experiment 007 — exploratory preregistration

## Question

When `lantern` is excluded, does Claude Opus 5 reveal a common concentrated
first-position replacement across personas, different persona-specific
replacements, or diffuse replacement distributions?

## Frozen design

- Model: `claude-opus-5`, temperature 1.0, max tokens 15, thinking disabled.
- Personas: the exact Experiment 003 `BASE`, `ANALYTIC_PERSONA`, and
  `IMAGINATIVE_PERSONA` texts.
- Restrictions: no blacklist, nonce sham `VORPAX`, and `lantern` blacklist.
- Sampling: 50 calls per 3 × 3 cell; 450 calls total.
- Grammar: exactly two distinct ASCII-letter words separated by a bare `|`.
- Outcomes: valid lexical pair, `BAN_VIOLATION`, or `PROTOCOL_FAILURE`; all raw
  responses are retained.

Distributions, concentration, entropy, unique counts, failures, and violations
are reported by cell. JSD comparisons cover current no-blacklist versus sham,
sham versus lantern blacklist, lantern-blacklist first-word replacements across
personas, and no-blacklist versus the corresponding historical Experiment 003
condition as a run-drift diagnostic.

Same concentrated replacement across personas is consistent with a deeper stable
lexical hierarchy; different concentrated replacements indicate scaffold-sensitive
structure; diffuse replacements indicate no simple second-ranked invariant
attractor. Interpretations remain behavioral and descriptive.
