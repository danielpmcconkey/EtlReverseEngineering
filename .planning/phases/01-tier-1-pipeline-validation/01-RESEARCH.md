# Phase 1: Tier 1 - Pipeline Validation - Research

**Researched:** 2026-03-09
**Domain:** ETL Reverse Engineering -- job conf authoring, anti-pattern assessment, Proofmark validation
**Confidence:** HIGH

## Summary

Phase 1 proves the entire 13-step RE workflow end-to-end on the 3 simplest jobs in the portfolio: BranchDirectory, ComplianceResolutionTime, and OverdraftFeeSummary. All three are Tier 1 -- single data source, no external module, Overwrite mode, CSV output. They have zero dependencies on other jobs.

The goal is NOT to RE hard jobs. The goal is to validate the full pipeline (analysis -> docs -> job conf -> execution -> Proofmark verification) and establish a repeatable pattern that all subsequent phases inherit. Every deliverable template, every SQL convention, every Proofmark pattern set here becomes the baseline for 102 more jobs.

**Primary recommendation:** Process jobs sequentially (one complete before starting the next). Use the first job to establish all doc templates and conventions, then apply them with refinements to jobs 2 and 3. Capture lessons learned after each job.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| DELIV-01 | BRD with numbered requirements and evidence | Template established per-job; evidence cites original job conf SQL, data source tables, output format |
| DELIV-02 | FSD with numbered specs, traceability to BRD | Template with REQ->SPEC numbering; must document anti-pattern remediations |
| DELIV-03 | Test strategy with traceability to FSD/BRD | Template referencing Proofmark as primary validation; 92-date coverage matrix |
| DELIV-04 | `_re` JSON job conf based on FSD | Job conf authoring patterns documented below; must use `{ETL_RE_OUTPUT}` token |
| DELIV-05 | External modules only when needed | Tier 1 jobs have NO external modules; this requirement is trivially satisfied (document "none needed" in FSD) |
| DELIV-06 | Output manifesto | All 3 jobs produce exactly 1 CSV output each; manifesto documents file paths, format, row counts |
| DELIV-07 | Proofmark config YAML with evidence | Patterns documented below; ComplianceResolutionTime needs `trailer_rows: 1` |
| DELIV-08 | 92/92 Proofmark PASS | Queue-driven execution via `control.task_queue` then `control.proofmark_test_queue` |
| PROC-01 | Zero human input | All SQL templates, DB commands, and verification queries are documented for autonomous execution |
| PROC-02 | Proofmark failure retry (max 5) | Triage->RCA->fix->doc update->retry loop; query patterns for detecting failures documented |
| PROC-03 | Iterative learning | Lessons learned captured after each job; available for Tier 2 |
| ANTI-01 | Assess all 10 anti-patterns per job | Checklist of AP1-AP10 per job; findings documented in BRD |
| ANTI-02 | AP3 SQL-first approach | Tier 1 has no external modules; document this as baseline for later tiers |
| ANTI-03 | AP6 row-by-row conversion | Tier 1 has no C# code to convert; document this as baseline |
| COMP-01 | Tier 1 complete (3 jobs) | All 3 jobs with 92/92 PASS and full doc sets |
</phase_requirements>

## Standard Stack

### Core Infrastructure

| Component | Location | Purpose | Notes |
|-----------|----------|---------|-------|
| MockEtlFramework | `/workspace/MockEtlFramework` | ETL execution engine (.NET 8) | Read-only. Executes jobs via `control.task_queue` |
| Proofmark | `/workspace/proofmark` | Python output comparison tool | Validates byte-identical output via `control.proofmark_test_queue` |
| PostgreSQL | `172.18.0.1:5432`, DB: `atc` | Integration bus | `control.jobs`, `control.task_queue`, `control.proofmark_test_queue` |
| EtlReverseEngineering | `/workspace/EtlReverseEngineering` | RE work product repo | Job confs, docs, proofmark configs |

