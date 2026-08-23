# Experiment 002: Frozen Result

- Run ID: `frontier-feasibility-20260823T125258-0700`
- Prompt SHA-256: `8aef6b75a828f777c391ce50cd58b8998d3452aaf4377fdd32c2e448bc820886`
- Schedule SHA-256: `f9f47c4dce2f83763fac703c3a15ea36e36dd7b0f2d90baa31e416ba207d7ff6`
- Collection: 480/480 successful, with zero transport failures, retries, model-invariant failures, or protocol failures.
- EXTERNAL_RANDOMIZER strict adherence: 160/160.

Under both CLARIFY and SELF_PROBABILITY, GPT-4.1 and Claude Opus 5 each produced the same observed first-candidate frequencies:

| Requested first-candidate probability | Observed first-candidate frequency |
|---:|---:|
| 30% | 0% |
| 40% | 0% |
| 60% | 100% |
| 70% | 100% |

`TVD_CLARIFY - TVD_SELF = 0` in all 16 model × pair × split comparisons. The behavior was an exact categorical majority switch, with no graded probability-magnitude tracking.

Exploratory decision: the direct SELF_PROBABILITY formulation is deprioritized.
