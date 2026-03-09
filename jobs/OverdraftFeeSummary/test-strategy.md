# OverdraftFeeSummary -- Test Strategy

**Job:** OverdraftFeeSummary_RE
**Traces to:** FSD (jobs/OverdraftFeeSummary/FSD.md), BRD (jobs/OverdraftFeeSummary/BRD.md)

---

## Primary Validation

### Proofmark Byte-Identical Comparison
**Method:** Proofmark CSV comparison across all 92 effective dates (2024-10-01 through 2024-12-31).

**Config:** `proofmark-configs/OverdraftFeeSummary.yaml` (header_rows: 1, trailer_rows: 0)

**LHS (V1):** `{ETL_ROOT}/Output/curated/overdraft_fee_summary/overdraft_fee_summary/{date}/overdraft_fee_summary.csv`
**RHS (RE):** `{ETL_RE_OUTPUT}/overdraft_fee_summary/overdraft_fee_summary/{date}/overdraft_fee_summary.csv`

**Pass criteria:** 92/92 PASS. Zero tolerance for differences.

**Trailer handling:** No trailer in this job. Proofmark config uses `trailer_rows: 0`.

---

## Coverage Matrix

| Dimension | Coverage | Notes |
|-----------|----------|-------|
| Effective dates | 92/92 | Oct 1 - Dec 31, 2024 |
| Data rows per date | 2 | One per fee_waived value (0 and 1) |
| Columns | 6 | 5 from SQL + etl_effective_date |
| Line endings | LF | Verified via V1 conf and binary inspection |
| Header | Present | Single header row |
| Trailer | None | V1 has no trailerFormat |

---

## Traceability

| Test Aspect | Traces to FSD | Traces to BRD |
|-------------|---------------|---------------|
| Row content match | FSD-OFS-002 | BRD-OFS-003, BRD-OFS-004, BRD-OFS-005, BRD-OFS-006 |
| Column schema match | FSD-OFS-005 | BRD-OFS-011 |
| Header presence | FSD-OFS-004 | BRD-OFS-010 |
| Line ending format | FSD-OFS-004 | BRD-OFS-009 |
| Row count (2 data) | FSD-OFS-002 | BRD-OFS-012 |
| Output path | FSD-OFS-004 | BRD-OFS-013 |
| Ordering | FSD-OFS-002 | BRD-OFS-007 |

---

## Risk Assessment

**Low risk.** OverdraftFeeSummary is the simplest Tier 1 job:
- Single source table with straightforward GROUP BY aggregation
- AP4 remediation (removing 5 unused columns) is DataSourcing-only, cannot affect output
- AP8 remediation (removing dead ROW_NUMBER CTE) is algebraically equivalent -- CTE passed all rows through unfiltered
- No trailer to complicate comparison
- Static row count across all dates (always 2 rows: fee_waived=0 and fee_waived=1)
- ROUND(,2) behavior consistent across all dates
