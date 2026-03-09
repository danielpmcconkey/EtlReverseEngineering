# CustomerAccountSummary -- Test Strategy

**Job:** CustomerAccountSummary_RE
**Traces to:** FSD (jobs/CustomerAccountSummary/FSD.md), BRD (jobs/CustomerAccountSummary/BRD.md)

---

## Primary Validation

### Proofmark Byte-Identical Comparison
**Method:** Proofmark CSV comparison across all 92 effective dates (2024-10-01 through 2024-12-31).

**Config:** `proofmark-configs/CustomerAccountSummary.yaml` (header_rows: 1, trailer_rows: 0)

**LHS (V1):** `{ETL_ROOT}/Output/curated/customer_account_summary/customer_account_summary/{date}/customer_account_summary.csv`
**RHS (RE):** `{ETL_RE_OUTPUT}/customer_account_summary/customer_account_summary/{date}/customer_account_summary.csv`

**Pass criteria:** 92/92 PASS. Zero tolerance for differences.

---

## Coverage Matrix

| Dimension | Coverage | Notes |
|-----------|----------|-------|
| Effective dates | 92/92 | Oct 1 - Dec 31, 2024 |
| Data rows per date | 2230 | All customers present every date |
| Columns | 6 | 5 from SQL + etl_effective_date |
| Line endings | LF | Verified from V1 job conf |
| Header | Present | Single header row |
| Trailer | None | No trailer in V1 output |

---

## Traceability

| Test Aspect | Traces to FSD | Traces to BRD |
|-------------|---------------|---------------|
| Row content match | FSD-CAS-003 | BRD-CAS-004, BRD-CAS-005 |
| Column schema match | FSD-CAS-006 | BRD-CAS-009 |
| Header presence | FSD-CAS-005 | BRD-CAS-008 |
| Line ending format | FSD-CAS-005 | BRD-CAS-007 |
| Row count (2230 data) | FSD-CAS-003 | BRD-CAS-010 |
| No trailer | FSD-CAS-005 | BRD-CAS-011 |
| Output path | FSD-CAS-005 | BRD-CAS-012 |

---

## Risk Assessment

**Low risk.** CustomerAccountSummary has no anti-patterns requiring remediation:
- LEFT JOIN is correct and meaningful (customers to accounts)
- All sourced columns are used
- No dead SQL constructs
- SQL is identical to V1 -- only `outputDirectory` changes
