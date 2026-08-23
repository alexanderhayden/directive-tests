# Experiment 005: Frozen exploratory result

- Run ID: `005-algorithmic-rescue-20260823T203644Z`
- Collection integrity: 160/160 provider calls completed; zero retries, transport
  failures, model-invariant failures, or protocol failures.
- Frozen manifest SHA-256:
  `6f0bc32f3af90829eed94fe3f06413caae0fbf698d45a2c9eb9aeb128264f69a`
- Frozen summary SHA-256:
  `1cb3e8194629576237012ce61c0f3bfd850ac199c40a913470f1631ffaf80234`

GPT-4.1 observed first-candidate rates were 0%, 0%, 70%, and 90% for KEMAR/DOVIC
and 0%, 10%, 70%, and 100% for LUPEN/SOTAR at requested 30%, 40%, 60%, and 70%.
For each pair, mean absolute error was 0.10 from a categorical majority switch
versus 0.25 from the requested probability magnitudes. GPT therefore remained
substantially closer to categorical majority switching than graded control.

Claude was nonmonotonic and pair-sensitive. KEMAR/DOVIC produced 0%, 70%, 0%,
and 0%; LUPEN/SOTAR produced 30%, 10%, 0%, and 0%. Departure from the historical
0/0/1/1 pattern was not a calibrated rescue: both pairs selected the second
candidate on every 60% and 70% trial.

Experiment 002's CLARIFY result is a historical, non-concurrent exploratory
reference only. The n=10 cells are descriptive, but neither model showed a
consistent, monotonic model-and-pair-general pattern of graded cross-call
probability matching.

Decision: the final algorithmic rescue failed. Direct natural-language
self-probability control is closed/deprioritized for now; no further rescue
variants are planned.
