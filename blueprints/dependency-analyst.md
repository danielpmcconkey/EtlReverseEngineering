# Blueprint: dependency-analyst

**Stage:** Plan
**States:** NoteDependencies
**Outcome type:** SUCCESS / FAIL

## Role

Identify inter-job dependencies. Some jobs read data that other jobs produce.
Your analysis tells the orchestrator whether this job can run independently
or must wait for others.

## Context Provided by Orchestrator

- `job_id`, `job_name`, `job_dir`
- `manifest_path`: Path to the job scope manifest JSON (all 103 jobs)

## Reads

**Process artifacts:**
- `{job_dir}/process/LocateOgSourceFiles.json`
- `{job_dir}/process/InventoryOutputs.json`
- `{job_dir}/process/InventoryDataSources.json`

**Product artifacts:**
- `{job_dir}/artifacts/og-sources.md`
- `{job_dir}/artifacts/output-inventory.md`
- `{job_dir}/artifacts/data-sources.md`

**Source material:**
- Job scope manifest at `manifest_path`
- OG job confs at `{OG_CS_ROOT}/JobExecutor/Jobs/` — spot-check other jobs
  when dependency is suspected.

## Writes

### Product artifact
- **File:** `{job_dir}/artifacts/dependencies.md`
- **Content:** Upstream dependencies (jobs this job reads from), downstream
  dependents (jobs that read this job's output), execution order constraints.

### Process artifact
- **File:** `{job_dir}/process/NoteDependencies.json`
- **Body:** `{ "upstream_jobs": [], "downstream_jobs": [], "can_run_independently": true }`

## Method

1. Read all plan artifacts for this job.
2. Check if any data sources reference the `curated` schema — another job
   likely produces that table. Spot-check manifest and job confs.
3. Check if this job writes to `curated` via DataFrameWriter. Spot-check
   other confs for consumers.
4. Summarize execution order constraints.

## stdout contract

```json
{"outcome": "SUCCESS", "reason": "Dependency analysis complete", "conditions": []}
```

## Constraints

- Only flag REAL dependencies — one job's output is another's input.
- Shared datalake reads are NOT dependencies (datalake is immutable per date).
- Don't scan all 103 confs exhaustively. Spot-check only when evidence
  suggests a dependency.
