# BranchDirectory — Business Requirements Document

**Job:** BranchDirectory
**Source V1 conf:** `/workspace/MockEtlFramework/JobExecutor/Jobs/branch_directory.json`
**Effective dates:** 2024-10-01 through 2024-12-31 (92 dates)

---

## Data Source

### BRD-BD-001: Source Table
The job sources from `datalake.branches` with 7 columns: `branch_id`, `branch_name`, `address_line1`, `city`, `state_province`, `postal_code`, `country`.

**Evidence:** V1 job conf `DataSourcing` module specifies schema `datalake`, table `branches`, with these exact 7 columns.

### BRD-BD-002: Effective Date Scoping
Data is scoped to a single effective date per execution. The framework injects `ifw_effective_date` filtering at the DataSourcing layer.

**Evidence:** V1 output for any given date contains only rows where `ifw_effective_date` matches the execution date. Confirmed across 2024-10-01 and 2024-12-31.

---

## Business Rules

### BRD-BD-003: Deduplication by Branch ID
The output must contain at most one row per `branch_id`. If the source contains duplicate branch_ids for a given effective date, only one row per branch_id is retained.

**Evidence:** V1 SQL applies `ROW_NUMBER() OVER (PARTITION BY b.branch_id ORDER BY b.branch_id)` and filters `WHERE rn = 1`. In practice, the source data contains no duplicates (40 rows, 40 distinct branch_ids), making this a no-op.

### BRD-BD-004: Output Ordering
Rows are ordered ascending by `branch_id`.

**Evidence:** V1 SQL includes `ORDER BY branch_id`. V1 output confirms ascending order (branch_id 1 through 40).

---

## Output Format

### BRD-BD-005: File Format
Output is CSV with CRLF line endings, comma-delimited, no quoting (unless field contains comma).

**Evidence:** V1 job conf `CsvFileWriter` specifies `lineEnding: CRLF`, `includeHeader: true`. Binary inspection of V1 output confirms `\r\n` line endings.

### BRD-BD-006: Header Row
Output includes a single header row as the first line.

**Evidence:** V1 job conf `includeHeader: true`. V1 output first line: `branch_id,branch_name,address_line1,city,state_province,postal_code,country,ifw_effective_date,etl_effective_date`.

### BRD-BD-007: Column Schema
Output contains 9 columns in this order: `branch_id`, `branch_name`, `address_line1`, `city`, `state_province`, `postal_code`, `country`, `ifw_effective_date`, `etl_effective_date`.

**Evidence:** V1 output header. The first 7 are sourced columns, `ifw_effective_date` is from the framework's date injection, `etl_effective_date` is appended automatically by the framework.

### BRD-BD-008: Row Count
Output contains exactly 40 data rows (plus 1 header) for every effective date in the range.

**Evidence:** `wc -l` on V1 output for 2024-10-01 and 2024-12-31 both return 41 lines.

### BRD-BD-009: No Trailer
Output has no trailer row.

**Evidence:** V1 output last line is data row for branch_id 40, not a TRAILER marker. V1 job conf has no trailer configuration.

### BRD-BD-010: Output Path
Output path follows the pattern: `{outputDirectory}/branch_directory/branch_directory/{YYYY-MM-DD}/branch_directory.csv`.

**Evidence:** V1 job conf `CsvFileWriter` specifies `jobDirName: branch_directory`, `outputTableDirName: branch_directory`, `fileName: branch_directory.csv`. Directory structure confirmed on disk.

### BRD-BD-011: Write Mode
Output uses Overwrite mode -- each execution replaces any existing file for that date.

**Evidence:** V1 job conf `writeMode: Overwrite`.
