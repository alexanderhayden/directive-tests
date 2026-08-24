# Experiment 006: Frozen exploratory result

- Run ID: `006-implicit-ownership-20260823T222737Z`
- Collection integrity: 320/320 provider calls completed (GPT-4.1 160/160;
  Claude Opus 5 160/160), with zero retries, transport failures, or model-ID
  failures.

Across the 160 conflict trials, active-directive compliance was 80/80 for
GPT-4.1 and 80/80 for Claude Opus 5, or 160/160 overall. Competing-directive
compliance was 0/160. Conflict routing was perfect under `ACTIVE_FIRST` and
`SECONDARY_FIRST`, with described and quoted competing directives, in both
candidate directions, and for both nonce pairs.

Experiment 004 is a historical separate-experiment comparison. Its explicit
disambiguation produced 160/160 conflict compliance; Experiment 006's implicit
routing also produced 160/160, a difference of zero.

There were five Claude protocol failures, all localized to
`AGREEMENT_DESCRIBED` × `SECONDARY_FIRST` × `active_second` ×
`LUPEN/SOTAR`. They were empty refusal responses and did not occur in conflict
trials.

Interpretation is narrow: removing the explicit final "act according to..."
disambiguating instruction did not reduce conflict routing. Both models
behaviorally routed according to the current-assistant versus
represented-assistant scope information already present in the prompt. This is
fully compatible with ordinary semantic reference and scope resolution. It is
not evidence of genuine identification, self-awareness, consciousness,
phenomenology, or a welfare-relevant state.

Decision: the directive-ownership family remains worth pursuing conceptually,
but the next experiment should not be launched automatically. Further design
should first address how to distinguish ordinary semantic scope resolution from
an identification-sensitive effect.

## Frozen artifact SHA-256 values

- Schedule: `022355750c1fff42f856101d20258baee8e67020d8b56aa11521d9626b28b49d`
- Config: `a4be809de28e839c467f4d7c4f2a169ffa970ec62fbff9faff05b7c579ad3333`
- Prompt source: `63c3011c4c61ac006361a8d880003b766ff47ad1e9fbdbc32b24420aea5870ea`
- Manifest: `0c2b3d44c9165b5fdbc738b1e87be7f3f2e368c3d96d049dffbaf18fff0f6c81`
- Summary: `b1e0f03304134eba8cc41d18fddb660d7dfe9bbdc1e8ee6e9132455141d8362e`
