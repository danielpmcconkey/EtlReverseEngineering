# ETL Reverse Engineering

## What This Is

Reverse engineering of 105 production ETL jobs with zero documentation. The original teams are gone. We have the code, its output, and nothing else. This project produces clean, documented, anti-pattern-free replacements for every job — with proof that each replacement produces byte-identical output across 92 test dates. This is also a proof of concept intended to generate reusable artifacts for a ~100-job production prototype.

## Core Value

Output is king. Every RE'd job must produce output that matches the original across all 92 effective dates (Oct 1 – Dec 31, 2024). Nothing else matters if the data doesn't match.

## Requirements

### Validated

- ✓ Repository structure and conventions — established in EtlReverseEngineering repo
- ✓ Infrastructure working — ETL Framework, Proofmark, Postgres task queue, path tokens all confirmed functional
- ✓ Proofmark integration for output comparison — tested end-to-end

### Active

- [ ] **RE-01**: Each job gets a BRD with numbered requirements and evidence citing original code or data
- [ ] **RE-02**: Each job gets an FSD with numbered specs, traceability to BRD numbers, and evidence for each spec
- [ ] **RE-03**: Each job gets a test strategy with traceability to FSD/BRD numbers
- [ ] **RE-04**: Each job gets a new `_re` JSON job conf based on the FSD, remediated for anti-patterns
- [ ] **RE-05**: External modules are last resort — created ONLY when standard modules cannot produce byte-identical output. FSD must cite evidence for why.
- [ ] **RE-06**: Output manifesto listing every output in the system (some jobs produce multiple outputs)
- [ ] **RE-07**: Proofmark config YAML per output with evidence for any non-strict column matching
- [ ] **RE-08**: Proofmark test evidence showing 92/92 PASS for all effective dates
- [ ] **RE-09**: All 105 jobs RE'd with zero human input after planning
- [ ] **FAIL-01**: On Proofmark failure — triage, RCA, fix, update BRD/FSD with evidence, retry (max 5 attempts then flag for human review)
- [ ] **TIER-01**: Tier 1 batch complete — BranchDirectory, ComplianceResolutionTime, OverdraftFeeSummary (3 jobs)
- [ ] **TIER-02**: Tier 2 batch complete — remaining simple multi-source jobs (10 jobs)
- [ ] **TIER-03**: Tier 3 batch complete — Append mode jobs (13 jobs)
- [ ] **TIER-04**: Tier 4 batch complete — external module jobs (~67 jobs)
- [ ] **TIER-05**: Tier 5 batch complete — external module + Append mode (6 jobs)
- [ ] **TIER-06**: Tier 6 batch complete — boss-level jobs (4 jobs)

### Out of Scope

- Modifying the ETL Framework itself — read-only access, we work within its constraints
- Modifying original V1 job confs or output — those are the source of truth
- Performance optimization beyond anti-pattern remediation — matching output is the goal, not beating it
- Fixing upstream data quality issues — we reproduce what exists, warts and all

## Context

### Prime Directive: Anti-Pattern Remediation

This is not a lift-and-shift. The V1 code is assumed to be bad. Every RE'd job must identify and remediate these anti-patterns:

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

**AP3 is the big one.** External modules are last resort. The RE'd job should use only DataSourcing + SQL Transformation + standard writers unless there is a proven deficiency. AP6 (Row-by-Row Iteration) is often the path to eliminating external modules entirely — convert C# foreach to SQL set operations.

### Complexity Tiers

| Tier | Description | Count | Key Challenge |
|------|-------------|-------|---------------|
| 1 | Trivial (1 DS, no external, Overwrite) | 3 | None — validation of pipeline |
| 2 | Simple (1-2 DS, no external, Overwrite) | 10 | Multi-source joins |
| 3 | Simple + Append mode | 13 | Chronological execution, cumulative output |
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

### Iterative Learning

Early tier completions refine the approach for later tiers. The 13-step workflow is the expected base, not gospel. Agents should update their approach as patterns emerge — what works for Tier 1 informs Tier 2, what breaks in Tier 4 updates the blueprint for Tier 5+. The ultimate goal beyond these 105 jobs is a reusable blueprint for tens of thousands of jobs in production.

### Infrastructure

**Execution model:** Queue-driven. Agents write job confs and docs. ETL Framework (on host) executes jobs. Proofmark (on host) validates output. Postgres is the integration bus.

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

**Path tokens:**

| Token | Container Path | Used By |
|-------|---------------|---------|
| `{ETL_ROOT}` | `/workspace/MockEtlFramework` | ETL FW, Proofmark |
| `{ETL_RE_ROOT}` | `/workspace` | ETL FW (job conf paths), Proofmark (config paths) |
| `{ETL_RE_OUTPUT}` | `/workspace/MockEtlFramework/Output/curated_re` | ETL FW (output dir), Proofmark (rhs paths) |

**Database:** PostgreSQL at `172.18.0.1:5432`, DB: `atc`, User: `claude`
Key tables: `control.jobs`, `control.task_queue`, `control.proofmark_test_queue`

### Expected Workflow (per job)

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
13. Verify 92/92 PASS — if not, triage/RCA/fix/retry (max 5 attempts)

### Append Mode

23 jobs use Append mode. Append output is cumulative — each date's file contains all data from Oct 1 through that date. Append jobs MUST run dates in chronological order. Overwrite jobs (82) are independent per date.

### Reference Documents

- RE Blueprint with SQL templates and gotchas: `/workspace/AtcStrategy/POC5/re-blueprint.md`
- Job complexity analysis: `/workspace/AtcStrategy/POC5/job-complexity-analysis.md`

## Constraints

- **Network isolation**: Read-only access to V1 code and output. Write access only to `{ETL_RE_OUTPUT}` and EtlReverseEngineering repo.
- **ETL Framework as-is**: Cannot modify framework code. Must work within existing standard modules.
- **Queue-driven execution**: Jobs run on host via ETL Framework. Agents queue work via Postgres. No direct execution.
- **Full autonomy**: Zero human input after planning. Agents cannot ask Dan for clarification during execution.
- **Failure budget**: Max 5 fix-retry cycles per job before flagging for human review.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Start small, escalate complexity and batch size | Build confidence, validate mechanics, let early results refine approach | — Pending |
| Iterative learning across tiers | Early completions update the blueprint for later tiers. Scales to tens of thousands of jobs. | — Pending |
| `_re` suffix for RE job confs and job names | Lives alongside originals, clear provenance | ✓ Good |
| External modules only when standard modules can't match output | Minimize maintenance surface, prove SQL can replace C# | — Pending |
| GSD + CE for orchestration | Testing whether off-the-shelf tooling beats custom agent orchestration (POC3/POC4 both failed) | — Pending |
| All MCP tools mandatory | Serena, Context7, Sequential Thinking used alongside GSD/CE — post-hoc evaluation | — Pending |
| 5-attempt retry limit on Proofmark failures | Enough room to diagnose complex mismatches without infinite loops | — Pending |

---
*Last updated: 2026-03-09 after GSD initialization*
