# Blueprint Conventions

## Two Artifact Streams

Every agent produces two kinds of output:

### 1. Process Artifacts (agent-to-agent)

Structured JSON. One per node per job. Routing data for the orchestrator +
notes for downstream agents.

**Location:** `jobs/{job_id}/process/{node-name}.json`

**Standard header (every process artifact):**

```json
{
  "node": "{blueprint-name}",
  "job_id": 42,
  "outcome": "SUCCESS",
  "reason": "Human-readable summary of what happened",
  "conditions": [],
  "artifacts_written": ["artifacts/brd.md"],
  "artifacts_read": ["process/source-analyst.json", "process/output-analyst.json"],
  "body": {
    // Node-specific notes for downstream agents
  }
}
```

**Critical rule:** Process artifacts are only written on SUCCESS, APPROVED,
or CONDITIONAL outcomes. On FAIL or REJECTED, the agent reports via stdout
only — no process artifact written.

### 2. Product Artifacts (the deliverables)

The actual RE outputs: BRDs, FSDs, BDD specs, generated code, test suites.
Humans read these eventually.

**Location:** `jobs/{job_id}/artifacts/`

```
jobs/{job_id}/artifacts/
  og-sources.md              # Plan
  output-inventory.md        # Plan
  data-sources.md            # Plan
  dependencies.md            # Plan
  brd.md                     # Define
  fsd.md                     # Design
  bdd_specs/                 # Design
  code/
    jobconf.json             # FW loads via tokenized path
    {module_name}.py         # External module (if applicable)
  proofmark-config.yaml      # Build
  tests/
    test_{job_name}.py       # Unit tests
  triage/                    # Triage diagnostics
    data-profile.md
    og-flow-analysis.md
```

**Product artifacts live in EtlReverseEngineering during development.**
The publisher deploys final code artifacts into MockEtlFrameworkPython's
`RE/` directories (symlinked to the host framework):
- Job confs → `/workspace/MockEtlFrameworkPython/RE/Jobs/{job_name}/jobconf.json`
- External modules → `/workspace/MockEtlFrameworkPython/RE/externals/{module_name}.py`
- Proofmark configs → `/workspace/MockEtlFrameworkPython/RE/Jobs/{job_name}/proofmark-config.yaml`

The host framework sees these via symlinks. `control.jobs` stores the path as
`{ETL_ROOT}/RE/Jobs/{job_name}/jobconf.json` (literal `{ETL_ROOT}` token).
Only the publisher writes to MockEtlFrameworkPython — other agents write
to their `{job_dir}/artifacts/` working directory.

## Outcome Enum

These are the ONLY valid outcome values:

| Value | Used By | Meaning |
|-------|---------|---------|
| `SUCCESS` | Work nodes | Did the job, wrote the deliverable |
| `FAIL` | Work nodes | Couldn't complete, `reason` explains why |
| `APPROVED` | Review nodes | Deliverable passes review |
| `CONDITIONAL` | Review nodes | Passes with caveats, `conditions[]` lists them |
| `REJECTED` | Review nodes | Fails review, `reason` explains why |

The orchestrator reads `outcome`, routes to the next state per the state
machine, and doesn't interpret anything else.

## Agent Response Contract (stdout)

Every agent's stdout must end with a fenced JSON block:

```json
{"outcome": "SUCCESS", "reason": "...", "conditions": []}
```

The orchestrator parses the LAST JSON block from stdout. Everything above it
is agent reasoning/logging — captured but not parsed.

## What Agents Read

An agent reads from three places:

1. **Process artifacts from predecessors** — the JSON chain tells it what
   happened upstream and where deliverables are.
2. **Product artifacts from predecessors** — the actual deliverables to
   review, build on, or verify.
3. **Source material in MockEtlFramework** — the OG C# job code being
   reverse-engineered. Read-only. Agents study it, never modify it.

## Path Tokens

### Orchestrator-resolved tokens

These are resolved by the orchestrator before the agent sees them:

| Token | Meaning | Example (container) |
|-------|---------|---------------------|
| `{ORCH_ROOT}` | EtlReverseEngineering root | `/workspace/EtlReverseEngineering` |
| `{JOB_DIR}` | Per-job directory | `{ORCH_ROOT}/jobs/{job_id}` |
| `{OG_CS_ROOT}` | OG C# MockEtlFramework repo | `/workspace/MockEtlFramework` |
| `{FW_DOCS}` | Python framework documentation | `/workspace/MockEtlFrameworkPython/Documentation` |

### Literal tokens (NOT resolved by orchestrator)

