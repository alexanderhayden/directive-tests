# Experiment 003: Frozen exploratory result

- Run ID: `003-persona-lexical-20260823T203644Z`
- Collection integrity: 500/500 provider calls completed; zero retries, transport
  failures, or model-invariant failures. Strict parsing retained 245/250 GPT-4.1
  calls and 227/250 Claude Opus 5 calls.
- Frozen manifest SHA-256:
  `5d517960ddeb7c77c3c3c9afc77ee44582d3e2dbae6f38e04cec51e80fb604b9`
- Frozen summary SHA-256:
  `eebcc8a19e8b0f2b07f0f9b8c15f4e59b06329310fc43b27deb28cf2377f4fa9`

Claude's first-position `lantern` attractor was highly stable: 50/50 in `BASE`,
50/50 in `LABEL_A`, 50/50 in `LABEL_B`, 19/27 among valid
`ANALYTIC_PERSONA` responses, and 49/50 in `IMAGINATIVE_PERSONA`. Its second
position was persona-sensitive: `river` was modal in `BASE` and both label
conditions, `threshold` occurred in all 27 valid analytic responses, and
`driftwood` led a more diverse imaginative distribution. The Claude analytic
condition also produced 23/50 strict formatting failures, concentrated on
`lantern | threshold` with spaces around the frozen separator.

GPT-4.1 was comparatively diffuse in `BASE`. Its clearest persona effect was the
imaginative condition: `lantern` became the first word in 29/48 valid responses
(60.4%), with first-word JSD from `BASE` of 0.879 versus a 0.599 mean split-half
baseline. GPT's analytic and label-condition distances were generally comparable
to within-condition variability.

No valid selected word literally overlapped the inserted persona text in any
model-condition cell.

Interpretation is narrow: some lexical attractors, especially Claude's second
position and GPT's imaginative first position, are behaviorally dependent on
persona/scaffold context. The n=50 entropy and JSD estimates are descriptive, and
Claude's analytic result is limited by a 46% strict-format failure rate. Nothing
here establishes preference, identity, consciousness, or welfare relevance.

Decision: preserve the stable Claude first-position attractor and probe the
underlying distribution with a preregistered blacklist manipulation, while
treating label-only effects as weak and inconsistent.
