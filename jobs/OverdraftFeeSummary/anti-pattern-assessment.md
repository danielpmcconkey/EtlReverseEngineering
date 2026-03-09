# OverdraftFeeSummary -- Anti-Pattern Assessment

**Job:** OverdraftFeeSummary (V1) -> OverdraftFeeSummary_RE (RE)
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
| AP7 | Magic Values | Clean | None |
| AP8 | Complex/Dead SQL | **FOUND** | Remediated |
| AP9 | Misleading Names | Clean | None |
| AP10 | Over-Sourcing Date Ranges | Clean | None |

---

## Detailed Findings

### AP1 -- Dead-End Sourcing
**Finding:** Clean (after AP4 remediation). Single DataSourcing module (`datalake.overdraft_events`). Post-remediation, both sourced columns (`fee_amount`, `fee_waived`) are used in the transformation SQL and appear in the output.

### AP2 -- Duplicated Logic
**Finding:** Clean. No other job produces overdraft fee summary statistics. OverdraftFeeSummary is the sole producer of this output.

### AP3 -- Unnecessary External Module
**Finding:** N/A. No External module in V1. Job uses SQL Transformation only, which is appropriate for the GROUP BY aggregation logic.

### AP4 -- Unused Columns
**Finding:** **FOUND.**

V1 DataSourcing sources 7 columns. Of these, 5 are never referenced in the transformation SQL or output:

| Column | Referenced in SQL? | In output? | Verdict |
|--------|--------------------|------------|---------|
| overdraft_id | Only in dead ROW_NUMBER ORDER BY | No | Unused (dead code dependency) |
| account_id | No | No | Unused |
| customer_id | No | No | Unused |
| overdraft_amount | No | No | Unused |
| event_timestamp | No | No | Unused |

**Remediation:** Removed all 5 columns from DataSourcing. RE sources only `fee_amount` and `fee_waived`. This reduces data transfer from 7 to 2 columns and makes the sourcing contract honest about what the job actually needs.

### AP5 -- Asymmetric Null/Default Handling
**Finding:** Clean. The ROUND(,2) functions produce consistent rounding behavior. No integer division issues (unlike ComplianceResolutionTime). No null handling concerns -- fee_amount and fee_waived are always populated in the source data.

### AP6 -- Row-by-Row Iteration
**Finding:** N/A. No External module, no foreach loops. Pure SQL transformation.

### AP7 -- Magic Values
**Finding:** Clean. No hardcoded thresholds, magic numbers, or unexplained constants. The `2` in ROUND(,2) is a standard decimal precision parameter.

### AP8 -- Complex/Dead SQL
**Finding:** **FOUND (one issue, fully remediated).**

V1 SQL wraps the query in a CTE:
```sql
WITH all_events AS (
  SELECT oe.overdraft_id, oe.fee_amount, oe.fee_waived, oe.ifw_effective_date,
    ROW_NUMBER() OVER (PARTITION BY oe.ifw_effective_date ORDER BY oe.overdraft_id) AS rn
  FROM overdraft_events oe
)
SELECT ae.fee_waived, ROUND(SUM(ae.fee_amount), 2) AS total_fees, ...
FROM all_events ae
GROUP BY ae.fee_waived, ae.ifw_effective_date
ORDER BY ae.fee_waived
```

The `ROW_NUMBER()` window function computes `rn` for every row, but `rn` is never referenced anywhere in the outer query -- not in SELECT, WHERE, GROUP BY, or ORDER BY. The CTE passes through all rows unfiltered (no WHERE clause). The entire CTE is a no-op wrapper around the base table.

**Remediation:** Removed the CTE entirely. RE uses a direct query:
```sql
SELECT oe.fee_waived, ROUND(SUM(oe.fee_amount), 2) AS total_fees,
  COUNT(*) AS event_count, ROUND(AVG(oe.fee_amount), 2) AS avg_fee,
  oe.ifw_effective_date
FROM overdraft_events oe
GROUP BY oe.fee_waived, oe.ifw_effective_date
ORDER BY oe.fee_waived
```

This is algebraically identical. The CTE added computation (ROW_NUMBER) that was never consumed. Unlike ComplianceResolutionTime's cartesian join, this AP8 finding is pure dead code with zero impact on output.

### AP9 -- Misleading Names
**Finding:** Clean. Job name "OverdraftFeeSummary" accurately describes the output: summary statistics of overdraft fees grouped by waiver status.

### AP10 -- Over-Sourcing Date Ranges
**Finding:** Clean. DataSourcing is scoped by the framework's effective date injection. No broad date range sourcing or post-filter narrowing.
