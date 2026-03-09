# Phase 3: Tier 3 - Append Mode - Research

**Researched:** 2026-03-09
**Domain:** ETL Reverse Engineering -- Append mode cumulative output, chronological execution, Proofmark validation at 13-job scale
**Confidence:** HIGH

## Summary

Phase 3 introduces the first fundamental behavior change from Phases 1-2: **Append mode**. All 13 Tier 3 jobs use `writeMode: Append`, meaning each date's output file contains ALL data from Oct 1 through that date, growing cumulatively. The framework handles this by reading the prior date's output via `DatePartitionHelper.FindLatestPartition`, dropping the `etl_effective_date` column, unioning it with the current date's data, re-injecting the current date's `etl_effective_date`, and writing the combined result. This means **execution order is load-bearing** -- dates MUST run Oct 1 through Dec 31 in strict chronological order, and a failure at any date cascades (the framework already enforces this via fail-fast in `TaskQueueService.ProcessBatch`).

None of the 13 jobs use external modules -- all are DataSourcing + SQL Transformation + standard writers, same pattern as Phases 1-2. Two jobs output Parquet (2 parts each), the rest are CSV. One job (`BranchVisitsByCustomerCsvAppendTrailer`) introduces two new DataSourcing features not seen in prior phases: `additionalFilter` and `mostRecent`. One job (`DailyTransactionVolume`) has a `{timestamp}` trailer requiring `trailer_match: skip`. The dependency chain `DailyTransactionSummary -> DailyTransactionVolume -> MonthlyTransactionTrend` is NOT a data dependency (all three source from `datalake.transactions`/`datalake.branches`), but execution ordering should respect it for safety.

**CRITICAL FIX REQUIRED:** The Phase 2 sequencing bug (config files must exist on disk before task queuing) must be fixed in `re-blueprint.md` before Phase 3 execution. This is a one-line addition that prevents the ~65% turn waste seen in Phase 2.

**Primary recommendation:** Fix the blueprint sequencing bug first. Then batch jobs into 3-4 waves. Start with simple Append jobs (1-2 DS, no trailer, no special features) to validate the Append pattern works in RE, then escalate to jobs with trailers, special DataSourcing features, and Parquet. The dependency chain jobs (DailyTransactionSummary/DailyTransactionVolume/MonthlyTransactionTrend) should run in order within the same or sequential waves.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| COMP-03 | Tier 3 complete -- 13 Append mode jobs | All 13 V1 job confs analyzed. Append mode mechanics fully understood from framework source (CsvFileWriter, ParquetFileWriter, DatePartitionHelper, TaskQueueService). Anti-pattern candidates identified. Proofmark config patterns documented for both CSV and Parquet Append output. New DataSourcing features (additionalFilter, mostRecent) verified in ModuleFactory. Blueprint sequencing fix identified. |
</phase_requirements>

## Standard Stack

### Core Infrastructure

Same as Phases 1-2 -- no changes.

| Component | Location | Purpose | Notes |
|-----------|----------|---------|-------|
| MockEtlFramework | `/workspace/MockEtlFramework` | ETL execution engine (.NET 8) | Read-only. Handles Append mode via DatePartitionHelper |
| Proofmark | `/workspace/proofmark` | Output comparison tool | CSV and Parquet comparison |
| PostgreSQL | `172.18.0.1:5432`, DB: `atc` | Integration bus | `control.jobs`, `control.task_queue`, `control.proofmark_test_queue` |
| EtlReverseEngineering | `/workspace/EtlReverseEngineering` | RE work product repo | Job confs, docs, proofmark configs |

### Path Tokens

Same as Phases 1-2 -- no changes.

| Token | Container Path | Used In |
|-------|---------------|---------|
| `{ETL_ROOT}` | `/workspace/MockEtlFramework` | V1 output paths (Proofmark LHS) |
| `{ETL_RE_ROOT}` | `/workspace` | Job conf paths, Proofmark config paths |
| `{ETL_RE_OUTPUT}` | `/workspace/MockEtlFramework/Output/curated_re` | RE output directory |

## Architecture Patterns

### Append Mode Mechanics (CRITICAL -- new for Phase 3)

