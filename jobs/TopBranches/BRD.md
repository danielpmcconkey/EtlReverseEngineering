# TopBranches -- Business Requirements Document

**Job:** TopBranches
**Source V1 conf:** `/workspace/MockEtlFramework/JobExecutor/Jobs/top_branches.json`
**Effective dates:** 2024-10-01 through 2024-12-31 (92 dates)

---

## Data Sources

### BRD-TB-001: Branch Visits Source
The job sources from `datalake.branch_visits` with 2 columns: `visit_id`, `branch_id`.

**Evidence:** V1 job conf first `DataSourcing` module specifies schema `datalake`, table `branch_visits`, with these exact 2 columns.

### BRD-TB-002: Branches Source
The job sources from `datalake.branches` with 2 columns: `branch_id`, `branch_name`.

**Evidence:** V1 job conf second `DataSourcing` module specifies schema `datalake`, table `branches`, with these exact 2 columns.

### BRD-TB-003: Effective Date Scoping
Data is scoped to a single effective date per execution. The framework injects `ifw_effective_date` filtering at the DataSourcing layer for both sources.

**Evidence:** V1 output for any given date contains only rows where `ifw_effective_date` matches the execution date.

### BRD-TB-004: No Runtime Dependencies
TopBranches reads directly from `datalake.branch_visits` and `datalake.branches`. It does NOT depend on the output of BranchVisitSummary, BranchDirectory, or any other RE'd job. It operates directly on raw datalake tables.

**Evidence:** V1 job conf DataSourcing modules reference `datalake.branch_visits` and `datalake.branches` -- not any curated output.

### BRD-TB-005: Join Relationship
Visit totals per branch are joined to branches on `branch_id` to obtain `branch_name` for the output. This is an INNER JOIN.

**Evidence:** V1 SQL `JOIN branches b ON vt.branch_id = b.branch_id`.

---

## Business Rules

### BRD-TB-006: Visit Counting
Visits per branch are counted using `COUNT(*)` grouped by `branch_id`. Each row in `branch_visits` represents one visit.

**Evidence:** V1 SQL `SELECT bv.branch_id, COUNT(*) AS total_visits FROM branch_visits bv ... GROUP BY bv.branch_id`.

### BRD-TB-007: Ranking
Branches are ranked by total_visits descending using `RANK()` window function. Ties receive the same rank, and the next rank is skipped (standard RANK behavior, not DENSE_RANK).

**Evidence:** V1 SQL `RANK() OVER (ORDER BY vt.total_visits DESC) AS rank`. V1 output for 2024-10-01 shows multiple branches tied at rank 1 (10 visits each), then rank 3 (next group).

### BRD-TB-008: Ordering
Output rows are ordered by rank ascending, then branch_id ascending (for tie-breaking within same rank).

**Evidence:** V1 SQL `ORDER BY rank, vt.branch_id`. V1 output shows branches ordered by descending visit count, with ties broken by ascending branch_id.

### BRD-TB-009: ifw_effective_date from Branches
The `ifw_effective_date` column in the output comes from the `branches` table (injected by the framework at DataSourcing).

**Evidence:** V1 SQL accesses `b.ifw_effective_date` in the SELECT. Since both sources share the same effective date, this is equivalent to using either source's `ifw_effective_date`.

---

## Output Format

### BRD-TB-010: File Format
Output is CSV with LF line endings, comma-delimited, no quoting (unless field contains comma).

**Evidence:** V1 job conf `CsvFileWriter` specifies `lineEnding: LF`, `includeHeader: true`.

### BRD-TB-011: Header Row
Output includes a single header row as the first line.

**Evidence:** V1 job conf `includeHeader: true`. V1 output first line: `branch_id,branch_name,total_visits,rank,ifw_effective_date,etl_effective_date`.

### BRD-TB-012: Column Schema
Output contains 6 columns in this order: `branch_id`, `branch_name`, `total_visits`, `rank`, `ifw_effective_date`, `etl_effective_date`.

**Evidence:** V1 output header and data rows. The first 5 are from the transformation SQL, `etl_effective_date` is appended automatically by the framework.

### BRD-TB-013: Row Count
Output contains 40 data rows (all branches ranked) plus 1 header and 1 trailer for every effective date.

**Evidence:** V1 output for 2024-10-01 contains 42 lines (1 header + 40 data + 1 trailer). There are 40 branches in the source data.

### BRD-TB-014: Trailer Format -- Non-Deterministic
Output includes a trailer row in the format `CONTROL|{date}|{row_count}|{timestamp}` where:
- `date` is the effective date
- `row_count` is the number of data rows (always 40)
- `timestamp` is the runtime ISO timestamp (e.g., `2026-03-08T17:52:27Z`)

**CRITICAL:** The `{timestamp}` token makes this trailer NON-DETERMINISTIC. V1 and RE runs will produce different timestamps. Proofmark must exclude the trailer from comparison via `trailer_rows: 1`.

**Evidence:** V1 job conf `trailerFormat: "CONTROL|{date}|{row_count}|{timestamp}"`. V1 output last line for 2024-10-01: `CONTROL|2024-10-01|40|2026-03-08T17:52:27Z`.

### BRD-TB-015: Output Path
Output path follows the pattern: `{outputDirectory}/top_branches/top_branches/{YYYY-MM-DD}/top_branches.csv`.

**Evidence:** V1 job conf `CsvFileWriter` specifies `jobDirName: top_branches`, `outputTableDirName: top_branches`, `fileName: top_branches.csv`.

### BRD-TB-016: Write Mode
Output uses Overwrite mode -- each execution replaces any existing file for that date.

**Evidence:** V1 job conf `writeMode: Overwrite`.
