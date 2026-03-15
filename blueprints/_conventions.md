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
3. **Source material in MockEtlFrameworkPython** — the OG job code being
   reverse-engineered. Read-only. Agents study it, never modify it.
   - OG job confs: `/workspace/MockEtlFrameworkPython/JobExecutor/Jobs/`
   - OG external modules: `/workspace/MockEtlFrameworkPython/src/etl/modules/externals/`
   - OG output: `/workspace/MockEtlFrameworkPython/Output/curated/`

## Paths

### Container paths (hardcoded)

All paths in blueprints are absolute container paths. No tokens, no indirection.

| Path | What | Mode |
|------|------|------|
| `/workspace/EtlReverseEngineering/` | Orchestrator root | Read/Write |
| `/workspace/EtlReverseEngineering/jobs/{job_id}/` | Per-job working directory | Read/Write |
| `/workspace/MockEtlFrameworkPython/` | OG ETL framework (Python) | Read-only |
| `/workspace/MockEtlFrameworkPython/JobExecutor/Jobs/` | OG job confs (JSON) | Read-only |
| `/workspace/MockEtlFrameworkPython/src/etl/modules/externals/` | OG external modules (Python) | Read-only |
| `/workspace/MockEtlFrameworkPython/Output/curated/` | OG curated output | Read-only |
| `/workspace/MockEtlFrameworkPython/Output/re-curated/` | RE curated output (produced by host) | Read-only |
| `/workspace/MockEtlFrameworkPython/RE/Jobs/` | RE job confs + proofmark configs | Write (publisher only) |
| `/workspace/MockEtlFrameworkPython/RE/externals/` | RE external modules | Write (publisher only) |
| `/workspace/MockEtlFrameworkPython/Documentation/` | Framework docs | Read-only |
| `/workspace/proofmark/Documentation/` | Proofmark docs | Read-only |

### The `{ETL_ROOT}` literal

`{ETL_ROOT}` is **not a token you resolve**. It is a literal string that
agents write into database entries. The host-side services (ETL framework,
Proofmark) expand it from their own environment variable at runtime. The
host path differs from the container path — that's the whole point.

**Use `{ETL_ROOT}` ONLY in:**
- `control.jobs` path entries (publisher)
- `control.proofmark_test_queue` path entries (proofmark executor)

**Never use `{ETL_ROOT}` when:**
- Reading or writing files on the container filesystem
- Referencing paths in blueprints, artifacts, or process JSONs

Example Proofmark queue entry:
```sql
INSERT INTO control.proofmark_test_queue (config_path, lhs_path, rhs_path, job_key, date_key)
VALUES (
  '{ETL_ROOT}/RE/Jobs/{job_name}/proofmark-config.yaml',
  '{ETL_ROOT}/Output/curated/{job_name}/{output_table}/{date}/{output_table}.csv',
  '{ETL_ROOT}/Output/re-curated/{job_name}/{output_table}/{date}/{output_table}.csv',
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

## OG Code Layout (MockEtlFrameworkPython)

```
/workspace/MockEtlFrameworkPython/
├── JobExecutor/Jobs/              # OG job conf JSON files
├── src/etl/modules/externals/     # OG external modules (Python)
├── src/etl/modules/               # Framework module implementations
├── RE/Jobs/                       # RE job confs (deployed by publisher)
├── RE/externals/                  # RE external modules (deployed by publisher)
├── Output/curated/                # OG output (read-only)
├── Output/re-curated/             # RE output (produced by host)
└── Documentation/                 # Framework docs
```

### External Module Interface

External modules are Python files with two requirements:
1. A function: `def execute(shared_state: dict[str, object]) -> dict[str, object]`
2. A `register()` call at module scope: `register("ExternalModules.ClassName", execute)`

Discovery is directory-based — the framework globs `*.py` from both
`src/etl/modules/externals/` and `RE/externals/`, loads each file, and the
`register()` call populates an internal registry keyed by `typeName`.

The `assemblyPath` field in job confs is vestigial (from the original C#
framework) and is ignored by the Python framework. Agents should not
reference it or treat it as meaningful.

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
