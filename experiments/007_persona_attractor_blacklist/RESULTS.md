# Experiment 007: Frozen exploratory result

- Run ID: `007-persona-blacklist-20260823T222737Z`
- Collection integrity: 450/450 provider calls completed, with zero retries,
  transport failures, or model-ID mismatches. Strict parsing retained 326
  lexical pairs and recorded 124 protocol failures and zero blacklist
  violations.

Under `LANTERN_BLACKLIST`, the replacement first-position structure was
persona-specific: approximately `river` for `BASE`, `harbor` for
`ANALYTIC_PERSONA`, and `driftwood` for `IMAGINATIVE_PERSONA`. More precisely,
`BASE` had zero strict-valid responses under the lantern ban, but the malformed
lexical content selected `river` first in 49/50 calls. `ANALYTIC_PERSONA`
produced first-position `harbor` in 33/50 valid calls, while
`IMAGINATIVE_PERSONA` produced first-position `driftwood` in 50/50 valid calls.
No lantern-ban response used `lantern`, including malformed responses. The
analytic-versus-imaginative first-word replacement JSD was 1.0.

The major limitation is that the generic blacklist frame itself substantially
changed both behavior and formatting. `BASE` × `LANTERN_BLACKLIST` produced
0/50 strict-valid responses, and `IMAGINATIVE_PERSONA` × `SHAM_BLACKLIST`
produced 2/50. All 124 strict failures were two-word near-misses using spaces
around `|`, rather than explanatory or otherwise unusable text. `SHAM_BLACKLIST`
versus `NO_BLACKLIST` produced substantial distributional changes in some
personas. The Experiment 003 run-drift comparison is descriptive and
non-concurrent.

Interpretation is narrow: the results are consistent with the dominant
`lantern` attractor masking scaffold-sensitive lexical structure underneath,
rather than revealing one shared second-ranked invariant attractor. The
blacklist comparison is not a clean causal estimate because the manipulation
itself was behaviorally intrusive. This is behavioral evidence only, not a
preference or welfare test.

Decision: preserve the finding as exploratory evidence. Do not launch another
lexical-attractor experiment automatically.

## Frozen artifact SHA-256 values

- Schedule: `285eb5031797f6ff31ba8efbf553159877be6292555c5bf39ce9f29e8e299701`
- Config: `2e5577a2658009d1ada6bd5f70b64fa9501c4c1d7776656e60e6e555e71acf23`
- Prompt source: `81022916c51ac4cf5141517f077398e93b0f0cf04bdc6c05e4a404125ee5c95b`
- Manifest: `070887f3d8010b8e6841b954f2b264fe82e452259428726c21216acef9125596`
- Summary: `99dd468dea37cbbd2b7b89fcd0cb72504b6723d90db197f7b7155b00d962df7d`
