# ComplianceResolutionTime -- Anti-Pattern Assessment

**Job:** ComplianceResolutionTime (V1) -> ComplianceResolutionTime_RE (RE)
**Assessed against:** Master Anti-Pattern List (AP1-AP10)

---

## Summary

| AP | Name | Finding | Action |
|----|------|---------|--------|
| AP1 | Dead-End Sourcing | Clean | None |
| AP2 | Duplicated Logic | Clean | None |
| AP3 | Unnecessary External Module | N/A | None |
| AP4 | Unused Columns | **FOUND** | Remediated |
| AP5 | Asymmetric Null/Default Handling | **FOUND** | Documented only |
| AP6 | Row-by-Row Iteration | N/A | None |
| AP7 | Magic Values | Clean | None |
| AP8 | Complex/Dead SQL | **FOUND** | Remediated |
| AP9 | Misleading Names | Clean | None |
| AP10 | Over-Sourcing Date Ranges | Clean | None |

---

## Detailed Findings

### AP1 -- Dead-End Sourcing
**Finding:** Clean. Single DataSourcing module (`datalake.compliance_events`). All sourced columns (post-AP4 remediation) are used in transformation and/or output.

### AP2 -- Duplicated Logic
**Finding:** Clean. No other job produces compliance resolution time statistics. ComplianceResolutionTime is the sole producer of this output.

### AP3 -- Unnecessary External Module
**Finding:** N/A. No External module in V1. Job uses SQL Transformation only, which is appropriate for the filtering and aggregation logic.

### AP4 -- Unused Columns
**Finding:** **FOUND.**

V1 DataSourcing sources 6 columns including `customer_id`. However, `customer_id` is never referenced in the transformation SQL (not in the CTE filter, not in the SELECT, not in the GROUP BY, not in the output). It is pure dead weight -- sourced from the database, loaded into the result set, and then discarded.

**Remediation:** Removed `customer_id` from the DataSourcing columns list. RE sources 5 columns: `event_id`, `event_type`, `event_date`, `status`, `review_date`. This reduces data transfer and makes the sourcing contract honest about what the job actually needs.

**Note:** `event_id` is also not in the final output, but it is implicitly used as the unit of counting in the aggregation (`COUNT(*)` counts events). It's not "unused" in the same way `customer_id` is.

### AP5 -- Asymmetric Null/Default Handling
**Finding:** **FOUND (documented, NOT remediated).**

The `avg_resolution_days` calculation uses integer division: `CAST(SUM(days_to_resolve) AS INTEGER) / CAST(COUNT(*) AS INTEGER)`. This truncates toward zero rather than rounding. For example:
- AML_FLAG: 23920 / 1380 = 17.333... -> 17 (truncated)
- SANCTIONS_SCREEN: 19205 / 1610 = 11.926... -> 11 (truncated)

This is V1 behavior and is **NOT changed** in RE. Output must be byte-identical, and the integer division is the established business logic. Whether this is "correct" business intent or an original coding oversight is outside the scope of RE.

### AP6 -- Row-by-Row Iteration
**Finding:** N/A. No External module, no foreach loops. Pure SQL transformation.

### AP7 -- Magic Values
**Finding:** Clean. The `'Cleared'` status filter is a domain value, not a magic number. No hardcoded thresholds, date boundaries, or unexplained constants.

### AP8 -- Complex/Dead SQL
**Finding:** **FOUND (two issues).**

**Issue 1: Cartesian join hack (`JOIN compliance_events ON 1=1`)**
V1 SQL joins the `resolved` CTE back to the full `compliance_events` table with `ON 1=1` (cartesian join) solely to access `compliance_events.ifw_effective_date`. This is unnecessary because `ifw_effective_date` is available on every row in `compliance_events`, including the rows already selected into the `resolved` CTE. The GROUP BY collapses the cartesian explosion, so the output is correct, but the join forces the database to create N*M intermediate rows before aggregation.

**Remediation:** Access `ifw_effective_date` directly from `compliance_events` within the `resolved` CTE. No join needed.

**Issue 2: Unused ROW_NUMBER**
V1 SQL computes `ROW_NUMBER() OVER (PARTITION BY event_type ORDER BY event_date) AS rn` in the `resolved` CTE, but `rn` is never referenced in the outer SELECT or in any WHERE clause. The window function is computed for every row and then thrown away during GROUP BY aggregation.

**Remediation:** Removed the `ROW_NUMBER()` window function entirely.

### AP9 -- Misleading Names
**Finding:** Clean. Job name "ComplianceResolutionTime" accurately describes the output: statistics about how long compliance events take to resolve.

### AP10 -- Over-Sourcing Date Ranges
**Finding:** Clean. DataSourcing is scoped by the framework's effective date injection. No broad date range sourcing or post-filter narrowing.