| Token | Meaning | Why literal |
|-------|---------|-------------|
| `{ETL_ROOT}` | Python ETL framework root | Host-side services resolve this from their own env var at runtime. The host path differs from the container path. Agents must write `{ETL_ROOT}` as a literal string in all database entries and file references. |

### Derived paths (not separate tokens — use `{ETL_ROOT}` prefix)

| Path | Meaning | Mode |
|------|---------|------|
| `{ETL_ROOT}/Output/curated/` | OG curated output | Read-only (Docker ro mount) |
| `{ETL_ROOT}/Output/re-curated/` | RE curated output (produced by host) | Read-only (Docker ro mount) |
| `{ETL_ROOT}/src/etl/modules/externals/` | OG external modules (reference) | Read |
| `{ETL_ROOT}/JobExecutor/Jobs/` | OG job confs (reference) | Read |
| `{ETL_ROOT}/RE/Jobs/` | RE job confs + proofmark configs | Write (symlinked to host) |
| `{ETL_ROOT}/RE/externals/` | RE external modules | Write (symlinked to host) |

### Queue entry paths

When writing paths into Postgres queue tables (`control.task_queue`,
`control.proofmark_test_queue`), always use `{ETL_ROOT}` tokens — NOT
orchestrator tokens like `{ORCH_ROOT}`. The host-side services expand
`{ETL_ROOT}` from the env var at runtime. Orchestrator tokens mean nothing
to Proofmark or the ETL framework.

Example Proofmark queue entry:
```sql
INSERT INTO control.proofmark_test_queue (config_path, lhs_path, rhs_path, job_key, date_key)
VALUES (
  '{ETL_ROOT}/RE/Jobs/{job_name}/proofmark-config.yaml',
  '{ETL_ROOT}/Output/curated/{job_name}/{output_table}/{date}/',
  '{ETL_ROOT}/Output/re-curated/{job_name}/{output_table}/{date}/',
  '{job_name}_re',
  '{date}'
);
```

### Running ETL jobs and Proofmark

You **cannot** run the ETL framework or Proofmark locally in the container.
The framework's DB host is `localhost`, which resolves to nothing inside
the container. This is deliberate — validation runs on the host only.

To execute ETL jobs: INSERT into `control.task_queue`. See `job-executor` blueprint.
To run Proofmark: INSERT into `control.proofmark_test_queue`. See `proofmark-executor` blueprint.

## OG vs RE Job Identity

The orchestrator tracks jobs by an internal RE job ID (e.g., `373`). This is
NOT the same as the ETL framework's `job_id` in `control.jobs`.

- The orchestrator provides `job_name` — this is the **OG job name** (e.g.,
  `dans_transaction_special`). It identifies the job being reverse-engineered.
- The **publisher** creates a NEW entry in `control.jobs` with the name
  `{job_name}_re` (e.g., `dans_transaction_special_re`). This gets its own
  auto-incremented `job_id` from Postgres.
- **All downstream agents** (ExecuteJobRuns, ExecuteProofmark) must use the
  `_re` name when inserting into queue tables. Read the registered name from
  the Publish process artifact (`registered_name` field).
- The `_re` suffix prevents unique constraint collisions with the OG job
  in `control.jobs`.
- OG output paths use the OG name (`Output/curated/{job_name}/`).
  RE output paths use the OG name too (`Output/re-curated/{job_name}/`)
  because the job conf's `jobDirName` matches the OG convention.

Do NOT confuse the orchestrator's job ID with the framework's `job_id`.
Do NOT use the OG job name in queue tables — always append `_re`.

## OG C# Code Layout

```
{OG_CS_ROOT}/
├── JobExecutor/Jobs/              # Job conf JSON files
├── ExternalModules/               # C# external module .cs files
├── Lib/                           # Framework library code
├── SQL/                           # SQL files
└── Program.cs                     # Entry point
```

## Rejection Handling

When an agent is re-invoked after CONDITIONAL or REJECTED:

- The orchestrator provides the rejection reason / conditions in the task prompt.
- No accumulated errata. Only the most recent feedback.
- The agent regenerates its FULL product artifact (not a patch).

## Numbering Conventions

- BRD requirements: `BRD-001`, `BRD-002`, ...
- BDD scenarios: `BDD-001`, `BDD-002`, ...
- FSD specifications: `FSD-001`, `FSD-002`, ...

Scoped per job.

## Evidence Requirements

- All claims cite source: `BRD-NNN`, `BDD-NNN`, `FSD-NNN`, or `file:line`.
- No unsupported assertions.
- Reviewers MUST verify cited evidence exists in the actual files.
