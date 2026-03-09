# CardStatusSnapshot -- Test Strategy

**Job:** CardStatusSnapshot_RE
**Traces to:** FSD (jobs/CardStatusSnapshot/FSD.md), BRD (jobs/CardStatusSnapshot/BRD.md)

---

## Primary Validation

### Proofmark Byte-Identical Comparison
**Method:** Proofmark Parquet comparison across all 92 effective dates (2024-10-01 through 2024-12-31).

**Config:** `proofmark-configs/CardStatusSnapshot.yaml` (reader: parquet -- no csv section needed)

**LHS (V1):** `{ETL_ROOT}/Output/curated/card_status_snapshot/card_status_snapshot/{date}/card_status_snapshot`
**RHS (RE):** `{ETL_RE_OUTPUT}/card_status_snapshot/card_status_snapshot/{date}/card_status_snapshot`

**Pass criteria:** 92/92 PASS. Zero tolerance for differences.

**Parquet note:** Paths are DIRECTORY paths (no file extension). Proofmark reads all `part-*.parquet` files in each directory, concatenates them, and compares the resulting DataFrames.

---

## Coverage Matrix

| Dimension | Coverage | Notes |
|-----------|----------|-------|
| Effective dates | 92/92 | Oct 1 - Dec 31, 2024 |
| Data rows per date | 3 | One per card_status value |
| Columns | 4 | 3 from SQL + etl_effective_date |
| Part files | 50 | Massively over-partitioned for 3 rows |
| Format | Parquet | First Parquet job validated |

---

## Traceability

| Test Aspect | Traces to FSD | Traces to BRD |
|-------------|---------------|---------------|
| Row content match | FSD-CSS-002 | BRD-CSS-003, BRD-CSS-004 |
| Column schema match | FSD-CSS-005 | BRD-CSS-008 |
| Part file count | FSD-CSS-004 | BRD-CSS-012 |
| Row count (3 data) | FSD-CSS-002 | BRD-CSS-009 |
| Output path | FSD-CSS-004 | BRD-CSS-010 |

---

## Risk Assessment

**Low risk.** CardStatusSnapshot is a simple aggregation job:
- Single source table with straightforward GROUP BY
- AP4 remediation (removing 5 unused columns) is DataSourcing-only, cannot affect output
- No AP8 issues -- SQL is clean, no dead CTEs or unused window functions
- SQL is identical between V1 and RE
- Parquet comparison is the novel element -- this is the first Parquet Proofmark test in the project
- 3 rows across 50 parts is absurd but must match V1 exactly
