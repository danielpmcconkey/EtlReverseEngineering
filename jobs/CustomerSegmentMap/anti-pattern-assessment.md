# CustomerSegmentMap -- Anti-Pattern Assessment

**Job:** CustomerSegmentMap (V1) -> CustomerSegmentMap_RE (RE)
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

V1 conf sources `datalake.branches` with 4 columns: `branch_id`, `branch_name`, `city`, `state_province`. The SQL transformation only references `customers_segments cs` and `segments s`:

```sql
SELECT cs.customer_id, cs.segment_id, s.segment_name, s.segment_code, cs.ifw_effective_date
FROM customers_segments cs
JOIN segments s ON cs.segment_id = s.segment_id AND cs.ifw_effective_date = s.ifw_effective_date
ORDER BY cs.customer_id, cs.segment_id
```

The `branches` result set is never referenced. No JOIN, no subquery, no alias -- completely dead.

**Remediation:** Removed the `branches` DataSourcing module entirely from the RE job conf. Output is byte-identical since SQL never used this data.

### AP2 -- Duplicated Logic
**Finding:** Clean. No other job produces this customer-segment mapping.

### AP3 -- Unnecessary External Module
**Finding:** N/A. No External module.

### AP4 -- Unused Columns
**Finding:** Clean. All sourced columns from `customers_segments` (`customer_id`, `segment_id`) and `segments` (`segment_id`, `segment_name`, `segment_code`) appear in the SQL SELECT or JOIN condition.

### AP5 -- Asymmetric Null/Default Handling
**Finding:** N/A. No null handling logic.

### AP6 -- Row-by-Row Iteration
**Finding:** N/A. No External module.

### AP7 -- Magic Values
**Finding:** Clean. No hardcoded constants.

### AP8 -- Complex/Dead SQL
**Finding:** Clean. Simple JOIN query. No CTEs, no window functions.

### AP9 -- Misleading Names
**Finding:** Clean. "CustomerSegmentMap" accurately describes the customer-to-segment mapping.

### AP10 -- Over-Sourcing Date Ranges
**Finding:** Clean. Standard single-date scoping.
