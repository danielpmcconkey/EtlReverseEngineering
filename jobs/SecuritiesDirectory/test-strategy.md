# SecuritiesDirectory -- Test Strategy

**Job:** SecuritiesDirectory_RE
**Traces to:** FSD (jobs/SecuritiesDirectory/FSD.md), BRD (jobs/SecuritiesDirectory/BRD.md)

---

## Primary Validation

### Proofmark Byte-Identical Comparison
**Method:** Proofmark CSV comparison across all 92 effective dates (2024-10-01 through 2024-12-31).

**Config:** `proofmark-configs/SecuritiesDirectory.yaml` (header_rows: 1, trailer_rows: 0)

**LHS (V1):** `{ETL_ROOT}/Output/curated/securities_directory/securities_directory/{date}/securities_directory.csv`
**RHS (RE):** `{ETL_RE_OUTPUT}/securities_directory/securities_directory/{date}/securities_directory.csv`

**Pass criteria:** 92/92 PASS. Zero tolerance for differences.

---

## Coverage Matrix

| Dimension | Coverage | Notes |
|-----------|----------|-------|
| Effective dates | 92/92 | Oct 1 - Dec 31, 2024 |
| Data rows per date | 50 | All securities present every date |
| Columns | 8 | 7 from SQL + etl_effective_date |
| Line endings | LF | Verified from V1 job conf |
| Header | Present | Single header row |
| Trailer | None | No trailer in V1 output |

---

## Traceability

| Test Aspect | Traces to FSD | Traces to BRD |
|-------------|---------------|---------------|
| Row content match | FSD-SD-003 | BRD-SD-004, BRD-SD-005 |
| Column schema match | FSD-SD-006 | BRD-SD-008 |
| Header presence | FSD-SD-005 | BRD-SD-007 |
| Line ending format | FSD-SD-005 | BRD-SD-006 |
| Row count (50 data) | FSD-SD-003 | BRD-SD-009 |
| No trailer | FSD-SD-005 | BRD-SD-010 |
| Output path | FSD-SD-005 | BRD-SD-011 |

---

## Risk Assessment

**Low risk.** SecuritiesDirectory is a simple pass-through listing:
- Single source used in transformation (second source removed as AP1)
- No aggregation, no joins, no complex business logic
- Static row count across all dates (50 securities)
- AP1 remediation removes unused data sourcing only -- SQL is unchanged