### Path Tokens

| Token | Container Path | Used In |
|-------|---------------|---------|
| `{ETL_ROOT}` | `/workspace/MockEtlFramework` | V1 output paths (Proofmark LHS), framework internals |
| `{ETL_RE_ROOT}` | `/workspace` | Job conf paths in `control.jobs`, Proofmark config paths |
| `{ETL_RE_OUTPUT}` | `/workspace/MockEtlFramework/Output/curated_re` | RE output directory in job confs, Proofmark RHS paths |

### Database Access

```bash
PGPASSWORD=claude psql -h 172.18.0.1 -U claude -d atc
```

## Architecture Patterns

### Per-Job Directory Structure

```
/workspace/EtlReverseEngineering/
  job-confs/
    branch_directory_re.json
    compliance_resolution_time_re.json
    overdraft_fee_summary_re.json
  jobs/
    BranchDirectory/
      BRD.md
      FSD.md
      test-strategy.md
      output-manifesto.md
      anti-pattern-assessment.md     # or inline in BRD
    ComplianceResolutionTime/
      ...
    OverdraftFeeSummary/
      ...
  proofmark-configs/
    BranchDirectory.yaml
    ComplianceResolutionTime.yaml
    OverdraftFeeSummary.yaml
```

### 13-Step Workflow (per job)

This is the core execution pattern. Every step is autonomous.

| Step | Action | Artifacts Produced |
|------|--------|-------------------|
| 1 | Read original job conf | Understanding of V1 pipeline |
| 2 | Check original output (format, rows, stability) | Output characterization |
| 3 | Write BRD (numbered reqs, evidence, anti-patterns) | `jobs/{JobName}/BRD.md` |
| 4 | Write FSD (numbered specs, traceable to BRD) | `jobs/{JobName}/FSD.md` |
| 5 | Write test strategy (traceable to FSD/BRD) | `jobs/{JobName}/test-strategy.md` |
| 6 | Write `_re` job conf (remediate anti-patterns) | `job-confs/{job_name}_re.json` |
| 7 | Write external module (ONLY if needed) | N/A for Tier 1 |
| 8 | Write Proofmark config YAML | `proofmark-configs/{JobName}.yaml` |
| 9 | Register job in `control.jobs` | DB row |
| 10 | Queue 92 dates in `control.task_queue` | 92 DB rows |
| 11 | Verify all tasks Succeeded | Query `control.task_queue` |
| 12 | Queue 92 Proofmark comparisons | 92 DB rows in `control.proofmark_test_queue` |
| 13 | Verify 92/92 PASS | Query `control.proofmark_test_queue` |

### Job Conf Authoring Pattern

RE job confs follow V1 structure with these mandatory changes:

1. **`jobName`** gets `_RE` suffix (e.g., `BranchDirectory_RE`)
2. **`outputDirectory`** MUST use `{ETL_RE_OUTPUT}` token, never a relative path
3. Anti-pattern remediations applied to SQL and module config
4. Same `jobDirName`, `outputTableDirName`, and `fileName` as V1 (output path structure must match for Proofmark)

```json
{
  "jobName": "BranchDirectory_RE",
  "firstEffectiveDate": "2024-10-01",
  "modules": [
    {
      "type": "DataSourcing",
      "resultName": "branches",
      "schema": "datalake",
      "table": "branches",
      "columns": ["branch_id", "branch_name", "address_line1", "city", "state_province", "postal_code", "country"]
    },
    {
      "type": "Transformation",
      "resultName": "branch_dir",
      "sql": "..."
    },
    {
      "type": "CsvFileWriter",
      "source": "branch_dir",
      "includeHeader": true,
      "writeMode": "Overwrite",
      "lineEnding": "CRLF",
      "outputDirectory": "{ETL_RE_OUTPUT}",
      "jobDirName": "branch_directory",
      "fileName": "branch_directory.csv",
      "outputTableDirName": "branch_directory"
    }
  ]
}
```

