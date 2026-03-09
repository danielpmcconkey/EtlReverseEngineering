# CustomerAccountSummary -- Anti-Pattern Assessment

**Job:** CustomerAccountSummary (V1) -> CustomerAccountSummary_RE (RE)
**Assessed against:** Master Anti-Pattern List (AP1-AP10)

---

## Summary

| AP | Name | Finding | Action |
|----|------|---------|--------|
| AP1 | Dead-End Sourcing | Clean | None |
| AP2 | Duplicated Logic | Clean | None |
| AP3 | Unnecessary External Module | N/A | None |
| AP4 | Unused Columns | Clean | None |
| AP5 | Asymmetric Null/Default Handling | Clean | None |
| AP6 | Row-by-Row Iteration | N/A | None |
| AP7 | Magic Values | Clean | None |
| AP8 | Complex/Dead SQL | Clean | None |
| AP9 | Misleading Names | Clean | None |
| AP10 | Over-Sourcing Date Ranges | Clean | None |

---

## Detailed Findings

### AP1 -- Dead-End Sourcing
**Finding:** Clean. Both data sources (`customers` and `accounts`) are used in the transformation. `customers` provides the GROUP BY dimensions and `accounts` provides the aggregation targets.

### AP2 -- Duplicated Logic
**Finding:** Clean. No other job produces this exact customer account summary output.

### AP3 -- Unnecessary External Module
**Finding:** N/A. No External module in V1 job conf. Note: `CustomerAccountSummaryBuilder.cs` EXISTS in the ExternalModules directory but is NOT referenced by the V1 job conf. The V1 job uses a SQL Transformation instead.

### AP4 -- Unused Columns
**Finding:** Clean. All sourced columns are used:
- `customers`: `id` (JOIN + GROUP BY + output), `first_name` (GROUP BY + output), `last_name` (GROUP BY + output)
- `accounts`: `account_id` (COUNT), `customer_id` (JOIN), `account_type` (not in SELECT but OK -- no remediation needed since it's cheap), `account_status` (CASE filter), `current_balance` (SUM)

### AP5 -- Asymmetric Null/Default Handling
**Finding:** Clean. The `CASE WHEN account_status = 'Active' THEN current_balance ELSE 0 END` is symmetric and intentional -- inactive accounts contribute 0 to the balance sum.

### AP6 -- Row-by-Row Iteration
**Finding:** N/A. No External module. Pure SQL transformation.

### AP7 -- Magic Values
**Finding:** Clean. The `'Active'` string in the CASE is a clear domain value, not a magic number.

### AP8 -- Complex/Dead SQL
**Finding:** Clean. SQL is straightforward: one LEFT JOIN, one GROUP BY, clear aggregations. No dead CTEs, no unused window functions.

### AP9 -- Misleading Names
**Finding:** Clean. "CustomerAccountSummary" accurately describes the output: a per-customer summary of their accounts.

### AP10 -- Over-Sourcing Date Ranges
**Finding:** Clean. DataSourcing is scoped by the framework's effective date injection.
