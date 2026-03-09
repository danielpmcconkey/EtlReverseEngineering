# BranchDirectory — Functional Specification Document

**Job:** BranchDirectory_RE
**Traces to:** BRD (jobs/BranchDirectory/BRD.md)

---

## Data Sourcing

### FSD-BD-001: Source Configuration
Source `datalake.branches` with columns: `branch_id`, `branch_name`, `address_line1`, `city`, `state_province`, `postal_code`, `country`.

**Traces to:** BRD-BD-001, BRD-BD-002
**Change from V1:** None. DataSourcing module is identical.

---

## Transformation

### FSD-BD-002: SQL Transformation
Select all 7 source columns plus `ifw_effective_date`, ordered by `branch_id` ascending.

```sql
SELECT branch_id, branch_name, address_line1, city, state_province, postal_code, country, ifw_effective_date
FROM branches
ORDER BY branch_id
```

**Traces to:** BRD-BD-003, BRD-BD-004
**Change from V1:** Removed dead ROW_NUMBER CTE (AP8 remediation). V1 used a CTE with `ROW_NUMBER() OVER (PARTITION BY branch_id ORDER BY branch_id)` and filtered `WHERE rn = 1`. Since ORDER BY matches PARTITION BY, row numbering within each partition is non-deterministic. Source data contains no duplicates (40 rows = 40 distinct branch_ids), making the dedup a complete no-op. Simplified to direct SELECT.

**Output equivalence:** Byte-identical. The ROW_NUMBER and WHERE clause were filtering nothing, and the ORDER BY branch_id is preserved.

### FSD-BD-003: No External Module Required
The job requires no C# External module. All logic is expressible in SQL.

**Traces to:** BRD-BD-003, BRD-BD-004
**DELIV-05 note:** Satisfied trivially -- no external module exists in V1, none needed in RE.

---

## Output

### FSD-BD-004: CSV Writer Configuration
- `includeHeader: true` (BRD-BD-006)
- `writeMode: Overwrite` (BRD-BD-011)
- `lineEnding: CRLF` (BRD-BD-005)
- `outputDirectory: {ETL_RE_OUTPUT}` (BRD-BD-010)
- `jobDirName: branch_directory`
- `fileName: branch_directory.csv`
- `outputTableDirName: branch_directory`

**Traces to:** BRD-BD-005 through BRD-BD-011
**Change from V1:** `outputDirectory` changed from `Output/curated` to `{ETL_RE_OUTPUT}` to write to RE output tree instead of V1 output tree.

### FSD-BD-005: Output Schema
9 columns: `branch_id`, `branch_name`, `address_line1`, `city`, `state_province`, `postal_code`, `country`, `ifw_effective_date`, `etl_effective_date`.

**Traces to:** BRD-BD-007
**Change from V1:** None. Column list and order are identical. `etl_effective_date` is appended automatically by the framework.
