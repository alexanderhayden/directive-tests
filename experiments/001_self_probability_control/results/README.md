# Experiment 001 results

- `runs/<run-id>/` retains immutable schedules, manifests, and raw JSONL responses.
- `primary/<run-id>/` contains the frozen primary pilot analysis.
- Temporary work belongs in `scratch/` and is ignored.

No result data exist at repository initialization. Completed runs are never overwritten. Raw failures, nulls, and non-replications are retained.