**How Append works in the framework:**

1. Writer calls `DatePartitionHelper.FindLatestPartition(tableDir)` which scans date-named subdirectories and returns the latest one (by string sort descending of `yyyy-MM-dd` names)
2. If a prior partition exists, reads its output file, strips the trailer (if any), drops the `etl_effective_date` column, and unions it with the current date's DataFrame
3. Re-injects `etl_effective_date` with the current date's value for ALL rows (prior + new)
4. Writes the combined result to the current date's partition directory

**Key implications:**
- **etl_effective_date is OVERWRITTEN** -- all rows in a given date's file show that date, not their original date. This is by design.
- **Trailer row_count is cumulative** -- e.g., DailyTransactionSummary: 2,489 rows on Oct 1, 12,471 on Oct 5, 230,435 on Dec 31
- **Execution order is load-bearing** -- if Oct 15 runs before Oct 14, Oct 15 would union with Oct 13's data (the latest existing partition), skipping Oct 14 entirely
- **The framework enforces order** -- `ClaimNextJobBatch` sorts tasks by effective_date. The advisory lock ensures one thread claims ALL tasks for a job. Tasks run sequentially within the batch.
- **Fail-fast cascades** -- if any date fails, all remaining dates in the batch are marked Failed with a "prior failure" message

**Append mode for Parquet** works identically to CSV: reads prior partition's parquet directory via `DataFrame.FromParquet`, drops `etl_effective_date`, unions, re-injects, writes.

### Append Mode Task Queuing

**IMPORTANT:** For Append mode jobs, all 92 dates must be queued as a single batch per job. The framework claims ALL pending tasks for a job at once (advisory lock prevents splitting). If tasks are queued in multiple batches, a worker might claim batch 1 (Oct 1-15) while another claims batch 2 (Oct 16-31), which would break the chronological chain.

Standard queue pattern (same SQL as Overwrite, the framework handles ordering):
```sql
INSERT INTO control.task_queue (job_name, effective_date, status)
SELECT 'JobName_RE', d.dt::date, 'Pending'
FROM generate_series('2024-10-01'::date, '2024-12-31'::date, '1 day') d(dt);
```

### Append Mode Retry Protocol

If an Append job fails mid-execution:

1. Check which dates succeeded vs failed: `SELECT effective_date, status FROM control.task_queue WHERE job_name = 'JobName_RE' ORDER BY effective_date`
2. Inspect the RE output directory: the last successfully written date's output should be intact
3. Check if any output exists for the failed date: `ls {ETL_RE_OUTPUT}/{jobDirName}/{tableDirName}/{failed_date}/` -- if it exists, delete it (partial write)
4. Reset failed tasks: `UPDATE control.task_queue SET status = 'Pending', error_message = NULL WHERE job_name = 'JobName_RE' AND status = 'Failed'`
5. Re-queue -- the framework will pick up from the earliest Pending date and FindLatestPartition will find the last Succeeded date's output to union with

**Nuclear option (full re-run):** If the output chain is corrupted, delete the entire RE output directory for the job and reset ALL tasks to Pending:
```sql
-- Then from bash: rm -rf {ETL_RE_OUTPUT}/{jobDirName}/{tableDirName}/
UPDATE control.task_queue SET status = 'Pending', error_message = NULL, started_at = NULL, completed_at = NULL
WHERE job_name = 'JobName_RE';
```

### New DataSourcing Features (first appearance in Tier 3)

**`additionalFilter`** -- Used by BranchVisitsByCustomerCsvAppendTrailer: `"additionalFilter": "customer_id < 1500"`. Adds a WHERE clause to the DataSourcing query beyond the standard effective_date filter. Must be preserved in RE conf verbatim.

**`mostRecent`** -- Used by BranchVisitsByCustomerCsvAppendTrailer on the `customers` DataSourcing: `"mostRecent": true`. Queries the datalake for the latest date ON OR BEFORE the effective date (instead of exact date match). Must be preserved in RE conf.

Both are supported by `ModuleFactory.cs` and `DataSourcing.cs`. Verified in source code.

### Per-Job Directory Structure

