# TransactionSizeBuckets -- Anti-Pattern Assessment

**Job:** TransactionSizeBuckets (V1) -> TransactionSizeBuckets_RE (RE)
**Assessed against:** Master Anti-Pattern List (AP1-AP10)

---

## Summary

| AP | Name | Finding | Action |
|----|------|---------|--------|
| AP1 | Dead-End Sourcing | **FOUND** | Remediated |
| AP2 | Duplicated Logic | Clean | None |
| AP3 | Unnecessary External Module | N/A | None |
| AP4 | Unused Columns | **FOUND** | Remediated |
| AP5 | Asymmetric Null/Default Handling | N/A | None |
| AP6 | Row-by-Row Iteration | N/A | None |
| AP7 | Magic Values | Clean | None |
| AP8 | Complex/Dead SQL | **FOUND** | Remediated |
| AP9 | Misleading Names | Clean | None |
| AP10 | Over-Sourcing Date Ranges | Clean | None |

---

## Detailed Findings

### AP1 -- Dead-End Sourcing
**Finding:** **FOUND.**

V1 sources `datalake.accounts` with 3 columns (`account_id`, `customer_id`, `account_type`) but the transformation SQL references ONLY `transactions t`. No column, alias, or table reference to `accounts` appears anywhere in the SQL.

**Remediation:** Removed the entire `accounts` DataSourcing module from the RE job conf. The SQL remains unchanged since it never referenced accounts.

**Evidence:** V1 SQL contains no reference to `accounts`, `a.`, or any accounts column name.

### AP2 -- Duplicated Logic
**Finding:** Clean. No other job produces this transaction size bucketing output.

### AP3 -- Unnecessary External Module
**Finding:** N/A. No External module in V1. Pure SQL transformation.

### AP4 -- Unused Columns
**Finding:** **FOUND.**

From `transactions`: `transaction_id`, `account_id`, and `txn_type` are sourced but only `amount` is used in the final output aggregation.

- `transaction_id`: Appears in V1's `txn_detail` and `bucketed` CTEs but is never used in GROUP BY, WHERE, or final SELECT.
- `account_id`: Used only in the dead ROW_NUMBER's PARTITION BY clause (which itself is AP8). Not in final output.
- `txn_type`: Appears in V1's `txn_detail` CTE SELECT but is never referenced downstream.

**Remediation:** Reduced DataSourcing columns from 4 (`transaction_id`, `account_id`, `txn_type`, `amount`) to 1 (`amount`). This is the most aggressive AP4 remediation possible for this job.

### AP5 -- Asymmetric Null/Default Handling
**Finding:** N/A. No null/default handling logic. CASE statement uses clear boundary conditions.

### AP6 -- Row-by-Row Iteration
**Finding:** N/A. No External module. Pure SQL transformation.

### AP7 -- Magic Values
**Finding:** Clean. The bucket boundaries (0, 25, 100, 500, 1000) are clear domain thresholds for transaction size classification. Not magic numbers.

### AP8 -- Complex/Dead SQL
**Finding:** **FOUND.**

V1 SQL includes a `txn_detail` CTE with `ROW_NUMBER() OVER (PARTITION BY t.account_id ORDER BY t.amount DESC) AS rn`. The `rn` column is never referenced in any subsequent CTE, WHERE clause, or SELECT statement.

**Remediation:** Removed the entire `txn_detail` CTE. The `bucketed` CTE now selects directly from `transactions` instead of from `txn_detail`. This eliminates dead window function computation.

**Evidence:** Searched all V1 SQL references to `rn`: only defined in `txn_detail`, never used in `bucketed`, `summary`, or final SELECT.

### AP9 -- Misleading Names
**Finding:** Clean. "TransactionSizeBuckets" accurately describes the output: transactions classified into size buckets.

### AP10 -- Over-Sourcing Date Ranges
**Finding:** Clean. DataSourcing is scoped by the framework's effective date injection.
