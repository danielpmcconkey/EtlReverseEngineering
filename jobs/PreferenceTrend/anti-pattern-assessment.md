# PreferenceTrend -- Anti-Pattern Assessment

**Job:** PreferenceTrend (V1) -> PreferenceTrend_RE (RE)
**Assessed against:** Master Anti-Pattern List (AP1-AP10)

---

## Summary

| AP | Name | Finding | Action |
|----|------|---------|--------|
| AP1 | Dead-End Sourcing | Clean | None |
| AP2 | Duplicated Logic | Clean | None |
| AP3 | Unnecessary External Module | N/A | None |
| AP4 | Unused Columns | **NOTED** | Not remediated |
| AP5 | Asymmetric Null/Default Handling | N/A | None |
| AP6 | Row-by-Row Iteration | N/A | None |
| AP7 | Magic Values | Clean | None |
| AP8 | Complex/Dead SQL | Clean | None |
| AP9 | Misleading Names | Clean | None |
| AP10 | Over-Sourcing Date Ranges | Clean | None |

---

## Detailed Findings

### AP1 -- Dead-End Sourcing
**Finding:** Clean. Single DataSourcing module, all data is consumed in the GROUP BY aggregation.

### AP2 -- Duplicated Logic
**Finding:** Clean. No other job produces preference trend aggregation.

### AP3 -- Unnecessary External Module
**Finding:** N/A. No External module.

### AP4 -- Unused Columns
**Finding:** Noted. `preference_id` and `customer_id` are sourced but not referenced in the SQL SELECT or GROUP BY. However, they contribute to `COUNT(*)` implicitly through the aggregation rows. Since the SQL uses `SUM(CASE ...)` not `COUNT(*)`, and GROUP BY only uses `preference_type` and `ifw_effective_date`, these columns are truly unused. Not remediating because removing them from DataSourcing doesn't change the output (the columns aren't in SELECT) and would require verifying framework behavior with reduced column sets.

### AP5 -- Asymmetric Null/Default Handling
**Finding:** N/A. CASE expressions handle opted_in values consistently (1 = opted in, 0 = opted out).

### AP6 -- Row-by-Row Iteration
**Finding:** N/A. No External module.

### AP7 -- Magic Values
**Finding:** Clean. No hardcoded constants beyond standard CASE values (0, 1).

### AP8 -- Complex/Dead SQL
**Finding:** Clean. Simple GROUP BY with CASE aggregation. No CTEs, no window functions.

### AP9 -- Misleading Names
**Finding:** Clean. "PreferenceTrend" accurately describes preference opt-in/opt-out trends.

### AP10 -- Over-Sourcing Date Ranges
**Finding:** Clean. No min/maxEffectiveDate overrides. Standard single-date scoping.
