# AccountOverdraftHistory — Anti-Pattern Assessment

**Job:** AccountOverdraftHistory (V1) -> AccountOverdraftHistory_RE (RE)
**Assessed against:** Master Anti-Pattern List (AP1-AP10)

---

## Summary

| AP | Name | Finding | Action |
|----|------|---------|--------|
| AP1 | Dead-End Sourcing | Clean | None |
| AP2 | Duplicated Logic | Clean | None |
| AP3 | Unnecessary External Module | N/A | None |
| AP4 | Unused Columns | **FOUND** | Remediated |
| AP5 | Asymmetric Null/Default Handling | N/A | None |
| AP6 | Row-by-Row Iteration | N/A | None |
| AP7 | Magic Values | Clean | None |
| AP8 | Complex/Dead SQL | Clean | None |
| AP9 | Misleading Names | Clean | None |
| AP10 | Over-Sourcing Date Ranges | Clean | None |

---

## Detailed Findings

### AP1 — Dead-End Sourcing
**Finding:** Clean. Both data sources (`overdraft_events` and `accounts`) are actively used. `overdraft_events` provides the core data; `accounts` provides `account_type` enrichment via JOIN. Neither source is dead-end.

### AP2 — Duplicated Logic
**Finding:** Clean. No other job produces this output. AccountOverdraftHistory is the sole producer of the overdraft history with account type enrichment.

### AP3 — Unnecessary External Module
**Finding:** N/A. No External module in V1. Job uses SQL Transformation only.

### AP4 — Unused Columns
**Finding:** **FOUND.**

From `overdraft_events`: `event_timestamp` is sourced but never appears in the SELECT list or any SQL clause. Removed.

From `accounts`: `customer_id`, `account_status`, `interest_rate`, `credit_limit` are sourced but only `account_id` (for JOIN) and `account_type` (for SELECT) are used. Removed the 4 unused columns.

**Remediation:** Reduced `overdraft_events` DataSourcing from 7 to 6 columns. Reduced `accounts` DataSourcing from 6 to 2 columns. Total: 5 unused columns removed.

**Evidence:** V1 SQL only references `oe.overdraft_id`, `oe.account_id`, `oe.customer_id`, `oe.overdraft_amount`, `oe.fee_amount`, `oe.fee_waived`, `oe.ifw_effective_date` from overdraft_events and `a.account_id`, `a.account_type`, `a.ifw_effective_date` from accounts. Framework provides `ifw_effective_date` automatically.

### AP5 — Asymmetric Null/Default Handling
**Finding:** N/A. No null/default handling logic in the transformation.

### AP6 — Row-by-Row Iteration
**Finding:** N/A. No External module, no foreach loops. Pure SQL transformation.

### AP7 — Magic Values
**Finding:** Clean. No hardcoded thresholds, date boundaries, or unexplained constants.

### AP8 — Complex/Dead SQL
**Finding:** Clean. The SQL is straightforward: a single JOIN with a SELECT and ORDER BY. No CTEs, no window functions, no dead code. This is the cleanest multi-source job in Tier 2.

### AP9 — Misleading Names
**Finding:** Clean. Job name "AccountOverdraftHistory" accurately describes the output: a history of overdraft events enriched with account type.

### AP10 — Over-Sourcing Date Ranges
**Finding:** Clean. DataSourcing is scoped by the framework's effective date injection for both sources.
