# FeeWaiverAnalysis -- Business Requirements Document

**Job:** FeeWaiverAnalysis
**Source V1 conf:** `/workspace/MockEtlFramework/JobExecutor/Jobs/fee_waiver_analysis.json`
**Effective dates:** 2024-10-01 through 2024-12-31 (92 dates)

---

## Data Sources

### BRD-FWA-001: Overdraft Events Source
The job sources from `datalake.overdraft_events` with 7 columns: `overdraft_id`, `account_id`, `customer_id`, `overdraft_amount`, `fee_amount`, `fee_waived`, `event_timestamp`.

**Evidence:** V1 job conf first `DataSourcing` module specifies schema `datalake`, table `overdraft_events`, with these exact 7 columns.

### BRD-FWA-002: Accounts Source
The job sources from `datalake.accounts` with 7 columns: `account_id`, `customer_id`, `account_type`, `account_status`, `interest_rate`, `credit_limit`, `apr`.

**Evidence:** V1 job conf second `DataSourcing` module specifies schema `datalake`, table `accounts`, with these exact 7 columns.

### BRD-FWA-003: Effective Date Scoping
Data is scoped to a single effective date per execution. The framework injects `ifw_effective_date` filtering at the DataSourcing layer for both sources.

**Evidence:** V1 output for any given date contains only rows where `ifw_effective_date` matches the execution date.

### BRD-FWA-004: Join Relationship
Overdraft events are LEFT JOINed to accounts on `account_id` AND `ifw_effective_date`. This preserves all overdraft events regardless of whether a matching account record exists.

**Evidence:** V1 SQL `LEFT JOIN accounts a ON oe.account_id = a.account_id AND oe.ifw_effective_date = a.ifw_effective_date`.

### BRD-FWA-005: LEFT JOIN Investigation Results
The LEFT JOIN to accounts is suspicious because ZERO columns from the accounts table appear in the SELECT, WHERE, or GROUP BY clauses. The entire accounts DataSourcing produces data that is joined but never used.

**Investigation (per Phase 1 lesson from ComplianceResolutionTime cartesian join):**

Query: `SELECT account_id, ifw_effective_date, COUNT(*) FROM datalake.accounts GROUP BY account_id, ifw_effective_date HAVING COUNT(*) > 1;`

**Result:** No duplicates found. Each (account_id, ifw_effective_date) pair appears exactly once in the accounts table. Therefore:
- The LEFT JOIN does NOT inflate row counts (unlike ComplianceResolutionTime's cartesian join)
- The LEFT JOIN is functionally dead code -- it has zero effect on the output
- However, we RETAIN the LEFT JOIN in the RE job conf for safety (removing changes nothing but adds risk)

**Disposition:** AP1 finding documented. LEFT JOIN retained in RE. AP4 remediation (removing unused accounts columns from DataSourcing) is partially applied -- only `account_id` kept (needed for JOIN ON clause).

---

## Business Rules

### BRD-FWA-006: Aggregation by Fee Waived Status
Output is aggregated by `fee_waived`, producing one row per distinct fee_waived value with:
- `event_count`: count of overdraft events
- `total_fees`: sum of fee_amount (with null handling), rounded to 2 decimal places
- `avg_fee`: average of fee_amount (with null handling), rounded to 2 decimal places

**Evidence:** V1 SQL `GROUP BY oe.fee_waived, oe.ifw_effective_date ORDER BY oe.fee_waived`. Output contains 1-2 data rows per date depending on whether both fee_waived values (0 and 1) have events.

### BRD-FWA-007: Null Handling for Fee Amount
Fee amount uses explicit null handling: `CASE WHEN oe.fee_amount IS NULL THEN 0.0 ELSE oe.fee_amount END`. This coerces NULL fee amounts to 0.0 before summing/averaging.

**Evidence:** V1 SQL uses this CASE expression for both SUM and AVG calculations. This is a defensive pattern that ensures consistent results even if fee_amount has NULL values.

### BRD-FWA-008: Ordering
Output rows are ordered by `fee_waived` ascending (0 before 1).

**Evidence:** V1 SQL `ORDER BY oe.fee_waived`. V1 output consistently shows fee_waived=0 row first when both exist.

### BRD-FWA-009: ifw_effective_date from Source
The `ifw_effective_date` column in the output comes from `overdraft_events` (injected by the framework at DataSourcing).

**Evidence:** V1 SQL accesses `oe.ifw_effective_date` and groups by it.

---

## Output Format

### BRD-FWA-010: File Format
Output is CSV with LF line endings, comma-delimited, no quoting (unless field contains comma).

**Evidence:** V1 job conf `CsvFileWriter` specifies `lineEnding: LF`, `includeHeader: true`.

### BRD-FWA-011: Header Row
Output includes a single header row as the first line.

**Evidence:** V1 job conf `includeHeader: true`. V1 output first line: `fee_waived,event_count,total_fees,avg_fee,ifw_effective_date,etl_effective_date`.

### BRD-FWA-012: Column Schema
Output contains 6 columns in this order: `fee_waived`, `event_count`, `total_fees`, `avg_fee`, `ifw_effective_date`, `etl_effective_date`.

**Evidence:** V1 output header and data rows. The first 5 are from the transformation SQL, `etl_effective_date` is appended automatically by the framework.

### BRD-FWA-013: Row Count
Output contains 1-2 data rows per date plus 1 header. No trailer.

**Evidence:** V1 output for 2024-10-01 has 2 data rows (fee_waived=0 and fee_waived=1). V1 output for 2024-12-31 has 2 data rows. V1 job conf has no `trailerFormat` field.

### BRD-FWA-014: Output Path
Output path follows the pattern: `{outputDirectory}/fee_waiver_analysis/fee_waiver_analysis/{YYYY-MM-DD}/fee_waiver_analysis.csv`.

**Evidence:** V1 job conf `CsvFileWriter` specifies `jobDirName: fee_waiver_analysis`, `outputTableDirName: fee_waiver_analysis`, `fileName: fee_waiver_analysis.csv`.

### BRD-FWA-015: Write Mode
Output uses Overwrite mode -- each execution replaces any existing file for that date.

**Evidence:** V1 job conf `writeMode: Overwrite`.