Same as Phases 1-2:

```
/workspace/EtlReverseEngineering/
  job-confs/{job_name}_re.json
  jobs/{JobName}/
    BRD.md
    FSD.md
    test-strategy.md
    output-manifesto.md
    anti-pattern-assessment.md
  proofmark-configs/{JobName}.yaml
```

### Dependency Chain

Three Tier 3 jobs have listed dependencies:

| Job | Depends On | Dependency Type |
|-----|-----------|-----------------|
| BranchVisitSummary (Job 24) | BranchDirectory (Job 22) | **Already RE'd** in Phase 1 |
| BranchVisitPurposeBreakdown (Job 25) | BranchDirectory (Job 22) | **Already RE'd** in Phase 1 |
| DailyTransactionVolume (Job 5) | DailyTransactionSummary (Job 2) | **Both in Tier 3** -- NOT a data dep (both source from datalake.transactions) |
| MonthlyTransactionTrend (Job 6) | DailyTransactionVolume (Job 5) | **Both in Tier 3** -- NOT a data dep (both source from datalake.transactions) |

All four "dependencies" are NOT data dependencies -- each job sources directly from datalake tables, not from another job's output. However, the dependency chain should be respected in execution ordering as a safety measure (run DailyTransactionSummary before DailyTransactionVolume before MonthlyTransactionTrend).

### Blueprint Sequencing Fix (MANDATORY before Phase 3)

**The bug:** In Phase 2, agents queued framework tasks before config files existed on disk. The framework picked up tasks immediately, failed to find configs, and fail-fast cascaded ~860 wasted turns.

**The fix:** Add an explicit ordering constraint to `re-blueprint.md` between steps 7 and 8:

> **CRITICAL ORDERING CONSTRAINT:** Steps 6-7 (write job conf and Proofmark config files) MUST complete and be verified on disk (`test -f path`) BEFORE steps 8-11 (register job, queue tasks, queue Proofmark). The framework and Proofmark workers pick up queued items immediately. If config files don't exist yet, the first task fails and fail-fast cascades SKIPs across the entire batch. For Append mode jobs this is catastrophic -- a cascaded failure means ALL 92 dates fail.

This fix applies to `re-blueprint.md` at `/workspace/AtcStrategy/POC5/re-blueprint.md`.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Append cumulation | Custom append logic in SQL | Framework's `writeMode: Append` | Framework handles prior partition lookup, trailer stripping, union, etl_effective_date injection |
| Chronological ordering | Manual date-by-date execution | Framework's `ClaimNextJobBatch` with advisory locks | Tasks auto-sort by effective_date, single-thread-per-job guaranteed |
| Parquet append | Custom parquet merge logic | Framework's `ParquetFileWriter` Append mode | Same union logic as CSV, handles part files correctly |
| additionalFilter | WHERE clause in SQL Transformation | DataSourcing `additionalFilter` field | Applied before the effective_date filter, composes correctly |
| mostRecent lookup | Complex SQL date windowing | DataSourcing `mostRecent` field | Framework handles the latest-date-on-or-before logic |

## Common Pitfalls

### Pitfall 1: Append Output Corruption from Non-Chronological Execution
**What goes wrong:** If dates execute out of order, FindLatestPartition picks up the wrong prior partition, creating gaps or duplicates in cumulative output.
**Why it happens:** Multiple workers claiming the same job's tasks, or tasks queued in non-sequential batches.
**How to avoid:** Queue all 92 dates at once. The framework's advisory lock + date sorting handles the rest. Never queue Append jobs across multiple INSERT statements with different date ranges.
**Warning signs:** Row counts that don't grow monotonically across dates, or missing date ranges in the cumulative output.

### Pitfall 2: Config Files Not on Disk Before Task Queuing (Phase 2 Bug)
**What goes wrong:** Framework picks up queued task, can't find job conf, fails. For Append jobs, fail-fast cascades ALL 92 dates.
**Why it happens:** Agent writes SQL to insert into task_queue before writing the JSON conf file.
**How to avoid:** Write conf files -> verify on disk with `test -f` -> THEN register job -> THEN queue tasks. The blueprint fix makes this explicit.
**Warning signs:** First task fails with "job conf not found" or similar, followed by 91 SKIPPED tasks.

