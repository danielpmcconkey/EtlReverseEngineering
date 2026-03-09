# TopBranches -- Functional Specification Document

**Job:** TopBranches_RE
**Traces to:** BRD (jobs/TopBranches/BRD.md)

---

## Data Sourcing

### FSD-TB-001: Branch Visits Source Configuration
Source `datalake.branch_visits` with columns: `branch_id`.

**Traces to:** BRD-TB-001, BRD-TB-003
**Change from V1:** Removed `visit_id` from sourced columns (AP4 remediation). V1 sourced 2 columns; RE sources 1. `visit_id` is never referenced in the transformation SQL -- only `branch_id` is used for GROUP BY counting and JOIN.

### FSD-TB-002: Branches Source Configuration
Source `datalake.branches` with columns: `branch_id`, `branch_name`.

**Traces to:** BRD-TB-002, BRD-TB-003
**Change from V1:** None. V1 sourced 2 columns; RE sources 2. Both columns are used: `branch_id` for JOIN, `branch_name` for output.

---

## Transformation

### FSD-TB-003: SQL Transformation
Count visits per branch, join to branches for branch_name, rank by total_visits descending.

```sql
WITH visit_totals AS (
  SELECT bv.branch_id, COUNT(*) AS total_visits
  FROM branch_visits bv
  GROUP BY bv.branch_id
)
SELECT vt.branch_id, b.branch_name, vt.total_visits,
  RANK() OVER (ORDER BY vt.total_visits DESC) AS rank,
  b.ifw_effective_date
FROM visit_totals vt
JOIN branches b ON vt.branch_id = b.branch_id
ORDER BY rank, vt.branch_id
```

**Traces to:** BRD-TB-005, BRD-TB-006, BRD-TB-007, BRD-TB-008, BRD-TB-009

**Changes from V1:**
- **AP4 remediation:** `visit_id` removed from branch_visits DataSourcing. Not referenced in SQL.
- **AP10/AP8 remediation:** Removed `WHERE bv.ifw_effective_date >= '2024-10-01'` from the `visit_totals` CTE. This WHERE clause is dead SQL -- the DataSourcing layer already filters both sources to the single effective date. The framework-injected `ifw_effective_date` filter means `branch_visits` only contains rows for the current execution date. The hardcoded date comparison is redundant and would only be problematic if someone ran the job for dates before 2024-10-01 (which the `firstEffectiveDate` field prevents anyway).

**Output equivalence:** AP4 column removal is DataSourcing-only. The dead WHERE clause removal has no effect because DataSourcing already guarantees single-date data. The SELECT column list, CTE logic, JOIN, RANK, and ORDER BY are identical to V1.

### FSD-TB-004: No External Module Required
The job requires no C# External module. All logic is expressible in SQL.

**Traces to:** BRD-TB-006

---

## Output

### FSD-TB-005: CSV Writer Configuration
- `includeHeader: true` (BRD-TB-011)
- `writeMode: Overwrite` (BRD-TB-016)
- `lineEnding: LF` (BRD-TB-010)
- `trailerFormat: "CONTROL|{date}|{row_count}|{timestamp}"` (BRD-TB-014)
- `outputDirectory: {ETL_RE_OUTPUT}` (BRD-TB-015)
- `jobDirName: top_branches`
- `fileName: top_branches.csv`
- `outputTableDirName: top_branches`

**Traces to:** BRD-TB-010 through BRD-TB-016
**Change from V1:** `outputDirectory` changed from `Output/curated` to `{ETL_RE_OUTPUT}` to write to RE output tree instead of V1 output tree.

### FSD-TB-006: Output Schema
6 columns: `branch_id`, `branch_name`, `total_visits`, `rank`, `ifw_effective_date`, `etl_effective_date`.

**Traces to:** BRD-TB-012
**Change from V1:** None. Column list and order are identical. `etl_effective_date` is appended automatically by the framework.
