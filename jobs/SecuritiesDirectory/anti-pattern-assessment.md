# SecuritiesDirectory -- Anti-Pattern Assessment

**Job:** SecuritiesDirectory (V1) -> SecuritiesDirectory_RE (RE)
**Assessed against:** Master Anti-Pattern List (AP1-AP10)

---

## Summary

| AP | Name | Finding | Action |
|----|------|---------|--------|
| AP1 | Dead-End Sourcing | **FOUND** | Remediated |
| AP2 | Duplicated Logic | Clean | None |
| AP3 | Unnecessary External Module | N/A | None |
| AP4 | Unused Columns | Clean | None |
| AP5 | Asymmetric Null/Default Handling | N/A | None |
| AP6 | Row-by-Row Iteration | N/A | None |
| AP7 | Magic Values | Clean | None |
| AP8 | Complex/Dead SQL | Clean | None |
| AP9 | Misleading Names | Clean | None |
| AP10 | Over-Sourcing Date Ranges | Clean | None |

---

## Detailed Findings

### AP1 -- Dead-End Sourcing
**Finding:** **FOUND.**

V1 sources `datalake.holdings` with 6 columns (`holding_id`, `investment_id`, `security_id`, `customer_id`, `quantity`, `current_value`) but the transformation SQL references ONLY `securities s`. No column, alias, or table reference to `holdings` appears anywhere in the SQL.

**Remediation:** Removed the entire `holdings` DataSourcing module from the RE job conf. The SQL remains unchanged since it never referenced holdings.

**Evidence:** V1 SQL: `SELECT s.security_id, s.ticker, s.security_name, s.security_type, s.sector, s.exchange, s.ifw_effective_date FROM securities s ORDER BY s.security_id` -- zero references to holdings.

### AP2 -- Duplicated Logic
**Finding:** Clean. No other job produces this securities directory listing.

### AP3 -- Unnecessary External Module
**Finding:** N/A. No External module in V1. Pure SQL transformation.

### AP4 -- Unused Columns
**Finding:** Clean. All 6 sourced securities columns appear in the final SELECT. (Holdings columns are moot since the entire source is removed per AP1.)

### AP5 -- Asymmetric Null/Default Handling
**Finding:** N/A. No null/default handling logic. Columns are passed through without modification.

### AP6 -- Row-by-Row Iteration
**Finding:** N/A. No External module. Pure SQL transformation.

### AP7 -- Magic Values
**Finding:** Clean. No hardcoded thresholds or unexplained constants.

### AP8 -- Complex/Dead SQL
**Finding:** Clean. SQL is a simple SELECT with ORDER BY. No CTEs, no window functions, no dead code.

### AP9 -- Misleading Names
**Finding:** Clean. "SecuritiesDirectory" accurately describes the output: a directory listing of securities.

### AP10 -- Over-Sourcing Date Ranges
**Finding:** Clean. DataSourcing is scoped by the framework's effective date injection.
