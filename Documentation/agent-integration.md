# Agent Integration

Source: `src/workflow_engine/agent_node.py`, `src/workflow_engine/nodes.py` (`create_agent_registry`)

## AgentNode

`AgentNode` replaces stub nodes with real Claude CLI invocations. Enabled when `EngineConfig.use_agents` is true (the default).

Each agent gets:
- A **blueprint** (markdown file) as the system prompt via `--append-system-prompt`
- A **user prompt** with job context (job ID, directories, current node, retry count, last rejection reason)
- **Model** from `MODEL_MAP` (per-node) or CLI `--model` fallback
- ETL effective date range (for date-aware nodes only)

CLI invocation:
```
claude -p \
  --append-system-prompt <blueprint_text> \
  --output-format json \
  --model <MODEL_MAP[node] or CLI fallback> \
  --dangerously-skip-permissions \
  --no-session-persistence \
  [--agents <sub_agent_json>] \
  <prompt>
```

Working directory is set to the parent of `jobs_dir`. Per-step timeout is **1800 seconds** (30 minutes).

## Per-Node Model Assignment

The model for each agent invocation is determined by:

1. **`MODEL_MAP`** in `nodes.py` -- explicit per-node assignments (16 opus, 2 haiku)
2. **CLI `--model` flag** -- fallback for all other nodes (default: sonnet)

The `create_agent_registry()` function resolves this: `MODEL_MAP.get(node_name, model)`.

## Sub-Agents (Code Quality Review)

Author nodes that generate code or config get an internal code quality reviewer sub-agent via Claude's `--agents` flag. The sub-agent catches slop before the output reaches the dedicated reviewer downstream.

Author nodes: `BuildJobArtifacts`, `BuildJobArtifactsResponse`, `BuildProofmarkConfig`, `BuildProofmarkResponse`, `BuildUnitTests`, `BuildUnitTestsResponse`.

## Two-Artifact-Stream Architecture

Each job gets a directory at `jobs_dir/{job_id}/` with two subdirectories:

### `process/`
- **Audience**: Other agents (downstream nodes).
- **Content**: JSON files named `{node_name}.json`, containing the outcome data block emitted by the agent.
- **Lifecycle**: Written on SUCCESS, APPROVE, or CONDITIONAL. Deleted on rewind (`_cleanup_stale_artifacts` removes process artifacts for all downstream nodes when rewinding).
- **Purpose**: Gives downstream agents context about what upstream agents decided and found.

### `artifacts/`
- **Audience**: The final consumer (human or system).
- **Content**: Deliverable files -- BRDs, FSDs, job configs, test files, proofmark configs, etc.
- **Lifecycle**: Persists across the job lifecycle. Not cleaned up on rewind (agents are expected to overwrite).

## Stdout JSON Contract

Agents must emit a JSON block containing an `"outcome"` key somewhere in their text output. The parser (`_extract_outcome_json`) finds the **last** JSON object in the agent's output that has an `"outcome"` key.

The Claude CLI wraps output in `{"result": "<agent_text>"}` when using `--output-format json`. The parser unwraps this first.

### Valid outcome strings

| Agent emits | Maps to internal Outcome |
|---|---|
| `"SUCCESS"` | Outcome.SUCCESS |
| `"FAIL"` | Outcome.FAILURE |
| `"APPROVED"` | Outcome.APPROVE |
| `"CONDITIONAL"` | Outcome.CONDITIONAL |
| `"REJECTED"` | Outcome.FAIL |

Note the asymmetry: agents emit `"FAIL"` (mapped to FAILURE) and `"REJECTED"` (mapped to FAIL). FAILURE is for WORK nodes that can't complete. FAIL is for REVIEW nodes that reject.

If parsing fails at any stage (bad JSON, missing outcome key, unknown outcome string), the node returns `Outcome.FAILURE`.

### Example outcome block

```json
{
  "outcome": "APPROVED",
  "reason": "BRD accurately reflects all data sources and outputs identified in plan stage."
}
```

The `reason` field is logged but not used for routing.

## Blueprint Conventions

Blueprints live at `{blueprints_dir}/{blueprint-name}.md`. The blueprint name is extracted from the node description string (everything before the first colon). For example, the description `"brd-writer: Writes the BRD..."` maps to `blueprints_dir/brd-writer.md`.

Multiple nodes can share a blueprint. For example, `WriteBrd` and `WriteBrdResponse` both use `brd-writer.md`. Similarly, `ReviewBrd` and `FBR_BrdCheck` both use `brd-reviewer.md`.

All C# references have been removed from blueprints. The OG codebase is Python (MockEtlFrameworkPython). All paths in blueprints are hardcoded container paths. **`{ETL_ROOT}` is the ONLY remaining token** -- it's used as a literal string in DB entries for host-side resolution, not as a path the agent resolves. External modules use the `execute(shared_state) -> shared_state` + `register()` pattern.

Blueprint-to-node mapping (derived from `_NODE_DESCRIPTIONS` and `_RESPONSE_NODE_DESCRIPTIONS` in `nodes.py`):

| Blueprint | Nodes |
|---|---|
| og-locator | LocateOgSourceFiles |
| output-analyst | InventoryOutputs |
| source-analyst | InventoryDataSources |
| dependency-analyst | NoteDependencies |
| brd-writer | WriteBrd, WriteBrdResponse |
| brd-reviewer | ReviewBrd, FBR_BrdCheck |
| bdd-writer | WriteBddTestArch, WriteBddResponse |
| bdd-reviewer | ReviewBdd, FBR_BddCheck |
| fsd-writer | WriteFsd, WriteFsdResponse |
| fsd-reviewer | ReviewFsd, FBR_FsdCheck |
| builder | BuildJobArtifacts, BuildJobArtifactsResponse |
| artifact-reviewer | ReviewJobArtifacts, FBR_ArtifactCheck |
| proofmark-builder | BuildProofmarkConfig, BuildProofmarkResponse |
| proofmark-reviewer | ReviewProofmarkConfig, FBR_ProofmarkCheck |
| test-writer | BuildUnitTests, BuildUnitTestsResponse |
| test-reviewer | ReviewUnitTests, FBR_UnitTestCheck |
| test-executor | ExecuteUnitTests |
| publisher | Publish |
| evidence-auditor | FBR_EvidenceAudit |
| job-executor | ExecuteJobRuns |
| proofmark-executor | ExecuteProofmark |
| signoff | FinalSignOff |
| data-profiler | Triage_ProfileData |
| og-flow-analyst | Triage_AnalyzeOgFlow |
| triage-brd-checker | Triage_CheckBrd |
| triage-fsd-checker | Triage_CheckFsd |
| triage-code-checker | Triage_CheckCode |
| triage-pm-checker | Triage_CheckProofmark |

`Triage_Route` is the only node that never gets an agent -- it stays as `TriageRouterNode` regardless of `use_agents`, since it's pure deterministic routing logic.

## Error Handling

| Failure Mode | Result |
|---|---|
| Subprocess timeout (1800s) | Outcome.FAILURE |
| Non-zero exit code | Outcome.FAILURE |
| Unparseable CLI JSON | Outcome.FAILURE |
| No outcome JSON in agent text | Outcome.FAILURE |
| Unknown outcome string | Outcome.FAILURE |

All failures are logged with structured fields (node, job_id, error details). FAILURE is then promoted to FAIL by `_resolve_outcome` for nodes without explicit FAILURE transitions, triggering the self-retry path.
