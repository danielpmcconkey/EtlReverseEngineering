# BranchDirectory — Anti-Pattern Assessment

**Job:** BranchDirectory (V1) → BranchDirectory_RE (RE)
**Assessed against:** Master Anti-Pattern List (AP1–AP10)

---

## Summary

| AP | Name | Finding | Action |
|----|------|---------|--------|
| AP1 | Dead-End Sourcing | Clean | None |
| AP2 | Duplicated Logic | Clean | None |
| AP3 | Unnecessary External Module | N/A | None |
| AP4 | Unused Columns | Clean | None |
| AP5 | Asymmetric Null/Default Handling | N/A | None |
| AP6 | Row-by-Row Iteration | N/A | None |
| AP7 | Magic Values | Clean | None |
| AP8 | Complex/Dead SQL | **FOUND** | Remediated |
| AP9 | Misleading Names | Clean | None |
| AP10 | Over-Sourcing Date Ranges | Clean | None |

---

## Detailed Findings

### AP1 — Dead-End Sourcing
**Finding:** Clean. Single DataSourcing module (`datalake.branches`), all sourced data is used in transformation and output.

### AP2 — Duplicated Logic
**Finding:** Clean. No other job produces this output. BranchDirectory is the sole producer of the branch directory listing.

### AP3 — Unnecessary External Module
**Finding:** N/A. No External module in V1. Job uses SQL Transformation only, which is appropriate for the logic complexity.

### AP4 — Unused Columns
**Finding:** Clean. All 7 sourced columns (`branch_id`, `branch_name`, `address_line1`, `city`, `state_province`, `postal_code`, `country`) appear in the final SELECT and output.

### AP5 — Asymmetric Null/Default Handling
**Finding:** N/A. No null/default handling logic in the transformation. Columns are passed through without modification.

### AP6 — Row-by-Row Iteration
**Finding:** N/A. No External module, no foreach loops. Pure SQL transformation.

### AP7 — Magic Values
**Finding:** Clean. No hardcoded thresholds, date boundaries, or unexplained constants in the transformation SQL.

### AP8 — Complex/Dead SQL
**Finding:** **FOUND.**

V1 SQL uses a CTE with `ROW_NUMBER() OVER (PARTITION BY b.branch_id ORDER BY b.branch_id)` and filters `WHERE rn = 1`.

**Problem:** The `ORDER BY` clause in the window function is the same column as `PARTITION BY`. Within each partition (a single branch_id), ordering by branch_id produces only one possible ordering since all values are identical. The row numbering is therefore non-deterministic for any partition with >1 row. In practice, source data has 40 unique branch_ids with no duplicates, so every partition contains exactly 1 row, making the entire ROW_NUMBER + WHERE rn = 1 construct a no-op.

**Remediation:** Removed the CTE and ROW_NUMBER entirely. Replaced with a direct `SELECT ... FROM branches ORDER BY branch_id`. Output is byte-identical because the dedup was filtering nothing.

**Evidence:** Source data verified: `SELECT COUNT(*), COUNT(DISTINCT branch_id) FROM datalake.branches WHERE ifw_effective_date = '2024-10-01'` returns 40, 40.

### AP9 — Misleading Names
**Finding:** Clean. Job name "BranchDirectory" accurately describes the output: a directory (listing) of branches.

### AP10 — Over-Sourcing Date Ranges
**Finding:** Clean. DataSourcing is scoped by the framework's effective date injection. No broad date range sourcing or post-filter narrowing.
