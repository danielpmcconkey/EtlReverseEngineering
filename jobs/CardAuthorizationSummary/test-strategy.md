# CardAuthorizationSummary -- Test Strategy

**Job:** CardAuthorizationSummary_RE
**Traces to:** FSD (jobs/CardAuthorizationSummary/FSD.md), BRD (jobs/CardAuthorizationSummary/BRD.md)

---

## Primary Validation

### Proofmark Byte-Identical Comparison
**Method:** Proofmark CSV comparison across all 92 effective dates (2024-10-01 through 2024-12-31).

**Config:** `proofmark-configs/CardAuthorizationSummary.yaml` (header_rows: 1, trailer_rows: 1)

**LHS (V1):** `{ETL_ROOT}/Output/curated/card_authorization_summary/card_authorization_summary/{date}/card_authorization_summary.csv`
**RHS (RE):** `{ETL_RE_OUTPUT}/card_authorization_summary/card_authorization_summary/{date}/card_authorization_summary.csv`

**Pass criteria:** 92/92 PASS. Zero tolerance for differences.

**Trailer handling:** Proofmark config uses `trailer_rows: 1` to handle the `TRAILER|{row_count}|{date}` line. The trailer is deterministic (row count + effective date, no runtime timestamps), so Proofmark compares it as data. The `trailer_rows` setting tells Proofmark how many trailing rows to treat as trailer for structural parsing.

---

## Coverage Matrix

| Dimension | Coverage | Notes |
|-----------|----------|-------|
| Effective dates | 92/92 | Oct 1 - Dec 31, 2024 |
| Data rows per date | 2 | One per card type (Credit, Debit) |
| Columns | 7 | 6 from SQL + etl_effective_date |
| Line endings | LF | Verified via V1 conf |
| Header | Present | Single header row |
| Trailer | Present | TRAILER\|2\|{date} |

---

## Traceability

| Test Aspect | Traces to FSD | Traces to BRD |
|-------------|---------------|---------------|
| Row content match | FSD-CAUTH-003 | BRD-CAUTH-005, BRD-CAUTH-006 |
| Column schema match | FSD-CAUTH-006 | BRD-CAUTH-010 |
| Header presence | FSD-CAUTH-005 | BRD-CAUTH-009 |
| Line ending format | FSD-CAUTH-005 | BRD-CAUTH-008 |
| Row count (2 data) | FSD-CAUTH-003 | BRD-CAUTH-011 |
| Trailer format | FSD-CAUTH-005 | BRD-CAUTH-012 |
| Output path | FSD-CAUTH-005 | BRD-CAUTH-013 |
| Integer division (AP7) | FSD-CAUTH-003 | BRD-CAUTH-006 |

---

## Risk Assessment

**Low risk.** CardAuthorizationSummary has moderate anti-pattern density but all remediations are safe:
- AP4 removes unused columns from DataSourcing -- cannot affect SQL output
- AP8 ROW_NUMBER and dead CTE removal are pure dead code elimination
- AP7 integer division is preserved exactly -- the only risk area, but no change means no risk
- Deterministic trailer means full comparison including trailer line
- Static row count across all dates (always 2 rows: Credit and Debit)