### Anti-Patterns to Avoid in Job Confs

- **DO NOT** use `"outputDirectory": "Output/curated"` -- this resolves against `{ETL_ROOT}` and writes to the V1 output directory
- **DO NOT** change `jobDirName`, `outputTableDirName`, or `fileName` -- Proofmark path comparison depends on matching structure
- **DO NOT** add or remove columns from the SQL output -- byte-identical match required
- **DO** use `{ETL_RE_OUTPUT}` for `outputDirectory`
- **DO** keep the same `lineEnding` as V1 (CRLF or LF)

## Three Tier 1 Jobs -- Detailed Analysis

### Job 1: BranchDirectory

| Property | Value |
|----------|-------|
| V1 conf | `/workspace/MockEtlFramework/JobExecutor/Jobs/branch_directory.json` |
| Data source | `datalake.branches` (7 columns) |
| SQL | CTE with ROW_NUMBER dedup by `branch_id`, ORDER BY `branch_id` |
| Output format | CSV, header, CRLF line endings, no trailer |
| Output columns | branch_id, branch_name, address_line1, city, state_province, postal_code, country, ifw_effective_date, etl_effective_date |
| Row count | 40 data rows per date (stable) |
| Anti-patterns | AP8 likely (ROW_NUMBER with ORDER BY same column in PARTITION and ORDER, producing non-deterministic dedup if duplicates exist) |

**AP Assessment Notes:**
- AP1 (Dead-End Sourcing): Clean -- all sourced columns appear in output
- AP3 (Unnecessary External): N/A -- no external module
- AP4 (Unused Columns): Clean -- all 7 columns used
- AP6 (Row-by-Row): N/A -- no C# code
- AP8 (Complex/Dead SQL): The CTE uses `ROW_NUMBER() OVER (PARTITION BY branch_id ORDER BY branch_id)` which is a no-op dedup (ordering by the partition key guarantees arbitrary row selection). This should be simplified or documented.
- AP10 (Over-Sourcing): No explicit date range in DataSourcing -- falls back to `__etlEffectiveDate` (single day). Clean.

### Job 2: ComplianceResolutionTime

| Property | Value |
|----------|-------|
| V1 conf | `/workspace/MockEtlFramework/JobExecutor/Jobs/compliance_resolution_time.json` |
| Data source | `datalake.compliance_events` (6 columns) |
| SQL | CTE filtering to Cleared events with review_date, calculates `days_to_resolve` via `julianday()`, then aggregates by event_type with a bizarre `JOIN compliance_events ON 1=1` to get `ifw_effective_date` |
| Output format | CSV, header, LF line endings, trailer: `TRAILER\|{row_count}\|{date}` |
| Output columns | event_type, resolved_count, total_days, avg_resolution_days, ifw_effective_date, etl_effective_date |
| Row count | 5 data rows + 1 trailer = 7 lines total (header + 5 data + trailer) |
| Anti-patterns | AP8 (the `JOIN compliance_events ON 1=1` is a cartesian join hack to get `ifw_effective_date` into the GROUP BY result -- could be simplified), AP7 possible (integer division for avg) |

**AP Assessment Notes:**
- AP1: Clean -- single source, all used
- AP3: N/A
- AP4: `customer_id` and `event_date` are sourced but not in output (though `event_date` is used in the `julianday` calculation). `customer_id` is unused -- AP4 violation.
- AP5: The `julianday()` date arithmetic with CAST to INTEGER produces truncated averages (integer division). This is a design choice, not necessarily an anti-pattern, but should be documented.
- AP8: The `JOIN compliance_events ON 1=1` is dead SQL complexity -- `ifw_effective_date` is already available on the `resolved` CTE rows since they come from `compliance_events`. The ROW_NUMBER in the CTE is also never used for filtering.

