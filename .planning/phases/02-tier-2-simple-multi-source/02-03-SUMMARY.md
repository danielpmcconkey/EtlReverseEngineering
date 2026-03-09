---
phase: 02-tier-2-simple-multi-source
plan: 03
subsystem: etl-re
tags: [parquet, proofmark, multi-source, join, ranking, case-bucketing]

requires:
  - phase: 01-tier-1-pipeline-validation
    provides: "RE workflow, Proofmark infrastructure, control tables, CSV comparison pattern"
provides:
  - "Parquet Proofmark comparison pattern validated (reader: parquet, directory paths)"
  - "ParquetFileWriter job conf pattern proven (numParts, fileName as directory)"
  - "CardStatusSnapshot_RE -- 92/92 PASS, AP4 remediated"
  - "TopHoldingsByValue_RE -- 92/92 PASS, AP4+AP8 remediated"
affects: [02-tier-2-simple-multi-source, 03-tier-3-multi-source-complex, 04-tier-4-external-module]

tech-stack:
  added: []
  patterns: [parquet-proofmark-comparison, parquet-file-writer-conf, directory-path-proofmark]

key-files:
  created:
    - job-confs/card_status_snapshot_re.json
    - job-confs/top_holdings_by_value_re.json
    - proofmark-configs/CardStatusSnapshot.yaml
    - proofmark-configs/TopHoldingsByValue.yaml
    - jobs/CardStatusSnapshot/BRD.md
    - jobs/CardStatusSnapshot/FSD.md
    - jobs/CardStatusSnapshot/test-strategy.md
    - jobs/CardStatusSnapshot/output-manifesto.md
    - jobs/CardStatusSnapshot/anti-pattern-assessment.md
    - jobs/TopHoldingsByValue/BRD.md
    - jobs/TopHoldingsByValue/FSD.md
    - jobs/TopHoldingsByValue/test-strategy.md
    - jobs/TopHoldingsByValue/output-manifesto.md
    - jobs/TopHoldingsByValue/anti-pattern-assessment.md
  modified: []

key-decisions:
  - "Parquet Proofmark configs are minimal: just comparison_target + reader: parquet (no csv section)"
  - "AP4 for CardStatusSnapshot removed 5 of 6 sourced columns (card_type also unused, not just the 4 in plan)"
  - "AP8 for TopHoldingsByValue: unused_cte was unambiguously dead (defined, never referenced)"
  - "quantity retained in THV holdings DataSourcing per plan guidance (not listed as unused despite not appearing in SQL)"

patterns-established:
  - "Parquet Proofmark: directory paths, no file extension, reader: parquet config"
  - "ParquetFileWriter conf: fileName is a directory name, numParts must match V1, outputDirectory uses {ETL_RE_OUTPUT}"
  - "Multi-source Parquet job: multiple DataSourcing modules with AP4 applied per-source"

requirements-completed: [COMP-02]

duration: 55min
completed: 2026-03-09
---

# Phase 2 Plan 3: CardStatusSnapshot + TopHoldingsByValue Summary

**First Parquet RE jobs: 184/184 Proofmark PASS validating Parquet comparison pattern with directory paths, ParquetFileWriter confs, and multi-source JOIN with rank bucketing**

## Performance

- **Duration:** 55 min
- **Started:** 2026-03-09T18:49:55Z
- **Completed:** 2026-03-09T19:45:33Z
- **Tasks:** 2
- **Files created:** 14

## Accomplishments
- CardStatusSnapshot_RE: 92/92 Proofmark PASS -- first Parquet job in the project, AP4 remediated (5 unused columns removed)
- TopHoldingsByValue_RE: 92/92 Proofmark PASS -- multi-source Parquet with JOIN, ROW_NUMBER ranking, CASE bucketing, AP4+AP8 remediated
- Parquet Proofmark comparison pattern validated end-to-end: directory paths (not file paths), reader: parquet (no csv section)
- ParquetFileWriter job conf pattern proven: numParts must match V1, fileName is a directory name, outputDirectory uses {ETL_RE_OUTPUT}
- Complete doc sets for both jobs (BRD, FSD, test-strategy, output-manifesto, anti-pattern-assessment)

