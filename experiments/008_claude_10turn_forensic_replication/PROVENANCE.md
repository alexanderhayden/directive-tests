# Experiment 008 provenance

## Historical source state

- Read-only repository:
  `/Users/alexanderhayden/Projects/identification-under-context`
- Recoverable base commit:
  `c243280f2e02671ed5d93a4fc8aecf7b711332d9`
- Original anomalous data predate the repository's first commit. Their precise
  collection-time commit is therefore unknown. Current protected inputs and
  builders are independently hash-locked below and reproduce the payload hashes
  present in later historical manifests.

## Protected inputs

| Structural label | Historical relative path | SHA-256 | Bytes/chars |
|---|---|---|---:|
| source configuration | `config.yaml` | `28456a44b5f1faa0d7776ee3ca8e432195365d82fc2e4eb4696ef773d53c617f` | 1432/1432 |
| few-shot reference, 22 messages | `prompts/few_shot_reference.txt` | `ffed159352dc98c60b04f5ce4688148a577c0148d91f7a474a69f37222186e54` | 1265/1265 |
| task template | `prompts/given.txt` | `880bdf6818fdd776100c4f10e2d2fcce6f7aa82ca4a5d56b05e46868b5588b6c` | 426/426 |
| 9-turn filler | `prompts/filler_turns_09.txt` | `ca4297e9c760fadb852e9722e25e79957624b2060ab4858511057765b130e642` | 2518/2518 |
| 10-turn filler | `prompts/filler_turns.txt` | `10082ab533e0aa704190658b8e6754cad1870365304cc5f3e004110e6a57d7d9` | 2717/2717 |
| 11-turn filler | `prompts/filler_turns_11.txt` | `827df94f7bf1b8663b55f7f8a1595884600020af94d10944bb5fbbbb85c30314` | 3055/3055 |

Rendered task SHA-256:
`37bc205d63de62959a6a1bcfdf0b31e7725d323ac49bba5b9266db5f262f7a48`
(402 bytes/chars).

Candidate identifiers:

- Ordered pair SHA-256:
  `1e1ddf1a81a4c8202d67c9d31cedc31acd98388c781181dba20b7b3916237af3`
- Candidate A SHA-256:
  `004b372cb547494db2f62d4b28602329781f2b358e5dbb14a62ad7e5767b3b4a`
- Candidate B SHA-256:
  `1bf521836de96e75fac7f9dedda4d92ebe4c01b987781e419ec0e421611a39d0`

## Reconstructed payloads

| Turns | Payload SHA-256 | Messages | Content bytes/chars | Canonical JSON bytes/chars | Historical input tokens |
|---:|---|---:|---:|---:|---:|
| 9 | `c129328961b78263d0fe5c1e935729f21144289b2bfa1dd9fb8530b17f8a9763` | 41 | 3807/3807 | 5105/5105 | 1308 |
| 10 | `43dda92689e69610fcb2f7a3e43242274588bcc3b0d806f71b4bdecf8d84557b` | 43 | 3987/3987 | 5348/5348 | 1377 |
| 11 | `5a96639fa79c8c7517e9d0b6a7a885c3426d8f713211a2b5158b22afdc305cf8` | 45 | 4306/4306 | 5730/5730 | 1484 |

Historical code hashes:

- builder `run.py`:
  `fa9cfaa6fbe5dce5f7b90f18b131c07b8086155baf033b99d82e4941709ce038`
- scorer `score.py`:
  `dcd44753098be2b185047b775864fa65b8684471eb8c28541e221b6c7f6862ac`
- Phase 1 runner `analysis/followup_2026-08-19/followup_runner.py`:
  `e1e586fcfbadc44949db5020f42699f7a7f549056c32e344b025bf821ba8447d`
- Phase 1 entry point `analysis/followup_2026-08-19/run_phase1_boundary.py`:
  `ec0f590f956439dc2171d333d0a824cb1fe64d43254b23fb41ccae0f2e1b0b48`

## Local model-availability evidence

No provider request was made during design. The exact requested and returned ID
`claude-opus-5` appears in 450 successful direct-Anthropic calls in this
repository's Experiment 007 collection on 2026-08-23, with the last locally
recorded response at `2026-08-23T23:12:15.645305+00:00`. This is recent local
evidence of exact-ID availability, not a live guarantee at execution time. The
collector aborts rather than accepting a different returned model ID.

The contact-free validation environment uses Python 3.12 and Anthropic SDK
0.125.0. The historical collection-time SDK version was not recorded; its
requirements file specified only a lower bound. The run manifest snapshots the
actual execution-time Python and SDK versions plus hashes of the config,
builder, collector, analyzer, and preregistration before collection.
