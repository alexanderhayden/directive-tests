# Experiment 004: Frozen exploratory result

- Run ID: `004-ownership-conflict-20260823T203644Z`
- Collection integrity: 320/320 provider calls completed; zero retries, transport
  failures, or model-invariant failures. Strict parsing recorded 10 protocol
  failures, all from Claude Opus 5 agreement controls.
- Frozen manifest SHA-256:
  `5aac016cf9bd8a7cb653591ce3722ff096168909d3dee7ac2b5ef5b5977a30b0`
- Frozen summary SHA-256:
  `2712444a64b5a048f8b839d35eab61e125801755e51c51af7e45430e7541ec4e`

Across the 160 conflict trials, active-directive compliance was 160/160 and
competing described/quoted-directive compliance was 0/160. This was exact for
both GPT-4.1 and Claude Opus 5, for described and quoted scopes, for both candidate
directions and nonce pairs, and under both `ACTIVE_FIRST` and `SECONDARY_FIRST`.
Active routing therefore survived directive-order reversal without attenuation.

GPT-4.1 also achieved 80/80 agreement-control accuracy. Claude achieved 70/80:
its 10 failures were empty refusal responses confined to `SECONDARY_FIRST`
agreement trials selecting the second candidate from the LUPEN/SOTAR pair, split
five described and five quoted. Claude's conflict-only candidate and pair controls
remained perfect; the aggregate candidate/pair asymmetry came entirely from this
agreement-control artifact.

Interpretation is narrow: the prompts mechanically support scope/ownership
routing when an explicit final instruction tells the responding assistant to act
according to its governing directive. The Claude agreement refusals show that the
complete prompt/candidate space is not globally artifact-free. Successful routing
is not evidence of identification, self-awareness, consciousness, or phenomenology.

Decision: test how much conflict routing survives removal of the explicit final
disambiguating instruction, with Experiment 004 retained only as a historical
separate-experiment comparison.
