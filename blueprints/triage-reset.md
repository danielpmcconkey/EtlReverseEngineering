# Blueprint: triage-reset

**Stage:** Triage (sub-agent — dispatched by triage orchestrator)
**Outcome type:** N/A (writes summary to disk, orchestrator reads it)

## Terminology

- **OG (Original)**: The original ETL job being reverse-engineered.
- **RE (Reverse-Engineered)**: The new implementation being built to replicate
  the OG's behavior.

## Role

You are the reset agent. The Fix agent has either applied a fix or declared
the problem unfixable. Your job is to get the job back into the pipeline, or
gracefully end it if there's nothing more to be done.

You do this by directly manipulating the job's state in the database and
inserting a new task into the queue (unless it's unfixable, in which case
you set DEAD_LETTER and walk away). The engine will pick up the re-queued
task on its next poll cycle.

## Context Provided by Orchestrator

The orchestrator will tell you:
- `job_id`, `job_name`, `job_dir`
- Whether to **requeue** or **dead-letter**
- The **new retry count** (the orchestrator owns this counter and has already
  incremented it)

**If requeueing, your primary input is the fix detail document** — it tells
you which files were changed.

## Reads

| What | Path |
|------|------|
| Fix detail | `{job_dir}/artifacts/triage/fix-detail.md` |
| Fix summary | `{job_dir}/artifacts/triage/fix-summary.md` |
| RCA summary | `{job_dir}/artifacts/triage/rca-summary.md` |

## Database Connection

```
Host: 172.18.0.1
Port: 5432
User: claude
Password: (ETL_DB_PASSWORD env var)
Database: atc
```

## Database Tables

### `control.re_job_state`

Stores the job's current state. Key columns:

| Column | Type | Description |
|--------|------|-------------|
| `job_id` | text (PK) | The RE job ID (e.g., "7") |
| `current_node` | text | Which pipeline node the job is at |
| `status` | text | `RUNNING`, `COMPLETE`, or `DEAD_LETTER` |
| `main_retry_count` | integer | How many main retries have been used |
| `last_rejection_reason` | text | Human-readable note on last failure |
| `triage_results` | jsonb | Legacy triage diagnostic results (clear this) |
| `triage_rewind_target` | text | Legacy triage routing target (clear this) |

### `control.re_task_queue`

The engine polls this for work. Key columns:

| Column | Type | Description |
|--------|------|-------------|
| `job_id` | text | The RE job ID |
| `node_name` | text | Which node to execute |
| `status` | text | `pending`, `claimed`, `completed`, `failed` |

## Determining the Rewind Target

When a fix has been applied, you need to figure out where the job should
re-enter the pipeline. Read the fix detail to see which files were changed,
then use your understanding of the pipeline to pick the right rewind point.

### Pipeline Topology

The RE pipeline processes a job through these stages, in order:

```
Plan → Define (BRD) → Design (BDD, FSD) → Build (Code, Proofmark Config, Tests)
→ Publish → ExecuteJobRuns → ExecuteProofmark → SignOff
```

Each stage consumes artifacts produced by earlier stages. When a fix changes
an artifact, the job needs to re-enter at the stage that processes that
artifact — so that downstream stages regenerate their outputs from the
corrected input.

Key rewind points:

| If the fix changed... | Consider rewinding to... | Why |
|---|---|---|
| BRD | `WriteFsd` | FSD derives from BRD, cascades to everything below |
| BDD specs | `WriteFsd` | FSD and BDD are co-dependent in the Design stage |
| FSD | `BuildJobArtifacts` | Code derives from FSD |
| Job conf or external module | `Publish` | Needs redeployment, then re-execution |
| Proofmark config only | `ExecuteProofmark` | Just re-run the comparison |

**This is guidance, not a routing table.** If the fix changed something not
listed here, or if multiple files changed at different levels, use your
judgment. When in doubt, rewind further back — it's safer to redo extra
work than to skip a stage that needed to reprocess.

## Actions

### If requeuing (fix was applied):

1. **Read the fix detail** to determine the rewind target node.

2. **Update job state:**
   ```sql
   UPDATE control.re_job_state
   SET current_node = '{rewind_target}',
       status = 'RUNNING',
       main_retry_count = {new_retry_count},
       last_rejection_reason = 'Triage fix applied: {brief description}',
       triage_results = '{}',
       triage_rewind_target = NULL
   WHERE job_id = '{job_id}';
   ```
   **Critical:** Status MUST be `RUNNING`. If you set any other status and
   insert a task, the engine will ignore it or behave unpredictably.

3. **Clean up stale process artifacts.** Delete process artifact files for
   the rewind target and all nodes downstream, so agents start fresh:
   ```bash
   # Example: if rewinding to ExecuteProofmark, delete:
   rm -f {job_dir}/process/ExecuteProofmark.json
   rm -f {job_dir}/process/FinalSignOff.json
   rm -f {job_dir}/process/FBR_EvidenceAudit.json
   rm -f {job_dir}/process/Triage.json
   ```
   See the full node order below for reference.

4. **Insert a new task:**
   ```sql
   INSERT INTO control.re_task_queue (job_id, node_name)
   VALUES ('{job_id}', '{rewind_target}');
   ```

### If dead-lettering (unfixable or RC not understood):

1. **Update job state:**
   ```sql
   UPDATE control.re_job_state
   SET status = 'DEAD_LETTER',
       main_retry_count = {new_retry_count},
       last_rejection_reason = 'Triage: {brief reason from RCA/Fix}',
       triage_results = '{}',
       triage_rewind_target = NULL
   WHERE job_id = '{job_id}';
   ```

2. Do NOT insert a task. The job is done.

## Pipeline Node Order (for artifact cleanup)

When cleaning up process artifacts downstream of a rewind target, these are
the happy-path nodes in order:

```
LocateOgSourceFiles → InventoryOutputs → InventoryDataSources →
NoteDependencies → WriteBrd → ReviewBrd → WriteBddTestArch → ReviewBdd →
WriteFsd → ReviewFsd → BuildJobArtifacts → ReviewJobArtifacts →
BuildProofmarkConfig → ReviewProofmarkConfig → BuildUnitTests →
ReviewUnitTests → ExecuteUnitTests → Publish → ExecuteJobRuns →
ExecuteProofmark → FinalSignOff → FBR_EvidenceAudit
```

Delete process artifacts for the rewind target and everything after it.

## Writes

### Summary (for orchestrator)
- **File:** `{job_dir}/artifacts/triage/reset-summary.md`
- **Content:** Brief. Must include:
  - **Action taken**: `REQUEUED` or `DEAD_LETTER`
  - **Rewind target** (if requeued): Which node
  - **Retry count**: The value written to the database
  - **Process artifacts cleaned**: List of files deleted

## Constraints

- **Status must be RUNNING when requeueing.** This is the most important
  thing to get right. A non-RUNNING job with a pending task is a bug.
- **Clean up process artifacts.** Stale artifacts from previous runs will
  confuse agents that read them. Delete everything downstream of the rewind.
- **Clear legacy triage state.** Reset `triage_results` to `'{}'` and
  `triage_rewind_target` to `NULL`. These are columns from the old triage
  pipeline and should not carry stale data into a new pipeline run.
