# Phase 2: Tier 2 - Simple Multi-Source - Research

**Researched:** 2026-03-09
**Domain:** ETL Reverse Engineering -- multi-source joins, Parquet output, batch execution at 10-job scale
**Confidence:** HIGH

## Summary

Phase 2 scales the proven Phase 1 RE workflow to 10 "simple multi-source" jobs. The key new challenges vs Tier 1 are: multi-source JOINs (most jobs join 2 data sources), Parquet output format (4 of 10 jobs), trailer handling (2 jobs with different trailer formats), and batch execution at 10x scale. None of these 10 jobs use external modules -- confirmed by scanning both V1 job confs and the ExternalModules directory.

The 13-step workflow is unchanged from Phase 1. The biggest risk areas are: (1) Parquet output, which is new territory -- Phase 1 was all CSV, (2) the FeeWaiverAnalysis LEFT JOIN on accounts that never uses any accounts columns (could be load-bearing like the ComplianceResolutionTime cartesian join), and (3) TopBranches has a non-deterministic timestamp trailer requiring `trailer_rows: 1` in Proofmark config.

**Primary recommendation:** Batch jobs in waves of 3-4, processing all CSV jobs first (familiar territory), then Parquet jobs. Start with CustomerAccountSummary or SecuritiesDirectory to establish multi-source patterns, then parallelize remaining jobs. TopBranches can run independently despite the dependency chain listed in the complexity analysis (it reads from datalake tables, not other jobs' output).

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| COMP-02 | Tier 2 batch complete -- 10 simple multi-source jobs | All 10 V1 job confs analyzed, anti-patterns identified, output formats characterized, Proofmark config patterns documented for both CSV and Parquet |
</phase_requirements>

## Standard Stack

### Core Infrastructure

Same as Phase 1 -- no changes.

| Component | Location | Purpose | Notes |
|-----------|----------|---------|-------|
| MockEtlFramework | `/workspace/MockEtlFramework` | ETL execution engine (.NET 8) | Read-only. Executes jobs via `control.task_queue` |
| Proofmark | `/workspace/proofmark` | Output comparison tool | Now also needed for Parquet comparison |
| PostgreSQL | `172.18.0.1:5432`, DB: `atc` | Integration bus | `control.jobs`, `control.task_queue`, `control.proofmark_test_queue` |
| EtlReverseEngineering | `/workspace/EtlReverseEngineering` | RE work product repo | Job confs, docs, proofmark configs |

### Path Tokens

Same as Phase 1 -- no changes.

| Token | Container Path | Used In |
|-------|---------------|---------|
| `{ETL_ROOT}` | `/workspace/MockEtlFramework` | V1 output paths (Proofmark LHS) |
| `{ETL_RE_ROOT}` | `/workspace` | Job conf paths, Proofmark config paths |
| `{ETL_RE_OUTPUT}` | `/workspace/MockEtlFramework/Output/curated_re` | RE output directory |

## Architecture Patterns

### Per-Job Directory Structure

Same as Phase 1. Each job gets:

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

### 13-Step Workflow (per job)

Unchanged from Phase 1. All steps are autonomous. Key difference: Step 7 (external module) is N/A for all Tier 2 jobs.

### Batch Execution Pattern

For 10 jobs, register all jobs in `control.jobs`, then queue all 920 tasks (10 jobs x 92 dates) at once. The ETL Framework handles parallel execution across jobs. Then queue 920 Proofmark comparisons.

**Important: Job registration is idempotent** -- the framework's lazy reload was confirmed working in Phase 1. No restart needed.

### Proofmark Path Patterns

**CSV jobs** (6 of 10): Same as Phase 1 -- file path to the CSV file.

```sql
-- CSV Proofmark queue
INSERT INTO control.proofmark_test_queue (config_path, lhs_path, rhs_path, job_key, date_key)
SELECT
  '{ETL_RE_ROOT}/EtlReverseEngineering/proofmark-configs/{JobName}.yaml',
  '{ETL_ROOT}/Output/curated/{jobDirName}/{tableDirName}/' || to_char(d.dt, 'YYYY-MM-DD') || '/{fileName}.csv',
  '{ETL_RE_OUTPUT}/{jobDirName}/{tableDirName}/' || to_char(d.dt, 'YYYY-MM-DD') || '/{fileName}.csv',
  '{JobName}',
  d.dt::date
FROM generate_series('2024-10-01'::date, '2024-12-31'::date, '1 day') d(dt);
```

**Parquet jobs** (4 of 10): Directory path (NOT file path). Proofmark's ParquetReader expects a directory containing `part-*.parquet` files.

```sql
-- Parquet Proofmark queue -- note: paths point to DIRECTORY, not file
INSERT INTO control.proofmark_test_queue (config_path, lhs_path, rhs_path, job_key, date_key)
SELECT
  '{ETL_RE_ROOT}/EtlReverseEngineering/proofmark-configs/{JobName}.yaml',
  '{ETL_ROOT}/Output/curated/{jobDirName}/{tableDirName}/' || to_char(d.dt, 'YYYY-MM-DD') || '/{fileName}',
  '{ETL_RE_OUTPUT}/{jobDirName}/{tableDirName}/' || to_char(d.dt, 'YYYY-MM-DD') || '/{fileName}',
  '{JobName}',
  d.dt::date
FROM generate_series('2024-10-01'::date, '2024-12-31'::date, '1 day') d(dt);
```

**Key difference:** Parquet `fileName` has NO extension (it's a directory name). CSV `fileName` includes `.csv`.

## Ten Tier 2 Jobs -- Detailed Analysis

### Job 1: CardStatusSnapshot

| Property | Value |
|----------|-------|
| V1 conf | `card_status_snapshot.json` |
| Data sources | 1: `datalake.cards` |
| SQL | GROUP BY `card_status`, `ifw_effective_date` |
| Output format | **Parquet**, 50 parts, Overwrite |
| Output columns | card_status, card_count, ifw_effective_date, etl_effective_date |
| Row count | 3 rows/date (stable) |
| Anti-patterns | **AP4**: `card_id`, `customer_id`, `card_number_masked`, `expiration_date` sourced but unused. Only `card_status` is needed in the SQL. |
| Notes | 3 rows across 50 parts is massively over-partitioned but must match V1 |

### Job 2: CustomerAccountSummary

| Property | Value |
|----------|-------|
| V1 conf | `customer_account_summary.json` |
| Data sources | 2: `datalake.customers`, `datalake.accounts` |
| SQL | LEFT JOIN customers to accounts on `c.id = a.customer_id`, GROUP BY customer, SUM/COUNT |
| Output format | CSV, LF, no trailer, Overwrite |
| Output columns | customer_id, first_name, last_name, account_count, active_balance, etl_effective_date |
| Row count | 2230 rows/date (stable) |
| Anti-patterns | None significant. All sourced columns are used. LEFT JOIN is correct (customers without accounts get count=0). |
| Notes | An external module `CustomerAccountSummaryBuilder.cs` exists but is NOT used by the V1 job conf. Ignore it. |

### Job 3: SecuritiesDirectory

| Property | Value |
|----------|-------|
| V1 conf | `securities_directory.json` |
| Data sources | 2: `datalake.securities`, `datalake.holdings` |
| SQL | SELECT from securities only, ORDER BY security_id |
| Output format | CSV, LF, no trailer, Overwrite |
| Output columns | security_id, ticker, security_name, security_type, sector, exchange, ifw_effective_date, etl_effective_date |
| Row count | 50 rows/date (stable) |
| Anti-patterns | **AP1**: `holdings` is sourced but NEVER referenced in SQL. Complete dead-end sourcing. Safe to remove. |
| Notes | Previously RE'd as a test during pre-Phase 1 setup, then wiped. Known good pattern. |

### Job 4: CardAuthorizationSummary

| Property | Value |
|----------|-------|
| V1 conf | `card_authorization_summary.json` |
| Data sources | 2: `datalake.card_transactions`, `datalake.cards` |
| SQL | JOIN card_transactions to cards on card_id, ROW_NUMBER (unused), `unused_summary` CTE (dead), GROUP BY card_type with approval counts |
| Output format | CSV, LF, **trailer** (`TRAILER\|{row_count}\|{date}`), Overwrite |
| Output columns | card_type, total_count, approved_count, declined_count, approval_rate, ifw_effective_date, etl_effective_date |
| Row count | 2 data rows + trailer (stable) |
| Anti-patterns | **AP4**: `card_txn_id` from card_transactions and `customer_id` from both sources -- `customer_id` from card_transactions used nowhere in output, `card_txn_id` only in dead ROW_NUMBER. **AP8**: ROW_NUMBER in `txn_detail` CTE never filtered on. `unused_summary` CTE is literally dead code (defined, never referenced). **AP7**: Integer division for `approval_rate` produces 0 for all values (501/535 = 0 in integer math). This is the V1 behavior and MUST be preserved. |
| Notes | Trailer is deterministic (date-based, no timestamp). Proofmark needs `trailer_rows: 1`. |

### Job 5: FeeWaiverAnalysis

| Property | Value |
|----------|-------|
| V1 conf | `fee_waiver_analysis.json` |
| Data sources | 2: `datalake.overdraft_events`, `datalake.accounts` |
| SQL | LEFT JOIN overdraft_events to accounts on account_id + ifw_effective_date, GROUP BY fee_waived |
| Output format | CSV, LF, no trailer, Overwrite |
| Output columns | fee_waived, event_count, total_fees, avg_fee, ifw_effective_date, etl_effective_date |
| Row count | 1-2 rows/date (varies) |
| Anti-patterns | **AP1**: `accounts` table is sourced with 7 columns but ZERO accounts columns appear in SELECT, WHERE, or GROUP BY. The LEFT JOIN is completely pointless -- no column from `a` is ever referenced. **AP4**: From overdraft_events: `overdraft_id`, `customer_id`, `event_timestamp` sourced but unused. From accounts: ALL columns unused. |
| Notes | **CRITICAL INVESTIGATION NEEDED**: The LEFT JOIN could be load-bearing if `account_id` has multiple matches in `accounts` for the same date, inflating COUNT/SUM. Same pattern as ComplianceResolutionTime's cartesian join. Must verify by comparing output with and without the JOIN before remediating. Phase 1 lesson: "AP8 cartesian joins can be load-bearing." |

### Job 6: TopHoldingsByValue

| Property | Value |
|----------|-------|
| V1 conf | `top_holdings_by_value.json` |
| Data sources | 2: `datalake.holdings`, `datalake.securities` |
| SQL | GROUP BY security_id, JOIN to securities, ROW_NUMBER ranking, CASE for rank buckets, WHERE rank <= 20 |
| Output format | **Parquet**, 50 parts, Overwrite |
| Output columns | security_id, ticker, security_name, sector, total_held_value, holder_count, rank, ifw_effective_date, etl_effective_date |
| Row count | 20 rows/date (stable) |
| Anti-patterns | **AP8**: `unused_cte` CTE is literally dead code (defined, never referenced). **AP4**: From holdings: `holding_id`, `investment_id`, `customer_id` sourced but unused. From securities: `security_type` sourced but unused. |
| Notes | **NAMING MISMATCH**: Job complexity analysis calls this "TopHoldings" but actual jobName is "TopHoldingsByValue". Use the actual name. The `rank` column is output as a CASE string ('Top 5', 'Top 10', etc.), NOT the ROW_NUMBER integer. |

### Job 7: TransactionSizeBuckets

| Property | Value |
|----------|-------|
| V1 conf | `transaction_size_buckets.json` |
| Data sources | 2: `datalake.transactions`, `datalake.accounts` |
| SQL | ROW_NUMBER (unused), CASE bucketing, GROUP BY amount_bucket |
| Output format | CSV, LF, no trailer, Overwrite |
| Output columns | amount_bucket, txn_count, total_amount, avg_amount, ifw_effective_date, etl_effective_date |
| Row count | 5 rows/date (stable) |
| Anti-patterns | **AP1**: `accounts` is sourced but NEVER referenced in SQL. Dead-end sourcing. **AP8**: ROW_NUMBER in `txn_detail` CTE never filtered on. **AP4**: From transactions: `transaction_id`, `account_id`, `txn_type` sourced but only `amount` is used. From accounts: ALL columns unused. |
| Notes | Like SecuritiesDirectory, the second data source is completely unused. Safe to remove after output verification. |

### Job 8: AccountOverdraftHistory

| Property | Value |
|----------|-------|
| V1 conf | `account_overdraft_history.json` |
| Data sources | 2: `datalake.overdraft_events`, `datalake.accounts` |
| SQL | JOIN overdraft_events to accounts on account_id + ifw_effective_date, SELECT with account_type enrichment |
| Output format | **Parquet**, 50 parts, Overwrite |
| Output columns | overdraft_id, account_id, customer_id, account_type, overdraft_amount, fee_amount, fee_waived, ifw_effective_date, etl_effective_date |
| Row count | 2-3 rows/date (varies) |
| Anti-patterns | **AP4**: From accounts: `customer_id`, `account_status`, `interest_rate`, `credit_limit` sourced but only `account_type` is used. From overdraft_events: `event_timestamp` sourced but unused. |
| Notes | This is the cleanest multi-source job -- the JOIN is meaningful (enriches with account_type). |

### Job 9: PreferenceChangeCount

| Property | Value |
|----------|-------|
| V1 conf | `preference_change_count.json` |
| Data sources | 2: `datalake.customer_preferences`, `datalake.customers` |
| SQL | RANK() window (not ROW_NUMBER), GROUP BY customer_id with MAX CASE pivots for email/sms opt-in |
| Output format | **Parquet**, 1 part, Overwrite |
| Output columns | customer_id, preference_count, has_email_opt_in, has_sms_opt_in, ifw_effective_date, etl_effective_date |
| Row count | 2230 rows/date (stable) |
| Anti-patterns | **AP1**: `customers` table is sourced but NEVER referenced in SQL. Dead-end sourcing. **AP4**: From customer_preferences: `updated_date` sourced but unused. `preference_id` only used in RANK ORDER BY. From customers: ALL columns unused. **AP8**: RANK() window function computes `rnk` but it's never used for filtering or output. |
| Notes | The RANK is applied but never consumed -- it's dead computation like the ROW_NUMBER pattern. |

### Job 10: TopBranches

| Property | Value |
|----------|-------|
| V1 conf | `top_branches.json` |
| Data sources | 2: `datalake.branch_visits`, `datalake.branches` |
| SQL | GROUP BY branch_id with COUNT, JOIN to branches for branch_name, RANK() for ranking |
| Output format | CSV, LF, **trailer** (`CONTROL\|{date}\|{row_count}\|{timestamp}`), Overwrite |
| Output columns | branch_id, branch_name, total_visits, rank, ifw_effective_date, etl_effective_date |
| Row count | 40 data rows + trailer (stable) |
| Anti-patterns | **AP10/AP8**: `WHERE bv.ifw_effective_date >= '2024-10-01'` is dead SQL -- DataSourcing already filters to the current effective date, making this WHERE clause a no-op. **AP4**: From branch_visits: `visit_id` sourced but unused (only `branch_id` matters for the COUNT). |
| Notes | **NON-DETERMINISTIC TRAILER**: `CONTROL\|{date}\|{row_count}\|{timestamp}` includes a timestamp that differs between runs. Proofmark config MUST set `trailer_rows: 1`. **DEPENDENCY CLARIFICATION**: Despite the complexity analysis claiming TopBranches depends on BranchVisitSummary -> BranchDirectory, TopBranches reads directly from `datalake.branch_visits` and `datalake.branches`. It has NO runtime data dependency on other jobs. |

## Anti-Pattern Summary

| Job | AP1 | AP2 | AP3 | AP4 | AP5 | AP6 | AP7 | AP8 | AP9 | AP10 |
|-----|-----|-----|-----|-----|-----|-----|-----|-----|-----|------|
| CardStatusSnapshot | - | - | N/A | YES | - | N/A | - | - | - | - |
| CustomerAccountSummary | - | - | N/A | - | - | N/A | - | - | - | - |
| SecuritiesDirectory | YES | - | N/A | - | - | N/A | - | - | - | - |
| CardAuthorizationSummary | - | - | N/A | YES | - | N/A | YES* | YES | - | - |
| FeeWaiverAnalysis | YES | - | N/A | YES | - | N/A | - | - | - | - |
| TopHoldingsByValue | - | - | N/A | YES | - | N/A | - | YES | - | - |
| TransactionSizeBuckets | YES | - | N/A | YES | - | N/A | - | YES | - | - |
| AccountOverdraftHistory | - | - | N/A | YES | - | N/A | - | - | - | - |
| PreferenceChangeCount | YES | - | N/A | YES | - | N/A | - | YES | - | - |
| TopBranches | - | - | N/A | YES | - | N/A | - | YES | - | YES |

*AP7 for CardAuthorizationSummary: integer division for `approval_rate` is load-bearing (V1 outputs 0). Preserve, don't fix.

**AP3/AP6 are N/A for all 10 jobs** -- no external modules in Tier 2. Confirmed by scanning V1 job confs (all use DataSourcing + Transformation + Writer) and the ExternalModules directory.

**Note about CustomerAccountSummaryBuilder.cs**: This external module EXISTS in `/workspace/MockEtlFramework/ExternalModules/` but is NOT referenced by the V1 `customer_account_summary.json` job conf. The V1 job uses a SQL Transformation instead. No external module rebuild will be needed in Phase 2.

## Don't Hand-Roll

Same as Phase 1, plus:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Parquet comparison | Custom Parquet diff | Proofmark with `reader: parquet` | Reads all part files, concatenates, does multiset comparison |
| Anti-pattern verification | Manual SQL diff | Run both V1 and RE, compare with Proofmark | Proofmark catches any output difference |
| Batch job registration | One-at-a-time registration | Bulk INSERT into `control.jobs` | Framework's lazy reload handles discovery |

## Common Pitfalls

### Pitfall 1: Parquet Path Format (NEW)
**What goes wrong:** Using a file path instead of directory path for Parquet Proofmark comparisons.
**Why it happens:** CSV uses file paths (`.../file.csv`), Parquet uses directory paths (`.../directory_name`).
**How to avoid:** Parquet `fileName` in job conf has NO extension -- it's a directory name containing `part-*.parquet` files. Proofmark's ParquetReader validates that the path is a directory.
**Warning signs:** Proofmark error "Path must exist and be a directory".

### Pitfall 2: Non-Deterministic Timestamp Trailer (TopBranches)
**What goes wrong:** TopBranches trailer contains `{timestamp}` which differs between V1 and RE runs. Proofmark compares the trailer as data and fails.
**Why it happens:** `CONTROL|{date}|{row_count}|{timestamp}` format includes runtime timestamp.
**How to avoid:** Set `trailer_rows: 1` in Proofmark config for TopBranches. CardAuthorizationSummary's `TRAILER|{row_count}|{date}` is deterministic but also needs `trailer_rows: 1`.
**Warning signs:** Proofmark FAIL with "unmatched rows" on the last line.

### Pitfall 3: Load-Bearing Dead Joins (FeeWaiverAnalysis)
**What goes wrong:** Removing the accounts LEFT JOIN from FeeWaiverAnalysis changes aggregate counts if account_id has multiple matches per date.
**Why it happens:** A LEFT JOIN that appears useless (no columns referenced) can still inflate row counts if the join produces duplicates.
**How to avoid:** Phase 1 lesson: "AP8 cartesian joins can be load-bearing." Test output with AND without the JOIN before committing to removal. If output changes, keep the JOIN and document it.
**Warning signs:** Proofmark COUNT mismatch.

### Pitfall 4: Integer Division is Load-Bearing (CardAuthorizationSummary)
**What goes wrong:** "Fixing" the integer division in `approval_rate` changes the output from 0 to a decimal.
**Why it happens:** `CAST(approved AS INTEGER) / CAST(total AS INTEGER)` is integer division in SQLite. The V1 output shows `approval_rate = 0` for all rows. This IS the intended output.
**How to avoid:** Preserve the CAST/integer division exactly. Document as AP7 but do NOT remediate -- it's load-bearing.
**Warning signs:** Proofmark reports `approval_rate` mismatch.

### Pitfall 5: Parquet numParts Must Match
**What goes wrong:** Using a different `numParts` value changes the physical Parquet file layout.
**Why it happens:** Proofmark compares logical data (concatenated rows), so numParts shouldn't affect PASS/FAIL. But matching V1's numParts is defensive.
**How to avoid:** Copy `numParts` exactly from V1 job conf.
**Warning signs:** Proofmark should still PASS even with different numParts, but match for safety.

### Pitfall 6: TopHoldings vs TopHoldingsByValue Naming
**What goes wrong:** Using "TopHoldings" (from complexity analysis) instead of "TopHoldingsByValue" (actual jobName).
**Why it happens:** The complexity analysis uses abbreviated names.
**How to avoid:** Always reference the actual V1 `jobName` from the job conf: `TopHoldingsByValue`. Use `top_holdings_by_value` for directory/file names.
**Warning signs:** Job not found, path not found errors.

### All Phase 1 Pitfalls Still Apply
- Output directory must use `{ETL_RE_OUTPUT}`
- Line endings must match V1 (all Tier 2 CSV jobs use LF)
- Date formatting: use `to_char(d.dt, 'YYYY-MM-DD')`
- Job name in conf must exactly match `control.jobs` registration
- Anti-pattern remediation: DO NOT change final SELECT column list

## Code Examples

### Parquet Proofmark Config (minimal)

```yaml
comparison_target: CardStatusSnapshot
reader: parquet
```

No `csv` section needed. No trailer handling. Parquet is simpler than CSV for Proofmark.

### CSV Proofmark Config with Trailer

```yaml
comparison_target: TopBranches
reader: csv
csv:
  header_rows: 1
  trailer_rows: 1
```

### Parquet Job Conf Pattern

```json
{
  "jobName": "CardStatusSnapshot_RE",
  "firstEffectiveDate": "2024-10-01",
  "modules": [
    {
      "type": "DataSourcing",
      "resultName": "cards",
      "schema": "datalake",
      "table": "cards",
      "columns": ["card_status"]
    },
    {
      "type": "Transformation",
      "resultName": "output",
      "sql": "SELECT c.card_status, COUNT(*) AS card_count, c.ifw_effective_date FROM cards c GROUP BY c.card_status, c.ifw_effective_date"
    },
    {
      "type": "ParquetFileWriter",
      "source": "output",
      "outputDirectory": "{ETL_RE_OUTPUT}",
      "numParts": 50,
      "writeMode": "Overwrite",
      "jobDirName": "card_status_snapshot",
      "fileName": "card_status_snapshot",
      "outputTableDirName": "card_status_snapshot"
    }
  ]
}
```

### Batch Job Registration (all 10 at once)

```sql
INSERT INTO control.jobs (job_name, description, job_conf_path, is_active)
VALUES
  ('CardStatusSnapshot_RE', 'RE of CardStatusSnapshot - AP4 remediated', '{ETL_RE_ROOT}/EtlReverseEngineering/job-confs/card_status_snapshot_re.json', true),
  ('CustomerAccountSummary_RE', 'RE of CustomerAccountSummary - clean', '{ETL_RE_ROOT}/EtlReverseEngineering/job-confs/customer_account_summary_re.json', true),
  -- ... (8 more)
;
```

### Batch Task Queueing (multiple jobs)

```sql
INSERT INTO control.task_queue (job_name, effective_date, status)
SELECT job_name, d.dt::date, 'Pending'
FROM (
  VALUES ('CardStatusSnapshot_RE'), ('CustomerAccountSummary_RE'), ('SecuritiesDirectory_RE')
  -- ... more job names
) AS j(job_name)
CROSS JOIN generate_series('2024-10-01'::date, '2024-12-31'::date, '1 day') d(dt);
```

### Batch Proofmark Verification

```sql
SELECT job_key, result, COUNT(*)
FROM control.proofmark_test_queue
WHERE job_key IN ('CardStatusSnapshot', 'CustomerAccountSummary', 'SecuritiesDirectory',
                  'CardAuthorizationSummary', 'FeeWaiverAnalysis', 'TopHoldingsByValue',
                  'TransactionSizeBuckets', 'AccountOverdraftHistory', 'PreferenceChangeCount',
                  'TopBranches')
GROUP BY job_key, result
ORDER BY job_key, result;
-- Expected: each job_key shows PASS = 92
```

## Dependency Chain Analysis

The ROADMAP states: "Dependency chain Job 22 -> Job 24 -> Job 26 and Job 22 -> Job 25 executed in correct order."

- Job 22 = BranchDirectory (Tier 1, **already completed** in Phase 1)
- Job 24 = BranchVisitSummary (Tier 3, Append mode -- **NOT in Phase 2**)
- Job 25 = BranchVisitPurposeBreakdown (Tier 3, Append mode -- **NOT in Phase 2**)
- Job 26 = TopBranches (Tier 2, **in Phase 2**)

**Finding:** TopBranches reads directly from `datalake.branch_visits` and `datalake.branches`. It does NOT read output from BranchVisitSummary. The dependency chain in the complexity analysis is a logical grouping (they share source tables), not a runtime data dependency. TopBranches can run independently and in parallel with all other Tier 2 jobs.

**Success criteria #3 ("dependency chain executed in correct order") is automatically satisfied** because BranchDirectory is already done (Phase 1), and TopBranches has no actual dependency on BranchVisitSummary/BranchVisitPurposeBreakdown.

## External Module Confirmation

**No external modules needed for Phase 2.** Confirmed via:

1. All 10 V1 job confs use only DataSourcing + Transformation + Writer (no `"type": "External"` modules)
2. Scanned `/workspace/MockEtlFramework/ExternalModules/` -- found `CustomerAccountSummaryBuilder.cs` but it is NOT referenced by the V1 `customer_account_summary.json` job conf
3. This means the external module rebuild protocol is NOT triggered during Phase 2

## Output Format Summary

| Job | Format | Parts | Line Ending | Trailer | Rows/Date |
|-----|--------|-------|-------------|---------|-----------|
| CardStatusSnapshot | Parquet | 50 | N/A | N/A | 3 |
| CustomerAccountSummary | CSV | N/A | LF | None | 2230 |
| SecuritiesDirectory | CSV | N/A | LF | None | 50 |
| CardAuthorizationSummary | CSV | N/A | LF | `TRAILER\|{row_count}\|{date}` | 2 |
| FeeWaiverAnalysis | CSV | N/A | LF | None | 1-2 |
| TopHoldingsByValue | Parquet | 50 | N/A | N/A | 20 |
| TransactionSizeBuckets | CSV | N/A | LF | None | 5 |
| AccountOverdraftHistory | Parquet | 50 | N/A | N/A | 2-3 |
| PreferenceChangeCount | Parquet | 1 | N/A | N/A | 2230 |
| TopBranches | CSV | N/A | LF | `CONTROL\|{date}\|{row_count}\|{timestamp}` | 40 |

## State of the Art

| Phase 1 Pattern | Phase 2 Extension | Impact |
|-----------------|-------------------|--------|
| CSV-only output | Parquet output (4 jobs) | New Proofmark config pattern, directory paths |
| 1 data source per job | 2 data sources per job (most) | JOIN verification before anti-pattern remediation |
| 3 jobs sequential | 10 jobs batchable | Batch SQL for registration and queueing |
| All AP8 was dead code | Some AP8/AP1 may be load-bearing | Must verify JOINs before removing |

## Open Questions

1. **FeeWaiverAnalysis LEFT JOIN**
   - What we know: The `accounts` LEFT JOIN uses no accounts columns in the output. It joins on `account_id + ifw_effective_date`.
   - What's unclear: Whether the JOIN produces duplicate rows that inflate COUNT/SUM values (making it load-bearing).
   - Recommendation: Test with and without the JOIN. If output changes, keep it. If output is identical, remove it (AP1 remediation). This is the same pattern as the ComplianceResolutionTime cartesian join from Phase 1.

2. **Parquet numParts impact on Proofmark**
   - What we know: Proofmark concatenates all part files and compares logical rows. numParts affects physical layout only.
   - What's unclear: Whether different numParts could cause ordering differences in the concatenated result (Proofmark uses multiset comparison, so ordering shouldn't matter).
   - Recommendation: Match V1 numParts exactly. It's zero-cost and eliminates any risk.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | Proofmark (Python, queue-driven) |
| Config file | Per-job YAML in `proofmark-configs/` |
| Quick run command | `PGPASSWORD=claude psql -h 172.18.0.1 -U claude -d atc -c "SELECT result, COUNT(*) FROM control.proofmark_test_queue WHERE job_key = '{JobName}' GROUP BY result;"` |
| Full suite command | `PGPASSWORD=claude psql -h 172.18.0.1 -U claude -d atc -c "SELECT job_key, result, COUNT(*) FROM control.proofmark_test_queue WHERE job_key IN ('CardStatusSnapshot','CustomerAccountSummary','SecuritiesDirectory','CardAuthorizationSummary','FeeWaiverAnalysis','TopHoldingsByValue','TransactionSizeBuckets','AccountOverdraftHistory','PreferenceChangeCount','TopBranches') GROUP BY job_key, result ORDER BY job_key, result;"` |

### Phase Requirements -> Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| COMP-02 | All 10 Tier 2 jobs 92/92 PASS | integration | Full suite query above | N/A (DB-driven) |
| RE-01 | BRD per job | manual-only | Check `jobs/{JobName}/BRD.md` exists | Wave 0 |
| RE-02 | FSD per job | manual-only | Check `jobs/{JobName}/FSD.md` exists | Wave 0 |
| RE-04 | RE job conf per job | integration | Task queue Succeeded for all 92 dates | N/A (DB-driven) |
| RE-07 | Proofmark config per job | integration | Proofmark queue returns results | N/A (DB-driven) |
| RE-08 | 92/92 PASS per job | integration | Per-job Proofmark query | N/A (DB-driven) |

### Sampling Rate
- **Per task commit:** Verify `task_queue` status for current batch (all Succeeded)
- **Per wave merge:** Verify `proofmark_test_queue` results for current batch (92/92 PASS per job)
- **Phase gate:** All 10 jobs show 92/92 PASS + all doc artifacts exist

### Wave 0 Gaps
- [ ] 10 Proofmark config YAMLs (4 Parquet, 6 CSV)
- [ ] 10 job conf JSONs in `job-confs/`
- [ ] 10 job doc directories in `jobs/`
- [ ] Verify Parquet Proofmark comparison works end-to-end (first Parquet job is the test)

## Sources

### Primary (HIGH confidence)
- V1 job confs: All 10 read directly from `/workspace/MockEtlFramework/JobExecutor/Jobs/`
- V1 output files: Sampled at multiple dates for all 10 jobs
- ExternalModules directory scan: Confirmed only `CustomerAccountSummaryBuilder.cs` exists (unused by V1 conf)
- Proofmark reader documentation: Verified CSV vs Parquet path expectations
- Proofmark configuration documentation: Verified YAML schema for both reader types
- Phase 1 RESEARCH.md and completed deliverables: Template patterns, workflow, pitfalls
- RE Blueprint: SQL templates, path tokens, conventions

### Secondary (MEDIUM confidence)
- Job complexity analysis: Tier assignments confirmed, but naming (TopHoldings vs TopHoldingsByValue) and dependency claims (TopBranches -> BranchVisitSummary) were inaccurate

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- identical to Phase 1, verified infrastructure
- Architecture: HIGH -- 13-step workflow proven in Phase 1, Parquet patterns verified from Proofmark docs and V1 output inspection
- Anti-patterns: HIGH -- direct SQL analysis of all 10 V1 job confs
- Pitfalls: HIGH -- drawn from Phase 1 lessons + new patterns identified from V1 analysis
- FeeWaiverAnalysis JOIN: MEDIUM -- requires runtime verification (same pattern as Phase 1's cartesian join discovery)

**Research date:** 2026-03-09
**Valid until:** Indefinite -- infrastructure is stable, V1 job confs are static