### Pitfall 3: Stale RE Output from Prior Failed Runs
**What goes wrong:** A prior failed Append run left partial output. New run's FindLatestPartition picks up the stale output, corrupting the chain.
**Why it happens:** Framework writes output file before marking task Succeeded. If it crashes between write and status update, stale output exists.
**How to avoid:** Before retrying an Append job, check for and clean output from the failed date. For a full re-run, delete the entire RE output directory for the job.
**Warning signs:** Row count on Oct 1 (the first date) is higher than expected, or contains data from dates beyond Oct 1.

### Pitfall 4: Timestamp Trailers in Append Mode
**What goes wrong:** DailyTransactionVolume has `CONTROL|{date}|{row_count}|{timestamp}` trailer. The timestamp is non-deterministic. For Append mode, the trailer row_count is cumulative.
**Why it happens:** Append mode re-writes the entire file including trailer for every date.
**How to avoid:** Proofmark config must use `trailer_rows: 1` and `trailer_match: skip` for DailyTransactionVolume. Other Tier 3 trailers without `{timestamp}` can be compared normally (row_count and date are deterministic).
**Warning signs:** Proofmark fails on the trailer line only.

### Pitfall 5: mostRecent and additionalFilter in RE Confs
**What goes wrong:** RE conf omits `mostRecent: true` or `additionalFilter` from DataSourcing, changing the data fetched.
**Why it happens:** These fields are new in Tier 3, not present in any Phase 1-2 RE confs. Easy to miss during conf generation.
**How to avoid:** Copy these fields verbatim from V1 conf. They are functional requirements, not anti-patterns.
**Warning signs:** Row count mismatch on every date, or data for wrong customers appearing.

### Pitfall 6: Append Mode RE Output Cleanup Between Retries
**What goes wrong:** Agent resets tasks to Pending without cleaning output, then the Append chain picks up stale partial output from the failed run.
**Why it happens:** Overwrite mode doesn't need output cleanup (each date writes independently). Agents may apply Overwrite retry patterns to Append jobs.
**How to avoid:** Append retry protocol must include output inspection and cleanup. Document this in the plan explicitly.

## Code Examples

### RE Job Conf for Append Mode CSV (with trailer)

```json
{
  "jobName": "DailyTransactionSummary_RE",
  "firstEffectiveDate": "2024-10-01",
  "modules": [
    {
      "type": "DataSourcing",
      "resultName": "transactions",
      "schema": "datalake",
      "table": "transactions",
      "columns": ["transaction_id", "account_id", "txn_type", "amount"]
    },
    {
      "type": "Transformation",
      "resultName": "result",
      "sql": "SELECT ... ORDER BY ..."
    },
    {
      "type": "CsvFileWriter",
      "source": "result",
      "includeHeader": true,
      "trailerFormat": "TRAILER|{row_count}|{date}",
      "writeMode": "Append",
      "lineEnding": "LF",
      "outputDirectory": "{ETL_RE_OUTPUT}",
      "jobDirName": "daily_transaction_summary",
      "fileName": "daily_transaction_summary.csv",
      "outputTableDirName": "daily_transaction_summary"
    }
  ]
}
```

**Key difference from Overwrite mode:** `"writeMode": "Append"` and `"outputDirectory": "{ETL_RE_OUTPUT}"`. Everything else is standard.

### RE Job Conf with additionalFilter and mostRecent

```json
{
  "type": "DataSourcing",
  "resultName": "visits",
  "schema": "datalake",
  "table": "branch_visits",
  "columns": ["visit_id", "customer_id", "branch_id", "visit_timestamp", "visit_purpose"],
  "additionalFilter": "customer_id < 1500"
},
{
  "type": "DataSourcing",
  "resultName": "customers",
  "schema": "datalake",
  "table": "customers",
  "columns": ["id", "sort_name"],
  "mostRecent": true
}
```

### Proofmark Config for Append CSV with Deterministic Trailer

```yaml
comparison_target: DailyTransactionSummary
reader: csv
csv:
  header_rows: 1
  trailer_rows: 1
```

