# TopHoldingsByValue -- Test Strategy

**Job:** TopHoldingsByValue_RE
**Traces to:** FSD (jobs/TopHoldingsByValue/FSD.md), BRD (jobs/TopHoldingsByValue/BRD.md)

---

## Primary Validation

### Proofmark Byte-Identical Comparison
**Method:** Proofmark Parquet comparison across all 92 effective dates (2024-10-01 through 2024-12-31).

**Config:** `proofmark-configs/TopHoldingsByValue.yaml` (reader: parquet -- no csv section needed)

**LHS (V1):** `{ETL_ROOT}/Output/curated/top_holdings_by_value/top_holdings_by_value/{date}/top_holdings_by_value`
**RHS (RE):** `{ETL_RE_OUTPUT}/top_holdings_by_value/top_holdings_by_value/{date}/top_holdings_by_value`

**Pass criteria:** 92/92 PASS. Zero tolerance for differences.

**Parquet note:** Paths are DIRECTORY paths (no file extension). Proofmark reads all `part-*.parquet` files in each directory, concatenates them, and compares the resulting DataFrames.

---

## Coverage Matrix

| Dimension | Coverage | Notes |
|-----------|----------|-------|
| Effective dates | 92/92 | Oct 1 - Dec 31, 2024 |
| Data rows per date | 20 | Top 20 securities by held value |
| Columns | 9 | 8 from SQL + etl_effective_date |
| Part files | 50 | 20 rows across 50 parts |
| Format | Parquet | Second Parquet job validated |
| Sources | 2 | holdings + securities (multi-source) |

---

## Traceability

| Test Aspect | Traces to FSD | Traces to BRD |
|-------------|---------------|---------------|
| Row content match | FSD-THV-003 | BRD-THV-004 through BRD-THV-008 |
| Column schema match | FSD-THV-006 | BRD-THV-011 |
| Part file count | FSD-THV-005 | BRD-THV-015 |
| Row count (20 data) | FSD-THV-003 | BRD-THV-012 |
| Output path | FSD-THV-005 | BRD-THV-013 |
| Rank bucketing | FSD-THV-003 | BRD-THV-007 |
| Join correctness | FSD-THV-003 | BRD-THV-005 |

---

## Risk Assessment

**Medium risk.** TopHoldingsByValue has several complexity factors:
- Multi-source JOIN (holdings + securities) -- first multi-source Parquet job
- ROW_NUMBER ranking + CASE bucketing -- both must be preserved
- The `rank` output column is a string ('Top 5', etc.), not an integer -- easy to get wrong
- AP8 remediation removes `unused_cte` -- need to verify it was truly dead code
- AP4 removes columns from both sources -- need to verify none were indirectly used
- 20 rows across 50 parts is still over-partitioned but less extreme than CardStatusSnapshot