**CRITICAL:** The trailer format `TRAILER|{row_count}|{date}` is deterministic (no `{timestamp}`). The Proofmark config needs `trailer_rows: 1` to tell Proofmark this is a trailer line.

### Job 3: OverdraftFeeSummary

| Property | Value |
|----------|-------|
| V1 conf | `/workspace/MockEtlFramework/JobExecutor/Jobs/overdraft_fee_summary.json` |
| Data source | `datalake.overdraft_events` (7 columns) |
| SQL | CTE with ROW_NUMBER (unused), then GROUP BY `fee_waived` with SUM, COUNT, AVG, ORDER BY `fee_waived` |
| Output format | CSV, header, LF line endings, no trailer |
| Output columns | fee_waived, total_fees, event_count, avg_fee, ifw_effective_date, etl_effective_date |
| Row count | 2 data rows per date (fee_waived=0 and fee_waived=1) |
| Anti-patterns | AP4 (sources overdraft_id, account_id, customer_id, event_timestamp but only uses fee_amount and fee_waived), AP8 (ROW_NUMBER in CTE never used for filtering) |

**AP Assessment Notes:**
- AP1: Clean -- single source table is used
- AP3: N/A
- AP4: YES -- `account_id`, `customer_id`, `event_timestamp` sourced but never referenced. `overdraft_id` used only in ROW_NUMBER ORDER BY which itself is unused.
- AP8: YES -- The ROW_NUMBER window function computes `rn` but the outer query never filters on it. Dead SQL.
- AP10: No explicit date range. Falls back to `__etlEffectiveDate`. Clean.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Output comparison | Custom diff script | Proofmark + `control.proofmark_test_queue` | Hash-based multiset comparison handles column ordering, null semantics, trailer handling |
| Job execution | Direct `dotnet run` calls | `control.task_queue` + ETL FW `--service` mode | Advisory locks, failure cascade, parallel execution across jobs |
| Date generation | Manual date lists | `generate_series('2024-10-01'::date, '2024-12-31'::date, '1 day')` | 92 dates, no off-by-one risk |
| Path resolution | Hardcoded paths | `{ETL_RE_OUTPUT}`, `{ETL_RE_ROOT}`, `{ETL_ROOT}` tokens | Works across container/host boundary |

## Common Pitfalls

### Pitfall 1: Output Directory Token
**What goes wrong:** Using `"outputDirectory": "Output/curated"` in RE job conf writes to the V1 output directory, corrupting originals.
**Why it happens:** V1 confs use relative paths that resolve against `{ETL_ROOT}`.
**How to avoid:** Always use `"outputDirectory": "{ETL_RE_OUTPUT}"` in RE confs.
**Warning signs:** V1 output files changing modification times.

### Pitfall 2: Line Ending Mismatch
**What goes wrong:** Proofmark FAIL on otherwise identical data because line endings differ.
**Why it happens:** BranchDirectory uses CRLF, the other two use LF. Easy to copy-paste and forget.
**How to avoid:** Check V1 job conf `lineEnding` property and replicate exactly.
**Warning signs:** Proofmark reports "line break mismatch" in results.

### Pitfall 3: Trailer Configuration
**What goes wrong:** ComplianceResolutionTime has a trailer (`TRAILER|{row_count}|{date}`). If the RE conf omits `trailerFormat`, output won't match. If Proofmark config omits `trailer_rows: 1`, the trailer is compared as data.
**How to avoid:** Copy `trailerFormat` from V1 conf. Set `trailer_rows: 1` in Proofmark YAML for jobs with trailers.
**Warning signs:** Proofmark reports row count mismatch or unmatched rows.