Note: no `trailer_match: skip` needed -- the trailer contains `{row_count}|{date}`, both deterministic. The cumulative row_count will match if the Append chain executed correctly.

### Proofmark Config for Append CSV with Non-Deterministic Trailer

```yaml
comparison_target: DailyTransactionVolume
reader: csv
csv:
  header_rows: 1
  trailer_rows: 1
  trailer_match: skip
```

`trailer_match: skip` required because `{timestamp}` is non-deterministic.

### Proofmark Config for Append Parquet

```yaml
comparison_target: CustomerAddressHistory
reader: parquet
```

Same as Overwrite Parquet -- no trailer handling needed.

### Proofmark Queue for Append Mode

Same SQL as Overwrite mode. Each date gets its own Proofmark comparison, comparing the V1 cumulative output against the RE cumulative output:

```sql
-- CSV Append
INSERT INTO control.proofmark_test_queue (config_path, lhs_path, rhs_path, job_key, date_key)
SELECT
  '{ETL_RE_ROOT}/EtlReverseEngineering/proofmark-configs/DailyTransactionSummary.yaml',
  '{ETL_ROOT}/Output/curated/daily_transaction_summary/daily_transaction_summary/' || to_char(d.dt, 'YYYY-MM-DD') || '/daily_transaction_summary.csv',
  '{ETL_RE_OUTPUT}/daily_transaction_summary/daily_transaction_summary/' || to_char(d.dt, 'YYYY-MM-DD') || '/daily_transaction_summary.csv',
  'DailyTransactionSummary',
  d.dt::date
FROM generate_series('2024-10-01'::date, '2024-12-31'::date, '1 day') d(dt);

-- Parquet Append (directory paths, no file extension)
INSERT INTO control.proofmark_test_queue (config_path, lhs_path, rhs_path, job_key, date_key)
SELECT
  '{ETL_RE_ROOT}/EtlReverseEngineering/proofmark-configs/CustomerAddressHistory.yaml',
  '{ETL_ROOT}/Output/curated/customer_address_history/customer_address_history/' || to_char(d.dt, 'YYYY-MM-DD') || '/customer_address_history',
  '{ETL_RE_OUTPUT}/customer_address_history/customer_address_history/' || to_char(d.dt, 'YYYY-MM-DD') || '/customer_address_history',
  'CustomerAddressHistory',
  d.dt::date
FROM generate_series('2024-10-01'::date, '2024-12-31'::date, '1 day') d(dt);
```

## Tier 3 Job Catalog

### Complete Job Inventory

| # | Job Name | DS | Format | Line End | Trailer | Special | Anti-Pattern Candidates |
|---|----------|---:|--------|----------|---------|---------|------------------------|
| 1 | DailyTransactionSummary | 2 | CSV | LF | `TRAILER\|{row_count}\|{date}` | dep chain root | AP1: branches sourced but may not be used in SQL |
| 2 | DailyTransactionVolume | 1 | CSV | CRLF | `CONTROL\|{date}\|{row_count}\|{timestamp}` | dep on #1 | AP8: CTE selects min/max but only outputs 4 cols |
| 3 | MonthlyTransactionTrend | 2 | CSV | LF | None | dep on #2 | TBD |
| 4 | BranchVisitSummary | 2 | CSV | LF | `TRAILER\|{row_count}\|{date}` | dep on BranchDirectory | TBD |
| 5 | BranchVisitPurposeBreakdown | 3 | CSV | CRLF | `END\|{row_count}` | dep on BranchDirectory | TBD |
| 6 | BranchVisitsByCustomerCsvAppendTrailer | 2 | CSV | LF | `TRAILER\|{row_count}\|{date}` | additionalFilter, mostRecent | TBD |
| 7 | CustomerAddressHistory | 2 | Parquet(2) | N/A | None | | TBD |
| 8 | CustomerContactInfo | 3 | Parquet(2) | N/A | None | | TBD |
| 9 | CustomerSegmentMap | 3 | CSV | LF | None | | TBD |
| 10 | DailyWireVolume | 1 | CSV | LF | None | | TBD |
| 11 | MerchantCategoryDirectory | 2 | CSV | LF | None | | AP1: sources cards but may not use it |
| 12 | PreferenceTrend | 1 | CSV | LF | None | | TBD |
| 13 | TransactionCategorySummary | 2 | CSV | LF | `END\|{row_count}` | | TBD |

