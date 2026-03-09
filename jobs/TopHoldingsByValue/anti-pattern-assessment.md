# TopHoldingsByValue -- Anti-Pattern Assessment

**Job:** TopHoldingsByValue (V1) -> TopHoldingsByValue_RE (RE)
**Assessed against:** Master Anti-Pattern List (AP1-AP10)

---

## Summary

| AP | Name | Finding | Action |
|----|------|---------|--------|
| AP1 | Dead-End Sourcing | Clean (post-AP4) | None |
| AP2 | Duplicated Logic | Clean | None |
| AP3 | Unnecessary External Module | N/A | None |
| AP4 | Unused Columns | **FOUND** | Remediated |
| AP5 | Asymmetric Null/Default Handling | Clean | None |
| AP6 | Row-by-Row Iteration | N/A | None |
| AP7 | Magic Values | Minor | Not remediated |
| AP8 | Complex/Dead SQL | **FOUND** | Remediated |
| AP9 | Misleading Names | Clean | None |
| AP10 | Over-Sourcing Date Ranges | Clean | None |

---

## Detailed Findings

### AP1 -- Dead-End Sourcing
**Finding:** Clean (after AP4 remediation). Two DataSourcing modules:
- `datalake.holdings`: `security_id` used in GROUP BY/JOIN, `current_value` in SUM, `quantity` retained from V1 sourcing
- `datalake.securities`: `security_id` used in JOIN, `ticker`/`security_name`/`sector` all in output

Post-AP4, all remaining sourced columns serve a purpose in the transformation or output.

### AP2 -- Duplicated Logic
**Finding:** Clean. No other job computes top holdings by value. TopHoldingsByValue is the sole producer of this ranked securities output.

### AP3 -- Unnecessary External Module
**Finding:** N/A. No External module in V1. Job uses SQL Transformation with CTEs, which is appropriate for the multi-step aggregation + ranking + bucketing logic.

### AP4 -- Unused Columns
**Finding:** **FOUND.**

From holdings (V1 sources 6 columns, 3 unused):

| Column | Referenced in SQL? | In output? | Verdict |
|--------|--------------------|------------|---------|
| holding_id | No | No | Unused |
| investment_id | No | No | Unused |
| customer_id | No | No | Unused |

From securities (V1 sources 5 columns, 1 unused):

| Column | Referenced in SQL? | In output? | Verdict |
|--------|--------------------|------------|---------|
| security_type | No | No | Unused |

**Remediation:** Removed 3 columns from holdings DataSourcing (`holding_id`, `investment_id`, `customer_id`) and 1 from securities DataSourcing (`security_type`). Holdings reduced from 6 to 3 columns; securities reduced from 5 to 4 columns.

### AP5 -- Asymmetric Null/Default Handling
**Finding:** Clean. No explicit null handling in the SQL. JOIN will naturally exclude securities without matching holdings and vice versa, which is correct behavior.

### AP6 -- Row-by-Row Iteration
**Finding:** N/A. No External module, no foreach loops. Pure SQL transformation with CTEs.

### AP7 -- Magic Values
**Finding:** Minor. The rank boundaries (5, 10, 20) in the CASE statement are hardcoded business thresholds. However, these are part of the V1 business logic and cannot be remediated without changing output behavior. Documented but not actionable for RE.

### AP8 -- Complex/Dead SQL
**Finding:** **FOUND (one issue, fully remediated).**

V1 SQL contains a CTE named `unused_cte`:
```sql
unused_cte AS (
  SELECT security_id, total_held_value
  FROM security_totals
  WHERE total_held_value > 0
)
```

This CTE is defined but never referenced by any subsequent CTE or the final SELECT. The `ranked` CTE references `security_totals` directly, not `unused_cte`. The final SELECT references `ranked` only. `unused_cte` is pure dead code -- it computes a filtered subset that nobody consumes.

**Remediation:** Removed `unused_cte` CTE entirely. The remaining CTEs (`security_totals`, `ranked`) and the final SELECT are identical to V1.

Note: Unlike some AP8 findings, this is unambiguously dead code. The CTE alias is never referenced anywhere after its definition. No analysis of output impact is needed -- removing unreferenced code cannot change results.

### AP9 -- Misleading Names
**Finding:** Clean. Job name "TopHoldingsByValue" accurately describes the output: top securities ranked by total held value.

### AP10 -- Over-Sourcing Date Ranges
**Finding:** Clean. Both DataSourcing modules are scoped by the framework's effective date injection.
