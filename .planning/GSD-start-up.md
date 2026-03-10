# ETL Reverse Engineering

## What This Is

Reverse engineering of 105 production ETL jobs that have been running for years with zero documentation. The jobs produce validated, business-critical output consumed by downstream partners. The original teams are gone. We have the code, its output, and nothing else. This project produces clean, documented replacements for every job — with proof that each replacement produces byte-identical output.

## Core Value

Output is king. Every RE'd job must produce output that matches the original across all 92 test dates. Nothing else matters if the data doesn't match.

## Prime Directive: Anti-Pattern Remediation

This is not a lift-and-shift. The V1 code is assumed to be bad. Every RE'd job must identify and remediate the anti-patterns present in the original. The full catalog is in the Context section below, but the critical ones to internalize:

- **AP3 (Unnecessary External Module)** is the big one. External modules are a last resort. The RE'd job should use only DataSourcing + SQL Transformation + standard writers unless there is a proven deficiency in the ETL Framework's standard module set that prevents producing byte-identical output. If an external module is retained or created, the FSD must include explicit evidence explaining what the standard modules cannot do and why the external module is necessary.
- **AP1 (Dead-End Sourcing)** and **AP4 (Unused Columns)** — strip everything the job doesn't actually need.
- **AP6 (Row-by-Row Iteration)** — convert C# foreach loops to SQL set operations wherever possible. This is often the path to eliminating external modules entirely.

The goal is clean, minimal, SQL-first job confs with full traceability for every decision.

## Requirements

### Validated

- ✓ Repository structure and conventions — established in EtlReverseEngineering repo
- ✓ Infrastructure working — ETL Framework, Proofmark, Postgres task queue, path tokens all confirmed functional
- ✓ Proofmark integration for output comparison — tested end-to-end

### Active

- [ ] **RE-01**: Each job gets a BRD with numbered requirements (e.g. BRD-01) and evidence citing original code or data for each requirement
- [ ] **RE-02**: Each job gets an FSD with numbered specs, traceability to BRD numbers, and evidence for each functional specification
- [ ] **RE-03**: Each job gets a test strategy with traceability to FSD numbers (or BRD numbers if BDD style)
- [ ] **RE-04**: Each job gets a new `_re` JSON job conf based on the FSD, remediated for anti-patterns
- [ ] **RE-05**: External modules are a last resort — created ONLY when standard ETL Framework modules (DataSourcing, SQL Transformation, CsvFileWriter, ParquetFileWriter) cannot produce byte-identical output. FSD must cite evidence for why standard modules are insufficient if an external module is used.
- [ ] **RE-06**: Output manifesto listing every output in the system (some jobs produce multiple outputs)
- [ ] **RE-07**: Proofmark config YAML per output with evidence for any non-strict column matching
- [ ] **RE-08**: Proofmark test evidence showing 100% match for all 92 effective dates (Oct 1 – Dec 31, 2024)
- [ ] **RE-09**: All 105 jobs RE'd with zero human input after planning session
- [ ] **TIER-01**: Tier 1 batch complete — BranchDirectory, ComplianceResolutionTime, OverdraftFeeSummary
- [ ] **TIER-02**: Tier 2 batch complete — remaining simple multi-source jobs
- [ ] **TIER-03**: Tier 3 batch complete — Append mode jobs validated
- [ ] **TIER-04**: Tier 4 batch complete — external module jobs (bulk of portfolio, 67 jobs)
- [ ] **TIER-05**: Tier 5 batch complete — external module + Append mode
- [ ] **TIER-06**: Tier 6 batch complete — boss-level jobs (ExecutiveDashboard, Customer360Snapshot, etc.)

### Out of Scope

- Modifying the ETL Framework itself — read-only access, we work within its constraints
- Modifying original V1 job confs or output — those are the source of truth
- Performance optimization beyond anti-pattern remediation — matching output is the goal, not beating it
- Fixing upstream data quality issues — we reproduce what exists, warts and all

## Context

### Anti-Patterns to Remediate

These are the known code-quality problems in the V1 jobs. Every RE'd job must identify which of these are present and remediate them:

| ID | Name | Description |
|----|------|-------------|
| AP1 | Dead-End Sourcing | Sources tables/data never referenced in processing |
| AP2 | Duplicated Logic | Re-derives data another job already computes |
| AP3 | Unnecessary External Module | C# module where SQL Transformation would suffice |
| AP4 | Unused Columns | Sources columns never referenced in processing or output |
| AP5 | Asymmetric Null/Default Handling | Inconsistent NULL treatment across similar operations |
| AP6 | Row-by-Row Iteration | foreach loops where SQL set operations would work |
| AP7 | Magic Values | Hardcoded thresholds with no parameterization or docs |
| AP8 | Complex/Dead SQL | Unused CTEs, redundant subqueries, dead complexity |
| AP9 | Misleading Names | Names that contradict what the code actually produces |
| AP10 | Over-Sourcing Date Ranges | Broad date ranges filtered down in SQL WHERE clause |

### Complexity Tiers

Jobs are categorized by complexity signals: data source count, external module presence, write mode (Overwrite vs Append), output format.

| Tier | Description | Count | Key Challenge |
|------|-------------|-------|---------------|
| 1 | Trivial (1 DS, no external, Overwrite) | 3 | None — validation of pipeline |
| 2 | Simple (1-2 DS, no external, Overwrite) | 10 | Multi-source joins |
| 3 | Simple + Append mode (1-2 DS, no external, Append) | 13 | Chronological execution, cumulative output |
| 4 | Medium (external module, Overwrite) | ~67 | C# analysis and SQL conversion |
| 5 | Complex (external module, Append) | 6 | Both challenges combined |
| 6 | Boss level (high DS count, complex logic) | 4 | Everything at once |