### Preliminary Anti-Pattern Candidates

From job-complexity-analysis.md and V1 conf inspection:

- **MerchantCategoryDirectory** -- AP1 flagged: "sources cards, never uses it". SQL is only 104 chars, needs verification.
- **DailyTransactionSummary** -- AP1 candidate: sources `branches` but SQL only references `transactions`. Needs SQL analysis.
- **DailyTransactionVolume** -- AP8 candidate: CTE computes `min_amount` and `max_amount` but only outputs 4 columns. Dead columns in CTE.

Full anti-pattern assessment will be done per-job during execution (steps 3-4 of the workflow).

### Batch Grouping Recommendation

**Wave 1 (4 jobs -- simple Append, no trailers, no special features):**
- DailyWireVolume (1 DS, CSV, no trailer)
- PreferenceTrend (1 DS, CSV, no trailer)
- MerchantCategoryDirectory (2 DS, CSV, no trailer, known AP1)
- CustomerSegmentMap (3 DS, CSV, no trailer)

**Wave 2 (4 jobs -- Append with trailers, CRLF, dependency chain):**
- DailyTransactionSummary (2 DS, CSV, trailer, dep chain root)
- DailyTransactionVolume (1 DS, CSV, CRLF, timestamp trailer -- MUST run after DailyTransactionSummary)
- MonthlyTransactionTrend (2 DS, CSV, no trailer -- MUST run after DailyTransactionVolume)
- TransactionCategorySummary (2 DS, CSV, END trailer)

**Wave 3 (3 jobs -- Append with dependencies on Phase 1, special features):**
- BranchVisitSummary (2 DS, CSV, trailer, dep on BranchDirectory)
- BranchVisitPurposeBreakdown (3 DS, CSV, CRLF, END trailer, dep on BranchDirectory)
- BranchVisitsByCustomerCsvAppendTrailer (2 DS, CSV, trailer, additionalFilter + mostRecent)

**Wave 4 (2 jobs -- Parquet Append):**
- CustomerAddressHistory (2 DS, Parquet, 2 parts)
- CustomerContactInfo (3 DS, Parquet, 2 parts)

### Wave Sequencing Constraints

- Wave 2 internal: DailyTransactionSummary BEFORE DailyTransactionVolume BEFORE MonthlyTransactionTrend
- Waves 1, 3, 4 are independent of each other and Wave 2
- Within each wave, jobs without dependencies can be parallelized (multiple agents)
- All Append jobs within a single wave: each job's 92 tasks must complete before Proofmark queuing for that job

## Anti-Patterns to Avoid

### Not treating Overwrite retry patterns as Append-safe
Overwrite mode: reset tasks to Pending, re-run, done. Append mode: must inspect and potentially clean RE output before retrying. Different protocols.

### Queuing Proofmark before all 92 dates succeed
For Append mode, intermediate dates' output is VALID but only if the full chain completes. A Proofmark comparison on date 45 is only meaningful if dates 1-44 also ran correctly. Queue Proofmark only AFTER verifying all 92 tasks Succeeded.

### Splitting Append job tasks across multiple queue inserts
If tasks are inserted in batches (e.g., Oct 1-15, then Oct 16-31), a worker might claim the first batch, process it, then another worker claims the second batch. Since advisory locks are transaction-scoped and released after claim, this could lead to two workers operating on the same job's output directory sequentially but with a gap. Use a single INSERT for all 92 dates.

## State of the Art

| Old Approach (Phase 1-2) | New Approach (Phase 3) | Impact |
|--------------------------|------------------------|--------|
| Overwrite mode -- each date independent | Append mode -- dates are cumulative, order matters | Must validate full 92-date chain integrity |
| Any execution order works | Strict chronological order required | Framework handles this, but retry logic changes |
| Simple retry: reset + re-run | Append retry: inspect output + clean stale data + re-run | New retry protocol needed |
| No special DataSourcing fields | additionalFilter, mostRecent (first use) | Must preserve in RE confs |
| All CSV or all Parquet per phase | Mixed CSV (11) + Parquet (2) | Both format patterns needed |

