# TopBranches -- Anti-Pattern Assessment

**Job:** TopBranches (V1) -> TopBranches_RE (RE)
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
| AP8 | Complex/Dead SQL | **FOUND** | Remediated (combined with AP10) |
| AP9 | Misleading Names | Clean | None |
| AP10 | Over-Sourcing Date Ranges | **FOUND** | Remediated (combined with AP8) |

---

## Detailed Findings

### AP1 -- Dead-End Sourcing
**Finding:** Clean (after AP4 remediation). Two DataSourcing modules. Post-remediation:
- `branch_visits`: sources `branch_id` -- used in GROUP BY and JOIN
- `branches`: sources `branch_id` (JOIN key) and `branch_name` (output column)

All sourced columns are actively used.

### AP2 -- Duplicated Logic
**Finding:** Clean. TopBranches counts visits per branch and ranks them. BranchVisitSummary (if it exists) may also aggregate branch visits, but TopBranches produces a ranked output with branch names -- a distinct business output. More importantly, TopBranches reads from datalake tables directly, not from any other job's output.

### AP3 -- Unnecessary External Module
**Finding:** N/A. No External module in V1. Job uses SQL Transformation only, which is appropriate for the GROUP BY, JOIN, and RANK logic.

### AP4 -- Unused Columns
**Finding:** **FOUND.**

V1 DataSourcing for `branch_visits` sources 2 columns: `visit_id` and `branch_id`. However, `visit_id` is never referenced in the transformation SQL -- only `branch_id` is used for the GROUP BY counting and JOIN.

| Source | Column | Referenced in SQL? | In output? | Verdict |
|--------|--------|--------------------|------------|---------|
| branch_visits | visit_id | No | No | Unused |

**Remediation:** Removed `visit_id` from branch_visits DataSourcing (2 -> 1 column). `branch_id` is the only column needed for COUNT(*) aggregation and JOIN.

### AP5 -- Asymmetric Null/Default Handling
**Finding:** Clean. No null handling or special defaults. COUNT(*) and RANK() are standard aggregation/window functions with no null-related edge cases.

### AP6 -- Row-by-Row Iteration
**Finding:** N/A. No External module, no foreach loops. Pure SQL transformation.

### AP7 -- Magic Values
**Finding:** Clean. No hardcoded thresholds or magic numbers. The `'2024-10-01'` date literal is addressed under AP10 (dead WHERE clause).

### AP8 -- Complex/Dead SQL
**Finding:** **FOUND (combined with AP10, remediated).**

V1 SQL contains `WHERE bv.ifw_effective_date >= '2024-10-01'` in the `visit_totals` CTE. This WHERE clause is dead SQL for two reasons:

1. **DataSourcing filtering:** The framework injects `ifw_effective_date` filtering at the DataSourcing layer, ensuring `branch_visits` only contains rows for the single execution date. The WHERE clause is comparing single-date data against the first effective date, which always passes.

2. **firstEffectiveDate guard:** The job conf's `firstEffectiveDate: "2024-10-01"` prevents execution for any date before 2024-10-01, making the >= comparison always true.

**Remediation:** Removed the `WHERE bv.ifw_effective_date >= '2024-10-01'` clause entirely. DataSourcing already guarantees single-date data.

### AP9 -- Misleading Names
**Finding:** Clean. Job name "TopBranches" accurately describes the output: branches ranked by visit count (highest to lowest).

### AP10 -- Over-Sourcing Date Ranges
**Finding:** **FOUND (combined with AP8, remediated).**

The `WHERE bv.ifw_effective_date >= '2024-10-01'` clause is a hardcoded date filter applied on top of the framework's effective date filtering. This is the textbook AP10 pattern -- a SQL-level date filter that duplicates what DataSourcing already handles. It also contains a hardcoded date literal (weak AP7 signal).

**Remediation:** Removed as part of AP8 remediation. The framework's DataSourcing filtering is the single source of truth for effective date scoping.