### Pitfall 4: ETL Framework Job Cache
**What goes wrong:** After registering a new job in `control.jobs`, the ETL Framework doesn't see it because it caches the job registry at startup.
**Why it happens:** Framework reads `control.jobs` at startup and caches. (Lazy reload fix was reportedly added but not yet confirmed.)
**How to avoid:** Restart the ETL Framework after registering new jobs. Or verify lazy reload works on the first job.
**Warning signs:** Tasks stuck in Pending status, no log output for the new job.

### Pitfall 5: Date Formatting in Proofmark Queue SQL
**What goes wrong:** Using `d.dt::text` in SQL produces timestamps with timezone suffix (`2024-10-18 00:00:00-04`), breaking path construction.
**How to avoid:** Use `to_char(d.dt, 'YYYY-MM-DD')` for all date-to-string conversions in path construction.
**Warning signs:** Proofmark errors about file/directory not found.

### Pitfall 6: Anti-Pattern Remediation Breaking Output
**What goes wrong:** Removing dead SQL (AP8) or unused columns (AP4) from the Transformation SQL changes the output.
**Why it happens:** The CsvFileWriter dumps ALL columns from the DataFrame. Removing columns from the SELECT changes the output schema.
**How to avoid:** The Transformation SQL output columns must exactly match V1. Anti-pattern remediation applies to the DataSourcing inputs and intermediate SQL, NOT to the final SELECT list.
**Warning signs:** Proofmark schema mismatch errors.

### Pitfall 7: Job Name Must Match DB Registration
**What goes wrong:** Job name in conf says `BranchDirectory_RE` but registered as `BranchDirectory_re` in `control.jobs`.
**Why it happens:** Case sensitivity mismatch.
**How to avoid:** `jobName` in the JSON conf must exactly match `job_name` in `control.jobs`.
**Warning signs:** "Job not found" errors or tasks never picked up.

## Code Examples

### Register an RE Job

```sql
INSERT INTO control.jobs (job_name, description, job_conf_path, is_active)
VALUES (
  'BranchDirectory_RE',
  'RE of BranchDirectory - AP8 remediated (removed dead ROW_NUMBER)',
  '{ETL_RE_ROOT}/EtlReverseEngineering/job-confs/branch_directory_re.json',
  true
);
```

### Queue 92 Dates for Execution

```sql
INSERT INTO control.task_queue (job_name, effective_date, status)
SELECT 'BranchDirectory_RE', d.dt::date, 'Pending'
FROM generate_series('2024-10-01'::date, '2024-12-31'::date, '1 day') d(dt);
```

### Verify All Tasks Succeeded

```sql
SELECT status, COUNT(*)
FROM control.task_queue
WHERE job_name = 'BranchDirectory_RE'
GROUP BY status;
-- Expected: Succeeded = 92
```

### Queue 92 Proofmark Comparisons

```sql
INSERT INTO control.proofmark_test_queue (config_path, lhs_path, rhs_path, job_key, date_key)
SELECT
  '{ETL_RE_ROOT}/EtlReverseEngineering/proofmark-configs/BranchDirectory.yaml',
  '{ETL_ROOT}/Output/curated/branch_directory/branch_directory/' || to_char(d.dt, 'YYYY-MM-DD') || '/branch_directory.csv',
  '{ETL_RE_OUTPUT}/branch_directory/branch_directory/' || to_char(d.dt, 'YYYY-MM-DD') || '/branch_directory.csv',
  'BranchDirectory',
  d.dt::date
FROM generate_series('2024-10-01'::date, '2024-12-31'::date, '1 day') d(dt);
```

### Verify 92/92 PASS

```sql
SELECT result, COUNT(*)
FROM control.proofmark_test_queue
WHERE job_key = 'BranchDirectory'
GROUP BY result;
-- Expected: PASS = 92
```

### Reset Failed Tasks for Retry

```sql
UPDATE control.task_queue
SET status = 'Pending', error_message = NULL
WHERE job_name = 'BranchDirectory_RE' AND status = 'Failed';
```

### Minimal Proofmark Config (no trailer)

