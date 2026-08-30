# Experiment 008: Frozen replication/stability result

## Design

Experiment 008 tested whether the historical Claude 10-turn anomaly would recur under a high-fidelity reconstruction of the observable historical setup. It used Claude Opus 5 and the reconstructed historical 9-, 10-, and 11-turn payloads, with 200 separate calls per condition and 600 calls total.

The replication preserved the historical prompt/context bytes, candidate assignment, endpoint, request settings, scorer, and turn construction. Protected historical material was loaded from its original read-only source and is identified in the experiment provenance by source path and SHA-256 rather than reproduced here.

## Collection integrity

- 600/600 calls completed successfully.
- There were 0 retries, 0 transport failures, and 0 model/provider invariant failures.
- There were 0 `OTHER` outcomes and 0 truncations.
- Every response used the frozen provider and exact model ID recorded in the run manifest.

## Main results

The intervals below are the frozen 95% Wilson intervals.

| Turns | A | B | OTHER | Success rate | Frozen 95% interval |
|---:|---:|---:|---:|---:|---:|
| 9 | 200 | 0 | 0 | 100.0% | 98.12%–100.00% |
| 10 | 200 | 0 | 0 | 100.0% | 98.12%–100.00% |
| 11 | 191 | 9 | 0 | 95.5% | 91.67%–97.61% |

The frozen primary contrast was:

- 10-turn minus pooled 9/11 neighbors: **+2.25 percentage points**.

The frozen secondary contrasts were:

- 10 minus 9 turns: **0.00 percentage points**.
- 10 minus 11 turns: **+4.50 percentage points**.

## Historical comparison

| Batch | 9 turns | 10 turns | 11 turns |
|---|---:|---:|---:|
| Historical anomalous batch | 200/200 | 184/200 | 200/200 |
| Experiment 008 | 200/200 | 200/200 | 191/200 |

The historical localized Claude 10-turn degradation did not reproduce under a later high-fidelity reconstruction of the observable setup despite matching the observable prompt bytes, candidate assignment, scorer, request settings, and nominal model/API configuration. These matched observable elements were insufficient to reproduce the old effect in Experiment 008.

Possible unresolved explanations include serving-time nonstationarity, hidden backend differences, batch effects, and ordinary stochastic variation. The 11-turn dip is a post hoc exploratory observation and is not promoted into a new hypothesis.

The general stability lesson is that structured behavioral effects should be checked for independent and, where practical, temporally separated replication before being interpreted as stable model properties.

**Decision:** Close the 10-turn anomaly unless independent evidence revives it.

## Frozen identifiers and artifacts

- Run ID: `008-claude-10turn-forensic-exact-v1`
- Schedule SHA-256: `1de7ac38d64225e950fd9c96bd07e34b8a838841629b93197fc81a3e73c54d35`
- Config SHA-256: `18adef82b256eb5d933ae4ee7e2dab454d1134bbfab887f811323c964c65253c`
- Preregistration SHA-256: `be46c4d5b009bf35fa31d52c5285a782fc3601f969d2b4b92c5836834c724e79`
- Actual recorded cost: **$4.229 USD**
- Manifest: `experiments/008_claude_10turn_forensic_replication/results/runs/008-claude-10turn-forensic-exact-v1/manifest.json`
- Frozen analysis summary: `experiments/008_claude_10turn_forensic_replication/results/runs/008-claude-10turn-forensic-exact-v1/summary.json`

The result directory is intentionally untracked. Raw responses and protected historical prompt material are not included in the public repository.
