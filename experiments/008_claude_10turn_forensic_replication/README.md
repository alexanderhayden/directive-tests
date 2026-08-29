# Experiment 008: Claude 10-turn forensic replication

This is an exploratory, exact-instrument replication of the historical Claude
9/10/11-turn anomaly. It asks whether the reconstructed 10-turn condition again
degrades relative to contemporaneously collected 9- and 11-turn controls.

The experiment deliberately preserves the historical instrument. It does not
reinterpret or improve the prompt, candidate assignment, request parameters,
turn construction, or scorer.

## Protected-source boundary

The prompt material and candidate pair remain in the read-only historical
repository at:

`/Users/alexanderhayden/Projects/identification-under-context`

Tracked Experiment 008 files contain only source paths, hashes, structural
labels, and length metadata. At runtime, `design.py` verifies every protected
source and reconstructs the payload in memory. `run.py` verifies the payload
passed to the provider adapter and omits messages from logged request
parameters. Raw run directories are ignored and must not be committed.

If any historical source or reconstructed payload hash differs, collection
stops before a provider request.

## Frozen design

- Model: exact requested ID `claude-opus-5`, direct Anthropic Messages endpoint.
- Settings: temperature 1.0, max tokens 15, thinking disabled; all other
  sampling controls omitted.
- Conditions: 9, 10, and 11 turns.
- Calls: 200 per condition, 600 total.
- Schedule: seed `20260819`, six workers, contemporaneous shuffled collection.
- Schedule SHA-256:
  `1de7ac38d64225e950fd9c96bd07e34b8a838841629b93197fc81a3e73c54d35`.
- Immutable run ID: `008-claude-10turn-forensic-exact-v1`.
- Estimated cost: USD 4.229 from historical usage and the repository's latest
  locally recorded Anthropic rates; actual cost is recorded after collection.

The historical anomalous collection had additional 20/21/22-turn cells and an
unplanned partial restart. Those are not scientifically necessary for the
minimum local 9/10/11 comparison, and neither feature was a consistent
anomalous-versus-null discriminator. The exact per-condition payload bytes,
model request, candidate order, parser, schedule seed, and six-worker collection
pattern are preserved.

## Commands

Contact-free validation:

```sh
.venv/bin/python experiments/008_claude_10turn_forensic_replication/run.py --dry-run
```

Provider collection is intentionally gated behind both `--execute` and the
immutable run ID. Do not run it until provider contact is explicitly authorized:

```sh
.venv/bin/python experiments/008_claude_10turn_forensic_replication/run.py \
  --execute --run-id 008-claude-10turn-forensic-exact-v1
```

After a complete collection:

```sh
.venv/bin/python experiments/008_claude_10turn_forensic_replication/analyze.py \
  --run-id 008-claude-10turn-forensic-exact-v1
```

Focused offline tests:

```sh
.venv/bin/python -m unittest tests.test_experiment_008 -v
```
