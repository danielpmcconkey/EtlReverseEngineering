# TopBranches -- Test Strategy

**Job:** TopBranches_RE
**Traces to:** FSD (jobs/TopBranches/FSD.md), BRD (jobs/TopBranches/BRD.md)

---

## Primary Validation

### Proofmark Byte-Identical Comparison
**Method:** Proofmark CSV comparison across all 92 effective dates (2024-10-01 through 2024-12-31).

**Config:** `proofmark-configs/TopBranches.yaml` (header_rows: 1, trailer_rows: 1)

**LHS (V1):** `{ETL_ROOT}/Output/curated/top_branches/top_branches/{date}/top_branches.csv`
**RHS (RE):** `{ETL_RE_OUTPUT}/top_branches/top_branches/{date}/top_branches.csv`

**Pass criteria:** 92/92 PASS. Zero tolerance for differences.

**Trailer handling:** Proofmark config uses `trailer_rows: 1` to EXCLUDE the trailer from comparison. The trailer format `CONTROL|{date}|{row_count}|{timestamp}` includes a runtime timestamp that will differ between V1 and RE runs. Proofmark skips the last row entirely, comparing only header and 40 data rows.

---

## Coverage Matrix

| Dimension | Coverage | Notes |
|-----------|----------|-------|
| Effective dates | 92/92 | Oct 1 - Dec 31, 2024 |
| Data rows per date | 40 | All branches ranked |
| Columns | 6 | 5 from SQL + etl_effective_date |
| Line endings | LF | Verified via V1 conf |
| Header | Present | Single header row |
| Trailer | Present but EXCLUDED | CONTROL\|{date}\|40\|{timestamp} -- non-deterministic |

---

## Traceability

| Test Aspect | Traces to FSD | Traces to BRD |
|-------------|---------------|---------------|
| Row content match | FSD-TB-003 | BRD-TB-006, BRD-TB-007 |
| Column schema match | FSD-TB-006 | BRD-TB-012 |
| Header presence | FSD-TB-005 | BRD-TB-011 |
| Line ending format | FSD-TB-005 | BRD-TB-010 |
| Row count (40 data) | FSD-TB-003 | BRD-TB-013 |
| Trailer presence | FSD-TB-005 | BRD-TB-014 |
| Output path | FSD-TB-005 | BRD-TB-015 |
| Ranking correctness | FSD-TB-003 | BRD-TB-007, BRD-TB-008 |

---

## Risk Assessment

**Low risk.** TopBranches has straightforward SQL with minor anti-patterns:
- AP4 removes `visit_id` from DataSourcing -- cannot affect SQL output (only `branch_id` used)
- AP10/AP8 dead WHERE clause removal is safe -- DataSourcing already filters to single effective date
- Non-deterministic trailer handled by Proofmark `trailer_rows: 1` exclusion
- 40 data rows per date (all branches) provides good coverage of RANK window function
- No dependency on other RE'd jobs -- reads directly from datalake tables
