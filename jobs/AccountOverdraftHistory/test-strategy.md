# AccountOverdraftHistory — Test Strategy

**Job:** AccountOverdraftHistory_RE
**Traces to:** FSD (jobs/AccountOverdraftHistory/FSD.md), BRD (jobs/AccountOverdraftHistory/BRD.md)

---

## Primary Validation

### Proofmark Byte-Identical Comparison
**Method:** Proofmark Parquet comparison across all 92 effective dates (2024-10-01 through 2024-12-31).

**Config:** `proofmark-configs/AccountOverdraftHistory.yaml` (reader: parquet)

**LHS (V1):** `{ETL_ROOT}/Output/curated/account_overdraft_history/account_overdraft_history/{date}/account_overdraft_history`
**RHS (RE):** `{ETL_RE_OUTPUT}/account_overdraft_history/account_overdraft_history/{date}/account_overdraft_history`

**Pass criteria:** 92/92 PASS. Zero tolerance for differences.

---

## Coverage Matrix

| Dimension | Coverage | Notes |
|-----------|----------|-------|
| Effective dates | 92/92 | Oct 1 - Dec 31, 2024 |
| Data rows per date | 2-3 | Variable (depends on overdraft events for that date) |
| Columns | 9 | 8 from SQL SELECT + etl_effective_date |
| Format | Parquet | 50 parts per date |
| Header | N/A | Parquet has schema metadata, not CSV headers |
| Trailer | N/A | No trailer in Parquet format |

---

## Traceability

| Test Aspect | Traces to FSD | Traces to BRD |
|-------------|---------------|---------------|
| Row content match | FSD-AOH-003 | BRD-AOH-004, BRD-AOH-005 |
| Column schema match | FSD-AOH-006 | BRD-AOH-008 |
| Partition count | FSD-AOH-005 | BRD-AOH-007 |
| Row count per date | FSD-AOH-003 | BRD-AOH-009 |
| Output path | FSD-AOH-005 | BRD-AOH-010 |

---

## Risk Assessment

**Low risk.** AccountOverdraftHistory is the cleanest multi-source job in Tier 2:
- Meaningful JOIN (enriches overdraft events with account_type)
- No dead code, no dead sources
- AP4 remediation only (unused DataSourcing columns removed)
- Variable but small row count (2-3 per date)