## Open Questions

1. **DailyTransactionSummary branches usage**
   - What we know: V1 conf sources `branches` table (2 columns: branch_id, branch_name), but the SQL only references `transactions`
   - What's unclear: Whether `branches` is dead-end sourcing (AP1) or used in some way not visible in the SQL
   - Recommendation: Analyze the full SQL during BRD creation. If branches is unused, remediate as AP1.

2. **Dependency chain reality**
   - What we know: All three dependency chain jobs (DailyTransactionSummary, DailyTransactionVolume, MonthlyTransactionTrend) source from datalake tables, not each other's output
   - What's unclear: Why the dependency was flagged in the original analysis. Could be a V1 operational convention rather than a data dependency.
   - Recommendation: Respect the ordering as a safety measure but don't gate execution on it. Jobs can run in parallel safely since they don't read each other's output.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | Proofmark (custom, `/workspace/proofmark`) |
| Config file | Per-job YAML in `/workspace/EtlReverseEngineering/proofmark-configs/` |
| Quick run command | `Proofmark single-job comparison via control.proofmark_test_queue` |
| Full suite command | `Queue all 1196 comparisons (13 jobs x 92 dates) and verify PASS` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| COMP-03 | All 13 Tier 3 jobs 92/92 PASS | integration | Proofmark queue + verify | Wave 0: 13 YAML configs needed |

### Sampling Rate
- **Per job completion:** Verify 92/92 PASS in `control.proofmark_test_queue`
- **Per wave merge:** Verify all jobs in wave are 92/92 PASS
- **Phase gate:** Full 1196/1196 PASS (13 x 92) before phase completion

### Wave 0 Gaps
- [ ] Fix `re-blueprint.md` sequencing constraint (between steps 7 and 8)
- [ ] 13 Proofmark config YAML files (created per-job during execution)
- [ ] 13 RE job confs (created per-job during execution)
- [ ] No framework changes needed -- Append mode, additionalFilter, mostRecent all supported

## Sources

### Primary (HIGH confidence)
- `/workspace/MockEtlFramework/Lib/Modules/CsvFileWriter.cs` -- Append mode implementation, trailer handling, line endings
- `/workspace/MockEtlFramework/Lib/Modules/ParquetFileWriter.cs` -- Parquet Append mode implementation
- `/workspace/MockEtlFramework/Lib/DatePartitionHelper.cs` -- Prior partition discovery logic
- `/workspace/MockEtlFramework/Lib/Control/TaskQueueService.cs` -- Advisory lock, date sorting, fail-fast cascade
- `/workspace/MockEtlFramework/Lib/ModuleFactory.cs` -- additionalFilter, mostRecent field support verified
- `/workspace/MockEtlFramework/Lib/Modules/DataSourcing.cs` -- mostRecent/mostRecentPrior behavior documented
- All 13 V1 job conf files in `/workspace/MockEtlFramework/JobExecutor/Jobs/`
- V1 output files inspected for cumulative growth pattern
- `/workspace/AtcStrategy/POC5/phase-2-sequencing-bug.md` -- Sequencing bug details and fix
- `/workspace/AtcStrategy/POC5/re-blueprint.md` -- Current workflow steps
- `/workspace/AtcStrategy/POC5/job-complexity-analysis.md` -- Tier classification and dependency chains

### Secondary (MEDIUM confidence)
- Anti-pattern candidates for individual jobs -- preliminary from conf inspection, full assessment during execution

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- same infrastructure as Phases 1-2, no changes needed
- Architecture: HIGH -- Append mode mechanics fully traced through framework source code
- Pitfalls: HIGH -- based on Phase 2 execution experience + framework source code analysis
- Anti-patterns: MEDIUM -- preliminary assessment from conf inspection only, full analysis during execution

**Research date:** 2026-03-09
**Valid until:** 2026-04-09 (stable -- framework code unlikely to change)