```yaml
comparison_target: BranchDirectory
reader: csv
csv:
  header_rows: 1
  trailer_rows: 0
```

### Proofmark Config with Trailer

```yaml
comparison_target: ComplianceResolutionTime
reader: csv
csv:
  header_rows: 1
  trailer_rows: 1
```

## Anti-Pattern Assessment Checklist

For each Tier 1 job, assess against all 10 anti-patterns. Document findings in BRD.

| AP | Name | BranchDirectory | ComplianceResolutionTime | OverdraftFeeSummary |
|----|------|-----------------|--------------------------|---------------------|
| AP1 | Dead-End Sourcing | Clean | Clean | Clean |
| AP2 | Duplicated Logic | N/A (first job) | N/A | N/A |
| AP3 | Unnecessary External | N/A (no external) | N/A | N/A |
| AP4 | Unused Columns | Clean | YES: `customer_id` sourced, unused | YES: `account_id`, `customer_id`, `event_timestamp` unused |
| AP5 | Asymmetric Null/Default | Clean | Document integer division behavior | Clean |
| AP6 | Row-by-Row Iteration | N/A (no C#) | N/A | N/A |
| AP7 | Magic Values | Clean | Clean | Clean |
| AP8 | Complex/Dead SQL | YES: ROW_NUMBER never filtered | YES: `JOIN ON 1=1` hack, unused ROW_NUMBER | YES: ROW_NUMBER never filtered |
| AP9 | Misleading Names | Clean | Clean | Clean |
| AP10 | Over-Sourcing Dates | Clean | Clean | Clean |

**Remediation approach for AP4 and AP8:**
- Remove unused columns from `DataSourcing.columns` list (AP4)
- Remove dead SQL constructs from Transformation SQL (AP8)
- **CRITICAL:** Do NOT change the final SELECT column list -- output schema must match V1 exactly

## State of the Art

| V1 Pattern | RE Pattern | Impact |
|------------|------------|--------|
| Relative `outputDirectory` | `{ETL_RE_OUTPUT}` token | Prevents writing to V1 output |
| Unused DataSourcing columns | Trim to only needed columns | Cleaner configs, documents true dependencies |
| Dead SQL (unused CTEs/window funcs) | Simplified SQL | Easier to understand and maintain |
| No documentation | Full BRD/FSD/test strategy per job | Reproducible understanding |

## Open Questions

1. **ETL Framework lazy reload**: Hobson reportedly added lazy reload for `control.jobs`. Not yet tested. If it doesn't work, the framework must be restarted after each job registration. Test this on the first job.
   - What we know: The fix was reportedly committed
   - What's unclear: Whether it's deployed and functional in the current runtime
   - Recommendation: Test with BranchDirectory_RE. If it fails, document the workaround (restart).

2. **RE output directory creation**: `{ETL_RE_OUTPUT}` resolves to `/workspace/MockEtlFramework/Output/curated_re`. This directory may not exist yet.
   - What we know: BD's resurrection state mentions it doesn't exist
   - What's unclear: Whether SecuritiesDirectory testing created it (since that was done and then wiped)
   - Recommendation: `mkdir -p` the directory before first job execution.

3. **Anti-pattern remediation vs output fidelity**: When simplifying SQL (AP8), do intermediate query results change even if final output doesn't?
   - What we know: SQLite in-memory execution is deterministic for the same effective SQL
   - What's unclear: Whether removing unused CTEs could affect SQLite optimizer behavior
   - Recommendation: Always verify with Proofmark after remediation. That's what it's for.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | Proofmark (Python, queue-driven) |
| Config file | Per-job YAML in `proofmark-configs/` |
| Quick run command | `PGPASSWORD=claude psql -h 172.18.0.1 -U claude -d atc -c "SELECT result, COUNT(*) FROM control.proofmark_test_queue WHERE job_key = '{JobName}' GROUP BY result;"` |
| Full suite command | `PGPASSWORD=claude psql -h 172.18.0.1 -U claude -d atc -c "SELECT job_key, result, COUNT(*) FROM control.proofmark_test_queue GROUP BY job_key, result ORDER BY job_key, result;"` |

### Phase Requirements -> Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DELIV-08 | 92/92 Proofmark PASS per job | integration | Query `control.proofmark_test_queue` per job_key | N/A (DB-driven) |
| DELIV-01 | BRD exists with numbered reqs | manual-only | Check file exists at `jobs/{JobName}/BRD.md` | Wave 0 |
| DELIV-02 | FSD exists with traceability | manual-only | Check file exists at `jobs/{JobName}/FSD.md` | Wave 0 |
| DELIV-04 | RE job conf produces valid output | integration | ETL task_queue status = Succeeded for all 92 dates | N/A (DB-driven) |
| ANTI-01 | All anti-patterns assessed | manual-only | Check BRD contains AP1-AP10 assessment | Wave 0 |
| PROC-01 | Zero human input | process | Full workflow completes autonomously | N/A (process) |
| COMP-01 | All 3 jobs complete | integration | All 3 job_keys show 92 PASS in proofmark queue | N/A (DB-driven) |

### Sampling Rate
- **Per task commit:** Verify task_queue status for current job (all 92 Succeeded)
- **Per wave merge:** Verify proofmark_test_queue results for current job (92/92 PASS)
- **Phase gate:** All 3 jobs show 92/92 PASS + all doc artifacts exist

### Wave 0 Gaps
- [ ] `proofmark-configs/BranchDirectory.yaml` -- Proofmark config
- [ ] `proofmark-configs/ComplianceResolutionTime.yaml` -- Proofmark config (needs trailer_rows: 1)
- [ ] `proofmark-configs/OverdraftFeeSummary.yaml` -- Proofmark config
- [ ] `mkdir -p /workspace/MockEtlFramework/Output/curated_re` -- RE output directory
- [ ] Verify ETL Framework lazy reload works (or document restart workaround)

## Sources

### Primary (HIGH confidence)
- V1 job confs: `branch_directory.json`, `compliance_resolution_time.json`, `overdraft_fee_summary.json` -- read directly
- V1 output files: sampled for all 3 jobs at 2024-10-01 -- read directly
- MockEtlFramework Architecture.md -- full framework documentation
- MockEtlFramework configuration.md -- path tokens, env vars, appsettings
- Proofmark Documentation (overview, configuration, queue-runner) -- comparison pipeline docs
- RE Blueprint (`/workspace/AtcStrategy/POC5/re-blueprint.md`) -- SQL templates, gotchas, conventions
- Anti-patterns (`/workspace/AtcStrategy/POC5/anti-patterns.md`) -- AP1-AP10 definitions
- PROJECT.md (`/workspace/EtlReverseEngineering/.planning/PROJECT.md`) -- 13-step workflow, constraints
- DB schema -- `control.jobs`, `control.task_queue`, `control.proofmark_test_queue` verified via `\d`

### Secondary (MEDIUM confidence)
- BD resurrection state -- documents infrastructure issues found/fixed during SecuritiesDirectory RE
- Job complexity analysis -- tier assignments and job characteristics

### Tertiary (LOW confidence)
- ETL Framework lazy reload status -- reportedly fixed but untested

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all infrastructure verified through direct inspection of code, DB schema, and documentation
- Architecture: HIGH -- 13-step workflow is documented and was already tested on SecuritiesDirectory
- Pitfalls: HIGH -- drawn from actual issues encountered during SecuritiesDirectory RE (session 2)
- Anti-pattern assessment: HIGH -- direct analysis of V1 SQL in job confs
- Lazy reload status: LOW -- reported but unverified

**Research date:** 2026-03-09
**Valid until:** Indefinite -- this infrastructure is stable and under Dan's control
