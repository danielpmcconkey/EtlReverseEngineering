# PreferenceChangeCount — Anti-Pattern Assessment

**Job:** PreferenceChangeCount (V1) -> PreferenceChangeCount_RE (RE)
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

### AP1 — Dead-End Sourcing
**Finding:** **FOUND.**

The `datalake.customers` table is sourced with 4 columns (`id`, `prefix`, `first_name`, `last_name`) but ZERO of these columns appear anywhere in the transformation SQL. There is no JOIN condition referencing customers, no WHERE clause, no SELECT. The entire DataSourcing module is dead-end.

**Remediation:** Removed the `customers` DataSourcing module entirely. Same pattern as SecuritiesDirectory (dead `holdings` source) and TransactionSizeBuckets (dead `accounts` source). The customers data contributes nothing to the output.

**Evidence:** V1 SQL references only `customer_preferences cp` -- `cp.customer_id`, `cp.preference_type`, `cp.opted_in`, `cp.ifw_effective_date`. No `c.` or `customers.` alias appears anywhere.

### AP2 — Duplicated Logic
**Finding:** Clean. No other job produces this exact output.

### AP3 — Unnecessary External Module
**Finding:** N/A. No External module in V1.

### AP4 — Unused Columns
**Finding:** **FOUND.**

From `customer_preferences`: `updated_date` is sourced but never referenced in any SQL clause. `preference_id` is only used in the dead RANK() ORDER BY (see AP8).

**Remediation:** Removed `updated_date` from DataSourcing (never referenced in SQL). Removed `preference_id` as well -- it was only used in the RANK() ORDER BY clause, which is itself removed by AP8. With the RANK gone, `preference_id` has no remaining references.

From `customers`: ALL 4 columns unused (covered by AP1 remediation above).

### AP5 — Asymmetric Null/Default Handling
**Finding:** N/A. The CASE expressions produce 1 or 0, no null handling needed.

### AP6 — Row-by-Row Iteration
**Finding:** N/A. No External module.

### AP7 — Magic Values
**Finding:** Clean. The preference type strings `'MARKETING_EMAIL'` and `'MARKETING_SMS'` are domain values, not magic numbers.

### AP8 — Complex/Dead SQL
**Finding:** **FOUND.**

V1 SQL computes `RANK() OVER (PARTITION BY cp.customer_id, cp.preference_type ORDER BY cp.preference_id) AS rnk` in the `all_prefs` CTE. The resulting `rnk` column is:
- Not in the final SELECT
- Not used in any WHERE clause
- Not referenced by the `summary` CTE's GROUP BY or aggregations
- Completely dead computation

**Remediation:** Removed the RANK() window function from the `all_prefs` CTE. The CTE now simply selects `customer_id`, `preference_type`, `opted_in`, `ifw_effective_date`. Output is byte-identical because `rnk` was never consumed.

**Evidence:** The `summary` CTE uses `FROM all_prefs` and references only `customer_id`, `preference_type`, `opted_in`, `ifw_effective_date` -- it never references `rnk`.

### AP9 — Misleading Names
**Finding:** Clean. Job name "PreferenceChangeCount" describes the output: a count of preference changes per customer.

### AP10 — Over-Sourcing Date Ranges
**Finding:** Clean. DataSourcing is scoped by the framework's effective date injection.
