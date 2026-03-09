# TransactionSizeBuckets -- Test Strategy

**Job:** TransactionSizeBuckets_RE
**Traces to:** FSD (jobs/TransactionSizeBuckets/FSD.md), BRD (jobs/TransactionSizeBuckets/BRD.md)

---

## Primary Validation

### Proofmark Byte-Identical Comparison
**Method:** Proofmark CSV comparison across all 92 effective dates (2024-10-01 through 2024-12-31).

**Config:** `proofmark-configs/TransactionSizeBuckets.yaml` (header_rows: 1, trailer_rows: 0)

**LHS (V1):** `{ETL_ROOT}/Output/curated/transaction_size_buckets/transaction_size_buckets/{date}/transaction_size_buckets.csv`
**RHS (RE):** `{ETL_RE_OUTPUT}/transaction_size_buckets/transaction_size_buckets/{date}/transaction_size_buckets.csv`

**Pass criteria:** 92/92 PASS. Zero tolerance for differences.

---

## Coverage Matrix

| Dimension | Coverage | Notes |
|-----------|----------|-------|
| Effective dates | 92/92 | Oct 1 - Dec 31, 2024 |
| Data rows per date | 5 | One per amount bucket |
| Columns | 6 | 5 from SQL + etl_effective_date |
| Line endings | LF | Verified from V1 job conf |
| Header | Present | Single header row |
| Trailer | None | No trailer in V1 output |

---

## Traceability

| Test Aspect | Traces to FSD | Traces to BRD |
|-------------|---------------|---------------|
| Row content match | FSD-TSB-003 | BRD-TSB-004, BRD-TSB-005 |
| Column schema match | FSD-TSB-006 | BRD-TSB-011 |
| Header presence | FSD-TSB-005 | BRD-TSB-010 |
| Line ending format | FSD-TSB-005 | BRD-TSB-009 |
| Row count (5 data) | FSD-TSB-003 | BRD-TSB-012 |
| No trailer | FSD-TSB-005 | BRD-TSB-013 |
| Output path | FSD-TSB-005 | BRD-TSB-014 |

---

## Risk Assessment

**Low risk.** TransactionSizeBuckets has multiple anti-pattern remediations but all are safe:
- AP1: Accounts source never referenced -- removal is trivial
- AP8: ROW_NUMBER never filtered on -- removal is dead code cleanup
- AP4: Unused columns removed from DataSourcing -- no impact on SQL output
- All remediations are structural (DataSourcing/CTE cleanup), not functional (output-affecting)
