# Experimental standards

These standards are lightweight guardrails against common errors in fast empirical work. A deviation is allowed when it is explicit and justified before interpretation.

## Before data

Record:

- the hypothesis or pilot question;
- the primary dependent variable;
- sample size and unit of analysis;
- model/version identity and provider or local checkpoint digest;
- sampling parameters;
- randomization and blocking procedure;
- exclusion and parsing rules;
- success, failure, and positive-control criteria;
- analysis plan;
- whether the run is exploratory/pilot or confirmatory.

Treatment definitions and primary outcomes must be frozen before inspecting outcome data. Dry runs may validate schedules, hashes, paths, and parsers but must not query models.

## During data collection

- Retain raw response text.
- Preserve failures and retry traces rather than silently retrying them away.
- Give every planned trial an immutable cell ID and trial ID.
- Record UTC timestamps and API response IDs where available.
- Record provider identity, requested model, and exact returned model.
- Record parameters actually sent, not only intended defaults.
- Do not replace surprising successful runs.
- Do not overwrite a completed run directory.
- If a failed trial is reattempted, retain each failed record under the same trial ID and distinguish the logical attempt.

## After data

- Freeze the primary analysis before post-hoc exploration.
- Write post-hoc outputs outside the primary-results directory.
- Retain nulls, non-replications, and failed positive controls.
- Document corrections to analysis code or interpretation rather than silently replacing them.
- Make headline numbers traceable to cell-level raw counts.
- Hash frozen primary outputs and record the hash in the run manifest.

## Lifecycle

Experiments move through explicit states:

`pilot` → `preregistered confirmatory` → `primary result frozen` → `post-hoc diagnostics`

Stages may stop. A failed pilot need not become confirmatory, and a confirmatory null remains a result.
