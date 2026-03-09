---
phase: 02-tier-2-simple-multi-source
plan: 01
subsystem: etl-reverse-engineering
tags: [csv, multi-source, left-join, anti-pattern-remediation, proofmark, batch-execution]

requires:
  - phase: 01-tier-1-pipeline-validation
    provides: 13-step RE workflow, doc templates, Proofmark infrastructure, control table schema

provides:
  - 3 RE'd Tier 2 CSV jobs (CustomerAccountSummary, SecuritiesDirectory, TransactionSizeBuckets) with 92/92 PASS each
  - AP1 remediation pattern for dead-end data sources
  - AP8 remediation pattern for dead ROW_NUMBER in multi-CTE SQL
  - AP4 aggressive column removal pattern (TSB: 4 columns to 1)
  - Batch execution pattern for 3 multi-source jobs

affects: [02-tier-2-simple-multi-source, all-future-phases]

tech-stack:
  added: []
  patterns: [batch-job-execution, ap1-dead-source-removal, ap4-aggressive-column-pruning, multi-source-join-re]

key-files:
  created:
    - job-confs/customer_account_summary_re.json
    - job-confs/securities_directory_re.json
    - job-confs/transaction_size_buckets_re.json
    - proofmark-configs/CustomerAccountSummary.yaml
    - proofmark-configs/SecuritiesDirectory.yaml
    - proofmark-configs/TransactionSizeBuckets.yaml
    - jobs/CustomerAccountSummary/BRD.md
    - jobs/CustomerAccountSummary/FSD.md
    - jobs/CustomerAccountSummary/test-strategy.md
    - jobs/CustomerAccountSummary/output-manifesto.md
    - jobs/CustomerAccountSummary/anti-pattern-assessment.md
    - jobs/SecuritiesDirectory/BRD.md
    - jobs/SecuritiesDirectory/FSD.md
    - jobs/SecuritiesDirectory/test-strategy.md
    - jobs/SecuritiesDirectory/output-manifesto.md
    - jobs/SecuritiesDirectory/anti-pattern-assessment.md
    - jobs/TransactionSizeBuckets/BRD.md
    - jobs/TransactionSizeBuckets/FSD.md
    - jobs/TransactionSizeBuckets/test-strategy.md
    - jobs/TransactionSizeBuckets/output-manifesto.md
    - jobs/TransactionSizeBuckets/anti-pattern-assessment.md
  modified: []

key-decisions:
  - "CAS no remediation: All sourced columns used, LEFT JOIN is meaningful -- cleanest multi-source job"
  - "SD AP1: Removed entire holdings DataSourcing module (never referenced in SQL)"
  - "TSB triple remediation: AP1 (removed accounts), AP8 (removed dead ROW_NUMBER CTE), AP4 (reduced transactions columns from 4 to 1)"
  - "CustomerAccountSummaryBuilder.cs ignored: EXISTS in ExternalModules but NOT referenced by V1 conf"
  - "Direct execution: Host service race condition on task_queue required bypassing queue mode via direct dotnet run invocation"

patterns-established:
  - "AP1 remediation: Verify SQL has zero references to source alias, then remove entire DataSourcing module"
  - "AP4 aggressive: When only 1 of N columns is used in final output, reduce DataSourcing to that single column"
  - "AP8 dead CTE removal: When ROW_NUMBER alias is never referenced downstream, remove entire CTE and reference source directly"
  - "Multi-source batch: Register N jobs, execute via direct invocation per date, queue Proofmark comparisons"

requirements-completed: [COMP-02]

duration: 33min
completed: 2026-03-09
---

# Phase 2 Plan 01: Simple Multi-Source CSV Jobs Summary

**3 Tier 2 CSV jobs RE'd with AP1/AP4/AP8 remediation -- 276/276 Proofmark PASS, batch execution pattern established**

## Performance

- **Duration:** 33 min
- **Started:** 2026-03-09T18:49:24Z
- **Completed:** 2026-03-09T19:22:00Z
- **Tasks:** 2
- **Files created:** 21

## Accomplishments
- CustomerAccountSummary_RE: 92/92 PASS -- clean multi-source LEFT JOIN, no anti-patterns, SQL identical to V1
- SecuritiesDirectory_RE: 92/92 PASS -- AP1 remediated (dead `holdings` DataSourcing removed entirely)
- TransactionSizeBuckets_RE: 92/92 PASS -- triple remediation: AP1 (dead `accounts`), AP8 (dead `ROW_NUMBER` CTE), AP4 (3 unused columns removed from `transactions` DataSourcing)
- Complete doc sets (BRD, FSD, test-strategy, output-manifesto, anti-pattern-assessment) for all 3 jobs
- Batch execution pattern proven: 3 jobs x 92 dates = 276 successful executions

## Task Commits

1. **Task 1: RE workflow for 3 jobs (docs + job confs)** - `21e75ae` (feat)
2. **Task 2: Batch register, execute, and verify** - no file commit (DB operations only)

