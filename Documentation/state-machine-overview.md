# State Machine Overview

Source: `src/workflow_engine/transitions.py`, `src/workflow_engine/nodes.py`

The workflow is a linear 28-node happy path. Each node is classified as either WORK or REVIEW. WORK nodes advance on `SUCCESS`. REVIEW nodes advance on `APPROVE`.

## Stages and Nodes

### Plan (nodes 1-4)

| # | Node | Type | Model | Description |
|---|------|------|-------|-------------|
| 1 | LocateOgSourceFiles | WORK | sonnet | Locates original source files for the ETL job |
| 2 | InventoryOutputs | WORK | sonnet | Inventories all output targets produced by the ETL job |
| 3 | InventoryDataSources | WORK | sonnet | Inventories all data sources consumed by the ETL job |
| 4 | NoteDependencies | WORK | sonnet | Documents inter-job and external dependencies |

### Define (nodes 5-6)

| # | Node | Type | Model | Description |
|---|------|------|-------|-------------|
| 5 | WriteBrd | WORK | **opus** | Writes the Business Requirements Document from plan artifacts |
| 6 | ReviewBrd | REVIEW | **opus** | Reviews the BRD for correctness |

### Design (nodes 7-10)

| # | Node | Type | Model | Description |
|---|------|------|-------|-------------|
| 7 | WriteBddTestArch | WORK | **opus** | Writes BDD test architecture from the approved BRD |
| 8 | ReviewBdd | REVIEW | **opus** | Reviews BDD test architecture for completeness |
| 9 | WriteFsd | WORK | **opus** | Writes the Functional Specification Document from BDD and BRD |
| 10 | ReviewFsd | REVIEW | **opus** | Reviews the FSD for accuracy |

### Build (nodes 11-24)

| # | Node | Type | Model | Description |
|---|------|------|-------|-------------|
| 11 | BuildJobArtifacts | WORK | sonnet | Builds job config and external module artifacts from the FSD |
| 12 | ReviewJobArtifacts | REVIEW | **opus** | Reviews built job artifacts against the FSD |
| 13 | BuildProofmarkConfig | WORK | sonnet | Builds proofmark comparison configuration |
| 14 | ReviewProofmarkConfig | REVIEW | sonnet | Reviews proofmark config for correct match rules |
| 15 | BuildUnitTests | WORK | sonnet | Writes unit tests from BDD test architecture |
| 16 | ReviewUnitTests | REVIEW | sonnet | Reviews unit tests for coverage and correctness |
| 17 | ExecuteUnitTests | WORK | sonnet | Executes the unit test suite and reports results |
| 18 | Publish | WORK | **haiku** | Publishes built artifacts to the target environment |
| 19 | FBR_BrdCheck | REVIEW | **opus** | Final build review gate: BRD consistency |
| 20 | FBR_BddCheck | REVIEW | sonnet | Final build review gate: BDD consistency |
| 21 | FBR_FsdCheck | REVIEW | **opus** | Final build review gate: FSD consistency |
| 22 | FBR_ArtifactCheck | REVIEW | **opus** | Final build review gate: artifact consistency |
| 23 | FBR_ProofmarkCheck | REVIEW | sonnet | Final build review gate: proofmark config |
| 24 | FBR_UnitTestCheck | REVIEW | sonnet | Final build review gate: unit test coverage |

### Validate (nodes 25-28)

| # | Node | Type | Model | Description |
|---|------|------|-------|-------------|
| 25 | ExecuteJobRuns | WORK | sonnet | Executes the ETL job against real data |
| 26 | ExecuteProofmark | WORK | **haiku** | Runs proofmark comparison against job output |
| 27 | FinalSignOff | REVIEW | **opus** | Final human-equivalent sign-off on the completed job |
| 28 | FBR_EvidenceAudit | REVIEW | **opus** | Mechanical verification of all traceability links (terminal gate) |

Model assignments come from `MODEL_MAP` in `nodes.py`. Nodes showing "sonnet" use the CLI `--model` fallback.

## Response Nodes (off happy path)

When a REVIEW node returns `CONDITIONAL`, the job routes to a response node. Response nodes are WORK type. They revise the artifact, then route back to the same reviewer.

| Response Node | Paired Reviewer | Revises | Model |
|---|---|---|---|
| WriteBrdResponse | ReviewBrd | BRD | **opus** |
| WriteBddResponse | ReviewBdd | BDD test architecture | **opus** |
| WriteFsdResponse | ReviewFsd | FSD | **opus** |
| BuildJobArtifactsResponse | ReviewJobArtifacts | Job artifacts | sonnet |
| BuildProofmarkResponse | ReviewProofmarkConfig | Proofmark config | sonnet |
| BuildUnitTestsResponse | ReviewUnitTests | Unit tests | sonnet |

## Node Type Classification

Node types are computed in `transitions.py`. The `_REVIEW_NODES` set explicitly lists all REVIEW nodes (the 6 in-flow reviewers, the 6 FBR gates, FBR_EvidenceAudit, and FinalSignOff). Everything else is WORK. Response nodes are added to `NODE_TYPES` separately since they aren't in `HAPPY_PATH`.