## Task Commits

Each task was committed atomically:

1. **Task 1: RE workflow for CardStatusSnapshot and TopHoldingsByValue (docs + job confs)** - `ca6554f` (feat)
2. **Task 2: Batch register, execute, and verify both Parquet jobs (92/92 PASS each)** - DB operations only, no file commit

## Files Created/Modified
- `job-confs/card_status_snapshot_re.json` - RE job conf with ParquetFileWriter, numParts: 50, AP4 remediated
- `job-confs/top_holdings_by_value_re.json` - RE job conf with ParquetFileWriter, numParts: 50, AP4+AP8 remediated
- `proofmark-configs/CardStatusSnapshot.yaml` - Parquet Proofmark config (reader: parquet)
- `proofmark-configs/TopHoldingsByValue.yaml` - Parquet Proofmark config (reader: parquet)
- `jobs/CardStatusSnapshot/*.md` - Complete doc set (5 files)
- `jobs/TopHoldingsByValue/*.md` - Complete doc set (5 files)

## Decisions Made
- Parquet Proofmark configs need only `comparison_target` and `reader: parquet` -- no csv section, no header/trailer config
- AP4 for CardStatusSnapshot: plan identified 4 unused columns, but `card_type` is also sourced and never used in SQL. Removed all 5 non-`card_status` columns.
- AP8 for TopHoldingsByValue: `unused_cte` is textbook dead code -- defined but its alias is never referenced in any subsequent CTE or SELECT. Safe removal, zero output impact.
- `quantity` retained in TopHoldingsByValue holdings DataSourcing even though not in SQL -- plan explicitly listed only `holding_id`, `investment_id`, `customer_id` as unused

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Job conf path used container path instead of {ETL_RE_ROOT} token**
- **Found during:** Task 2 (job registration)
- **Issue:** Initial INSERT used `/workspace/EtlReverseEngineering/...` as job_conf_path instead of `{ETL_RE_ROOT}/EtlReverseEngineering/...`. The ETL framework runs on the host where `/workspace` doesn't exist.
- **Fix:** Updated control.jobs paths to use `{ETL_RE_ROOT}` token, reset failed tasks
- **Files modified:** None (DB-only fix)
- **Verification:** All 184 tasks succeeded after fix

---

**Total deviations:** 1 auto-fixed (Rule 1 - bug in job registration path)
**Impact on plan:** Minor. The plan's SQL template used `{ETL_RE_ROOT}` correctly; I just didn't interpolate it properly on first attempt.

## Issues Encountered
- ETL framework job registry caching caused persistent failures for 4 TopHoldingsByValue dates. The framework cached the old (incorrect) job_conf_path before the UPDATE. Required multiple delete/re-queue cycles for the last 4 dates (2024-12-28 through 2024-12-31) before the framework picked up the corrected path.
- Concurrent plan executors queued duplicate Proofmark entries (184 instead of 92 per job). The other executor cleaned up the duplicates. No impact on final results.
- Proofmark processing was slow (~55 min total) due to competing with ~350 pending comparisons from concurrent plan executions.

## Parquet-Specific Findings
- **Directory paths work:** Proofmark Parquet comparison accepts directory paths containing `part-*.parquet` files. No trailing slash needed.
- **Minimal config:** Parquet configs need only `comparison_target` and `reader: parquet`. No csv section, no header/trailer configuration.
- **Over-partitioning:** CardStatusSnapshot has 3 rows across 50 parts (most parts empty). TopHoldingsByValue has 20 rows across 50 parts. Both match V1 exactly despite being absurdly over-partitioned.
- **Lessons for Plan 02-04:** The remaining 2 Parquet jobs can follow this exact pattern. The Parquet Proofmark comparison pattern is proven.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Parquet Proofmark comparison pattern validated -- ready for remaining Parquet jobs (Plan 02-04)
- ParquetFileWriter job conf pattern documented and proven
- Multi-source JOIN pattern validated with TopHoldingsByValue

---
*Phase: 02-tier-2-simple-multi-source*
*Completed: 2026-03-09*
