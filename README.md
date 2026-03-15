# EtlReverseEngineering

Workflow engine that reverse-engineers legacy ETL jobs from [MockEtlFrameworkPython](https://github.com/danielpmcconkey/MockEtlFrameworkPython) using AI agents. Runs a 28-node state machine pipeline where each node invokes Claude CLI with a blueprint prompt. Jobs progress through **Plan -> Define -> Design -> Build -> Validate** stages.

## Why This Exists

POC5 used an LLM-based orchestrator that suffered from context rot. As conversations grew, the orchestrator fabricated results -- copying OG output to fake RE output, writing plausible summaries for work it didn't do. The fix: **the orchestrator is dumb.** It's a deterministic state machine. All intelligence lives in the agents, which get a fresh context on every invocation.

## Architecture

### The Engine (Python, no LLM)

A deterministic processing loop that:

1. Polls a Postgres task queue for unclaimed work
2. Claims a task (thread-safe via `SELECT ... FOR UPDATE SKIP LOCKED`)
3. Dispatches it to the appropriate Claude agent via `claude -p`
4. Parses the structured JSON response
5. Writes results and enqueues the next step per the transition table
6. Manages a pool of concurrent workers across all jobs

The engine doesn't make decisions. It follows a transition table -- a state machine that maps `(current_node, outcome) -> next_node`.

### Agent Invocation

Each agent is invoked as a fresh Claude CLI subprocess:

```bash
claude -p \
  --append-system-prompt <blueprint_text> \
  --output-format json \
  --model <per-node model or CLI fallback> \
  --dangerously-skip-permissions \
  --no-session-persistence \
  <prompt>
```

Agents do their work, return a structured JSON result with an `"outcome"` key, and die. No state carried between invocations. Per-step timeout is **1800 seconds** (30 minutes).

### Per-Node Model Mapping

`MODEL_MAP` in `src/workflow_engine/nodes.py` assigns models per node. The CLI `--model` flag is the **fallback default**, not a universal assignment.

| Tier | Nodes | Count | Rationale |
|------|-------|-------|-----------|
| **Opus** | Spec writing (BRD/BDD/FSD + responses), adversarial reviews (ReviewBrd/Bdd/Fsd, ReviewJobArtifacts), FBR drift gates (BrdCheck/FsdCheck/ArtifactCheck), judgment nodes (FinalSignOff, EvidenceAudit), triage OG tracing (AnalyzeOgFlow) | 16 | Spec/design and adversarial review need the strongest model |
| **Haiku** | Publish, ExecuteProofmark | 2 | Mechanical execution -- file copy, queue+poll |
| **Sonnet** | Everything else (via CLI `--model` fallback) | 23 | Solid default for plan, build, test, remaining triage |

### Task Queue (Postgres)

Tables live in the `control` schema with `re_` prefix. Key constraint:

- **`ix_re_task_queue_one_active`**: `UNIQUE` partial index on `(job_id) WHERE status IN ('pending', 'claimed')`. Only one active queue entry per job allowed.
- To restart a stalled job: mark orphaned `claimed` entries as `failed` first, THEN insert a new `pending` entry.

### Two-Artifact-Stream Architecture

Each job gets a directory at `jobs/{job_id}/` with two subdirectories:

- **`process/`** -- JSON files for inter-agent communication. Written on SUCCESS/APPROVE/CONDITIONAL. Cleaned up on rewind.
- **`artifacts/`** -- Deliverable files (BRDs, FSDs, job configs, tests, etc.). Persists across rewinds.

## CLI Usage

```bash
cd /workspace/EtlReverseEngineering
source .venv/bin/activate
python -m workflow_engine jobs/batch-12-manifest.json \
  --etl-start-date 2024-10-01 \
  --etl-end-date 2024-10-31 \
  --model sonnet \
  --n-jobs 12
```

| Flag | Default | Description |
|------|---------|-------------|
| `manifest_path` | (required) | Path to job manifest JSON |
| `--n-jobs` | 5 | Concurrent workers |
| `--model` | sonnet | Fallback model for nodes not in MODEL_MAP |
| `--etl-start-date` | (none) | First effective date (YYYY-MM-DD) |
| `--etl-end-date` | (none) | Last effective date (YYYY-MM-DD) |
| `--max-retries` | 5 | Max main retries per job before DEAD_LETTER |
| `--max-conditional` | 3 | Max consecutive CONDITIONALs per review node before escalation to FAIL |
| `--timeout` | 14400 | Max seconds for entire engine run |
| `--stubs` | (flag) | Use stub nodes instead of agents (testing) |
| `--blueprints-dir` | blueprints | Blueprint markdown directory |
| `--jobs-dir` | jobs | Job output directory |

## Pipeline Overview

28 happy-path nodes, 6 response nodes (off happy path), 7 triage nodes:

```
Plan (1-4)
  LocateOgSourceFiles -> InventoryOutputs -> InventoryDataSources -> NoteDependencies

Define (5-6)
  WriteBrd -> ReviewBrd

Design (7-10)
  WriteBddTestArch -> ReviewBdd -> WriteFsd -> ReviewFsd

Build (11-24)
  BuildJobArtifacts -> ReviewJobArtifacts -> BuildProofmarkConfig -> ReviewProofmarkConfig
  -> BuildUnitTests -> ReviewUnitTests -> ExecuteUnitTests -> Publish
  -> FBR_BrdCheck -> FBR_BddCheck -> FBR_FsdCheck -> FBR_ArtifactCheck
  -> FBR_ProofmarkCheck -> FBR_UnitTestCheck

Validate (25-28)
  ExecuteJobRuns -> ExecuteProofmark -> FinalSignOff -> FBR_EvidenceAudit -> COMPLETE

Response nodes (off happy path, loop back to reviewer):
  WriteBrdResponse, WriteBddResponse, WriteFsdResponse,
  BuildJobArtifactsResponse, BuildProofmarkResponse, BuildUnitTestsResponse

Triage sub-pipeline (entered on ExecuteProofmark FAILURE):
  Triage_ProfileData -> Triage_AnalyzeOgFlow -> Triage_CheckBrd -> Triage_CheckFsd
  -> Triage_CheckCode -> Triage_CheckProofmark -> Triage_Route
```

See `Documentation/` for detailed docs on transitions, FBR gauntlet, triage, and agent integration.

## Work-Node FAIL Transitions

All WORK nodes have self-retry FAIL transitions in the transition table. When a WORK node returns FAIL (e.g., agent timeout, bad JSON, crash), it retries itself. Previously only REVIEW/FBR nodes had FAIL edges, which caused zombie jobs when work nodes failed with no transition. The step handler now saves job state before raising `ValueError` on missing transitions as a safety net.

## Blueprint System

Blueprints live at `blueprints/{blueprint-name}.md`. The blueprint name is extracted from the node description (e.g., `"brd-writer: Writes the BRD..."` maps to `blueprints/brd-writer.md`). Multiple nodes share blueprints -- `WriteBrd` and `WriteBrdResponse` both use `brd-writer.md`.

All C# references have been removed from blueprints. The OG codebase is Python (MockEtlFrameworkPython). All paths are hardcoded container paths. **`{ETL_ROOT}` is the ONLY token** -- used as a literal string in DB entries for host-side resolution. External modules use the `execute(shared_state) -> shared_state` + `register()` pattern.

## Key Paths (Container)

| What | Path |
|------|------|
| OG job confs | `/workspace/MockEtlFrameworkPython/JobExecutor/Jobs/` |
| OG external modules | `/workspace/MockEtlFrameworkPython/src/etl/modules/externals/` |
| OG output | `/workspace/MockEtlFrameworkPython/Output/curated/` |
| RE output | `/workspace/MockEtlFrameworkPython/Output/re-curated/` |
| RE job confs deployed to | `/workspace/MockEtlFrameworkPython/RE/Jobs/` |
| RE externals deployed to | `/workspace/MockEtlFrameworkPython/RE/externals/` |
| Framework docs | `/workspace/MockEtlFrameworkPython/Documentation/` |
| Proofmark docs | `/workspace/proofmark/Documentation/` |

## Related Repos

- [MockEtlFrameworkPython](https://github.com/danielpmcconkey/MockEtlFrameworkPython) -- Python ETL engine (target for RE'd jobs)
- [proofmark](https://github.com/danielpmcconkey/proofmark) -- Comparison engine for OG vs RE output verification
- [AtcStrategy](https://github.com/danielpmcconkey/AtcStrategy) -- (private) Design notes, taxonomy, architecture docs