Full breakdown: `/workspace/AtcStrategy/POC5/job-complexity-analysis.md`

### Dependency Graph

Only 5 dependencies across 105 jobs. 100 jobs have zero dependencies.

- Job 5 (DailyTransactionVolume) → Job 2 (DailyTransactionSummary)
- Job 6 (MonthlyTransactionTrend) → Job 5
- Job 24 (BranchVisitSummary) → Job 22 (BranchDirectory)
- Job 25 (BranchVisitPurposeBreakdown) → Job 22
- Job 26 (TopBranches) → Job 24

### Infrastructure

**Execution model:** Queue-driven. Agents write job confs and docs. ETL Framework (on host) executes jobs. Proofmark (on host) validates output. Postgres is the integration bus.

**Network isolation:** Agents cannot modify ETL Framework code, V1 job confs, or original output files. Read-only access to those. Write access to RE output directory only.

**Key paths:**

| What | Path |
|------|------|
| V1 job confs | `/workspace/MockEtlFramework/JobExecutor/Jobs/*.json` |
| External modules | `/workspace/MockEtlFramework/ExternalModules/*.cs` |
| V1 output | `{ETL_ROOT}/Output/curated/{jobDirName}/{outputTableDirName}/{date}/{fileName}` |
| RE output | `{ETL_RE_OUTPUT}/{jobDirName}/{outputTableDirName}/{date}/{fileName}` |
| RE job confs | `/workspace/EtlReverseEngineering/job-confs/` |
| Per-job docs | `/workspace/EtlReverseEngineering/jobs/{JobName}/` |
| Proofmark configs | `/workspace/EtlReverseEngineering/proofmark-configs/{JobName}.yaml` |

**Path tokens (resolved by host services):**

| Token | Container Path | Used By |
|-------|---------------|---------|
| `{ETL_ROOT}` | `/workspace/MockEtlFramework` | ETL FW, Proofmark |
| `{ETL_RE_ROOT}` | `/workspace` | ETL FW (job conf paths), Proofmark (config paths) |
| `{ETL_RE_OUTPUT}` | `/workspace/MockEtlFramework/Output/curated_re` | ETL FW (output dir), Proofmark (rhs paths) |

**Database:** PostgreSQL at `172.18.0.1:5432`, DB: `atc`, User: `claude`
Key tables: `control.jobs`, `control.task_queue`, `control.proofmark_test_queue`

### Expected Workflow (per job)

Infrastructure has been verified end-to-end. The following is the expected base workflow — agents should adapt as needed for job complexity (external modules, Append mode, dependencies). See `/workspace/AtcStrategy/POC5/re-blueprint.md` for SQL templates and known gotchas.

1. Read original job conf and external module (if any)
2. Check original output (format, row count, stability across dates)
3. Write BRD (numbered requirements with evidence, flag anti-patterns)
4. Write FSD (numbered specs traceable to BRDs, document changes from V1)
5. Write test strategy (traceable to FSDs)
6. Write `_re` job conf (remediate anti-patterns, use `{ETL_RE_OUTPUT}`)
7. Write new external module ONLY if standard modules can't match output
8. Write Proofmark config YAML
9. Register job in `control.jobs`
10. Queue 92 dates in `control.task_queue` (chronological order for Append jobs)
11. Verify all tasks Succeeded
12. Queue 92 Proofmark comparisons in `control.proofmark_test_queue`
13. Verify 92/92 PASS

### Append Mode

23 jobs use Append mode. Append output is cumulative — each date's file contains all data from Oct 1 through that date. Append jobs MUST run dates in chronological order. Overwrite jobs (82) are independent per date.

### What's Already Done

- **EtlReverseEngineering repo** — created, pushed, directory conventions established.
- **RE Blueprint** — documented at `/workspace/AtcStrategy/POC5/re-blueprint.md` with SQL templates, gotchas, and known infrastructure pitfalls.
- **Infrastructure verified** — path tokens, job registration, task queue, Proofmark comparison all confirmed working.

## Constraints

- **Network isolation**: Agents have read-only access to V1 code and output. Write access only to `{ETL_RE_OUTPUT}` and EtlReverseEngineering repo.
- **ETL Framework as-is**: Cannot modify framework code. Must work within existing standard modules (DataSourcing, SQL Transformation, CsvFileWriter, ParquetFileWriter, External).
- **Execution environment**: Jobs run on host via ETL Framework. Agents queue work via Postgres. No direct execution.
- **Autonomy**: Zero human input after planning. Every phase must be self-contained — agents cannot ask Dan for clarification during execution.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Horizontal processing (one job fully through pipeline before next) | Prevents half-finished jobs, enables learning from each completion | — Pending |
| Tier-based processing order (easiest first) | Build confidence, validate mechanics before tackling complexity | — Pending |
| `_re` suffix for RE job confs and job names | Lives alongside originals, clear provenance | ✓ Good |
| External modules only when standard modules can't match output | Minimize maintenance surface, prove SQL can replace C# | — Pending |
| GSD + CE for orchestration | Testing whether off-the-shelf tooling beats custom agent orchestration (POC3/POC4 both failed) | — Pending |
| All MCP tools mandatory | Serena, Context7, Sequential Thinking used alongside GSD/CE — post-hoc evaluation | — Pending |

---
*Last updated: 2026-03-09 after GSD initialization*
