# BranchDirectory — Test Strategy

**Job:** BranchDirectory_RE
**Traces to:** FSD (jobs/BranchDirectory/FSD.md), BRD (jobs/BranchDirectory/BRD.md)

---

## Primary Validation

### Proofmark Byte-Identical Comparison
**Method:** Proofmark CSV comparison across all 92 effective dates (2024-10-01 through 2024-12-31).

**Config:** `proofmark-configs/BranchDirectory.yaml` (header_rows: 1, trailer_rows: 0)

**LHS (V1):** `{ETL_ROOT}/Output/curated/branch_directory/branch_directory/{date}/branch_directory.csv`
**RHS (RE):** `{ETL_RE_OUTPUT}/branch_directory/branch_directory/{date}/branch_directory.csv`

**Pass criteria:** 92/92 PASS. Zero tolerance for differences.

---

## Coverage Matrix

| Dimension | Coverage | Notes |
|-----------|----------|-------|
| Effective dates | 92/92 | Oct 1 - Dec 31, 2024 |
| Data rows per date | 40 | All branches present every date |
| Columns | 9 | 7 source + ifw_effective_date + etl_effective_date |
| Line endings | CRLF | Verified via binary inspection |
| Header | Present | Single header row |
| Trailer | None | No trailer in V1 output |

---

## Traceability

| Test Aspect | Traces to FSD | Traces to BRD |
|-------------|---------------|---------------|
| Row content match | FSD-BD-002 | BRD-BD-003, BRD-BD-004 |
| Column schema match | FSD-BD-005 | BRD-BD-007 |
| Header presence | FSD-BD-004 | BRD-BD-006 |
| Line ending format | FSD-BD-004 | BRD-BD-005 |
| Row count (40 data) | FSD-BD-002 | BRD-BD-008 |
| No trailer | FSD-BD-004 | BRD-BD-009 |
| Output path | FSD-BD-004 | BRD-BD-010 |

---

## Risk Assessment

**Low risk.** BranchDirectory is the simplest Tier 1 job:
- Single source table, no joins
- No aggregation, no complex business logic
- Static row count across all dates (40 branches)
- AP8 remediation removes dead code only, no functional change