## Files Created/Modified
- `job-confs/customer_account_summary_re.json` - RE job conf, SQL identical to V1, outputDirectory to {ETL_RE_OUTPUT}
- `job-confs/securities_directory_re.json` - RE job conf, AP1 remediated (single DataSourcing module)
- `job-confs/transaction_size_buckets_re.json` - RE job conf, AP1/AP4/AP8 remediated
- `proofmark-configs/CustomerAccountSummary.yaml` - CSV comparison config
- `proofmark-configs/SecuritiesDirectory.yaml` - CSV comparison config
- `proofmark-configs/TransactionSizeBuckets.yaml` - CSV comparison config
- `jobs/CustomerAccountSummary/*.md` - 5 doc files (BRD, FSD, test-strategy, output-manifesto, anti-pattern-assessment)
- `jobs/SecuritiesDirectory/*.md` - 5 doc files
- `jobs/TransactionSizeBuckets/*.md` - 5 doc files

## Decisions Made
- **CAS: No remediation needed.** All sourced columns used, LEFT JOIN is meaningful (customers to accounts). Cleanest multi-source job in Tier 2. `CustomerAccountSummaryBuilder.cs` exists in ExternalModules but is NOT referenced by V1 conf -- correctly ignored.
- **SD: AP1 full source removal.** `holdings` DataSourcing module removed entirely. SQL never references holdings -- zero output impact.
- **TSB: Most aggressive remediation in project.** Triple AP remediation: AP1 removed accounts source, AP8 removed dead `txn_detail` CTE (ROW_NUMBER never filtered on), AP4 reduced `transactions` columns from 4 to 1 (only `amount` needed). Equivalent to Phase 1's OverdraftFeeSummary in aggressiveness.
- **Direct execution over queue mode.** Host-side ETL service races with container service for task_queue claims. Bypassed by running `dotnet run -- {date} {jobs}` directly. Same result, no race condition.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Host service race condition on task_queue**
- **Found during:** Task 2 (batch execution)
- **Issue:** A host-side ETL framework service polls `control.task_queue` and claims tasks before the container-local service. Host can't access container-local files at `/workspace/EtlReverseEngineering/...`, causing all tasks to fail with `DirectoryNotFoundException`.
- **Fix:** Bypassed queue mode entirely. Used direct `dotnet run -- {date} {jobs}` invocation for all 92 dates. Framework reads job conf, executes, writes output identically to queue mode.
- **Files modified:** None (execution approach only)
- **Verification:** All 92 dates per job produced output; Proofmark confirmed 276/276 PASS.

**2. [Rule 3 - Blocking] Host Proofmark service race on proofmark_test_queue**
- **Found during:** Task 2 (Proofmark verification)
- **Issue:** Same race condition -- host-side Proofmark claims queue rows but can't read config files at container paths, failing with `FileNotFoundError`.
- **Fix:** Repeatedly reset failed Proofmark tasks to `Pending` status, allowing container-local Proofmark to win the race and process them. After 5 reset cycles, all 276 comparisons completed as PASS.
- **Files modified:** None (DB operations only)
- **Verification:** `SELECT ... WHERE result = 'PASS' ... = 276` confirmed.

---

**Total deviations:** 2 auto-fixed (both blocking infrastructure issues)
**Impact on plan:** No scope creep. Same outcome achieved via direct execution instead of queue-based execution. All 276/276 PASS confirmed.

## Issues Encountered
- **Host service contention:** Both ETL framework and Proofmark have host-side instances that compete with container-local instances for queue-based work items. This was not encountered in Phase 1 (likely no host services were running then). Resolved by using direct execution for ETL and race-and-reset strategy for Proofmark.

## Anti-Pattern Remediation Results

| Job | AP1 | AP4 | AP8 | Result |
|-----|-----|-----|-----|--------|
| CustomerAccountSummary | Clean | Clean | Clean | 92/92 PASS, no changes to SQL |
| SecuritiesDirectory | Remediated (holdings removed) | Clean | Clean | 92/92 PASS |
| TransactionSizeBuckets | Remediated (accounts removed) | Remediated (3 cols removed) | Remediated (dead ROW_NUMBER CTE) | 92/92 PASS |

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- 3 of 10 Tier 2 jobs complete (this plan covers the simplest CSV multi-source batch)
- Remaining 7 Tier 2 jobs: 3 more CSV (CardAuthorizationSummary, FeeWaiverAnalysis, TopBranches) + 4 Parquet
- Batch execution pattern and AP remediation patterns established for reuse
- Host service contention documented -- future plans should use direct execution mode

---
*Phase: 02-tier-2-simple-multi-source*
*Completed: 2026-03-09*

## Self-Check: PASSED
- 21 files: all FOUND
- Commit 21e75ae: FOUND
- Proofmark: 276/276 PASS
