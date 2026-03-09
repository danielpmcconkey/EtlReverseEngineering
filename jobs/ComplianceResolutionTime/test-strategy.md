# ComplianceResolutionTime -- Test Strategy

**Job:** ComplianceResolutionTime_RE
**Traces to:** FSD (jobs/ComplianceResolutionTime/FSD.md), BRD (jobs/ComplianceResolutionTime/BRD.md)

---

## Primary Validation

### Proofmark Byte-Identical Comparison
**Method:** Proofmark CSV comparison across all 92 effective dates (2024-10-01 through 2024-12-31).

**Config:** `proofmark-configs/ComplianceResolutionTime.yaml` (header_rows: 1, trailer_rows: 1)

**LHS (V1):** `{ETL_ROOT}/Output/curated/compliance_resolution_time/compliance_resolution_time/{date}/compliance_resolution_time.csv`
**RHS (RE):** `{ETL_RE_OUTPUT}/compliance_resolution_time/compliance_resolution_time/{date}/compliance_resolution_time.csv`

**Pass criteria:** 92/92 PASS. Zero tolerance for differences.

**Trailer handling:** Proofmark config uses `trailer_rows: 1` to handle the `TRAILER|{row_count}|{date}` line. The trailer is deterministic (row count + date, no timestamps), so Proofmark compares it as data, not skipping it. The `trailer_rows` setting tells Proofmark how many trailing rows to treat as trailer for structural parsing, not to exclude from comparison.

---

## Coverage Matrix

| Dimension | Coverage | Notes |
|-----------|----------|-------|
| Effective dates | 92/92 | Oct 1 - Dec 31, 2024 |
| Data rows per date | 5 | One per event type |
| Columns | 6 | 5 from SQL + etl_effective_date |
| Line endings | LF | Verified via V1 conf |
| Header | Present | Single header row |
| Trailer | Present | TRAILER\|5\|{date} |

---

## Traceability

| Test Aspect | Traces to FSD | Traces to BRD |
|-------------|---------------|---------------|
| Row content match | FSD-CRT-002 | BRD-CRT-003, BRD-CRT-005 |
| Column schema match | FSD-CRT-005 | BRD-CRT-010 |
| Header presence | FSD-CRT-004 | BRD-CRT-009 |
| Line ending format | FSD-CRT-004 | BRD-CRT-008 |
| Row count (5 data) | FSD-CRT-002 | BRD-CRT-011 |
| Trailer format | FSD-CRT-004 | BRD-CRT-012 |
| Output path | FSD-CRT-004 | BRD-CRT-013 |
| Integer division | FSD-CRT-002 | BRD-CRT-006 |

---

## Risk Assessment

**Low risk.** ComplianceResolutionTime has slightly more complexity than BranchDirectory:
- Single source table, but with CTE filtering and aggregation
- AP4 remediation (removing unused column) is DataSourcing-only, cannot affect output
- AP8 remediation (removing cartesian join and dead ROW_NUMBER) is algebraically equivalent
- AP5 integer division is preserved exactly -- the main risk area, but no change means no risk
- Static row count across all dates (5 event types, same counts)
