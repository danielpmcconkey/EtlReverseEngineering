# DailyWireVolume -- Anti-Pattern Assessment

**Job:** DailyWireVolume (V1) -> DailyWireVolume_RE (RE)
**Assessed against:** Master Anti-Pattern List (AP1-AP10)

---

## Summary

| AP | Name | Finding | Action |
|----|------|---------|--------|
| AP1 | Dead-End Sourcing | Clean | None |
| AP2 | Duplicated Logic | Clean | None |
| AP3 | Unnecessary External Module | N/A | None |
| AP4 | Unused Columns | Clean | None |
| AP5 | Asymmetric Null/Default Handling | N/A | None |
| AP6 | Row-by-Row Iteration | N/A | None |
| AP7 | Magic Values | **NOTED** | Retained |
| AP8 | Complex/Dead SQL | Clean | None |
| AP9 | Misleading Names | Clean | None |
| AP10 | Over-Sourcing Date Ranges | **NOTED** | Retained |

---

## Detailed Findings

### AP1 -- Dead-End Sourcing
**Finding:** Clean. Single DataSourcing module (`datalake.wire_transfers`), all sourced data is used in transformation (amount for SUM, ifw_effective_date for GROUP BY).

### AP2 -- Duplicated Logic
**Finding:** Clean. No other job produces daily wire volume aggregation.

### AP3 -- Unnecessary External Module
**Finding:** N/A. No External module. Pure SQL transformation.

### AP4 -- Unused Columns
**Finding:** Clean. Of the 6 sourced columns, `amount` and `ifw_effective_date` are used directly in SQL. The remaining 4 (`wire_id`, `customer_id`, `direction`, `status`) are consumed by `COUNT(*)` which counts all rows. Since COUNT(*) doesn't reference specific columns, these columns are technically unused but removing them from DataSourcing wouldn't change the output. However, removing them is cosmetic, not functional, and the SQL uses `COUNT(*)` not `COUNT(column)`, so all rows are counted regardless of column presence. Not remediating.

### AP5 -- Asymmetric Null/Default Handling
**Finding:** N/A. No null handling logic. ROUND and SUM handle nulls via standard SQL semantics.

### AP6 -- Row-by-Row Iteration
**Finding:** N/A. No External module, no loops.

### AP7 -- Magic Values
**Finding:** Noted. SQL contains hardcoded date boundaries `'2024-10-01'` and `'2024-12-31'`. These match the DataSourcing min/maxEffectiveDate and are the defined execution range, not arbitrary magic values. Retained as-is since they are load-bearing for output equivalence.

### AP8 -- Complex/Dead SQL
**Finding:** Clean. No CTEs, no window functions. Single straightforward GROUP BY query.

### AP9 -- Misleading Names
**Finding:** Clean. "DailyWireVolume" accurately describes the output: daily aggregated wire transfer volume.

### AP10 -- Over-Sourcing Date Ranges
**Finding:** Noted. The SQL `WHERE ifw_effective_date >= '2024-10-01' AND ifw_effective_date <= '2024-12-31'` is technically redundant with DataSourcing's `minEffectiveDate`/`maxEffectiveDate` which already scope the loaded data. However, this redundancy is harmless and removing the WHERE clause would produce identical output. Retained for safety.
