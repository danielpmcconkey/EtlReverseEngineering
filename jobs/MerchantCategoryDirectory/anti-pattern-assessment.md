# MerchantCategoryDirectory -- Anti-Pattern Assessment

**Job:** MerchantCategoryDirectory (V1) -> MerchantCategoryDirectory_RE (RE)
**Assessed against:** Master Anti-Pattern List (AP1-AP10)

---

## Summary

| AP | Name | Finding | Action |
|----|------|---------|--------|
| AP1 | Dead-End Sourcing | **FOUND** | **Remediated** |
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

V1 conf sources `datalake.cards` with columns `card_id`, `customer_id`, `card_type`. The SQL transformation is:
```sql
SELECT mc.mcc_code, mc.mcc_description, mc.risk_level, mc.ifw_effective_date FROM merchant_categories mc
```

The `cards` result set is never referenced. No JOIN, no subquery, no alias -- it's completely dead. The framework loads the entire `cards` table for each effective date, consuming I/O and memory for zero functional purpose.

**Remediation:** Removed the `cards` DataSourcing module entirely from the RE job conf. Since the SQL never references `cards`, this has zero impact on output. Output remains byte-identical.

**Evidence:** Confirmed `cards` alias does not appear anywhere in the SQL string. Verified V1 output on Oct 1 (20 rows) matches expected output from the `merchant_categories` query alone.

### AP2 -- Duplicated Logic
**Finding:** Clean. No other job produces this merchant category directory.

### AP3 -- Unnecessary External Module
**Finding:** N/A. No External module.

### AP4 -- Unused Columns
**Finding:** Clean. All 3 sourced columns from `merchant_categories` appear in the SQL SELECT.

### AP5 -- Asymmetric Null/Default Handling
**Finding:** N/A. No null handling logic.

### AP6 -- Row-by-Row Iteration
**Finding:** N/A. No External module.

### AP7 -- Magic Values
**Finding:** Clean. No hardcoded constants.

### AP8 -- Complex/Dead SQL
**Finding:** Clean. Single direct SELECT, no CTEs, no window functions.

### AP9 -- Misleading Names
**Finding:** Clean. "MerchantCategoryDirectory" accurately describes the output.

### AP10 -- Over-Sourcing Date Ranges
**Finding:** Clean. Standard single-date scoping.
