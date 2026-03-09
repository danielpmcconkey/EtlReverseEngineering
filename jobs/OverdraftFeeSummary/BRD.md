# OverdraftFeeSummary -- Business Requirements Document

**Job:** OverdraftFeeSummary
**Source V1 conf:** `/workspace/MockEtlFramework/JobExecutor/Jobs/overdraft_fee_summary.json`
**Effective dates:** 2024-10-01 through 2024-12-31 (92 dates)

---

## Data Source

### BRD-OFS-001: Source Table
The job sources from `datalake.overdraft_events` with 7 columns: `overdraft_id`, `account_id`, `customer_id`, `overdraft_amount`, `fee_amount`, `fee_waived`, `event_timestamp`.

**Evidence:** V1 job conf `DataSourcing` module specifies schema `datalake`, table `overdraft_events`, with these exact 7 columns.

### BRD-OFS-002: Effective Date Scoping
Data is scoped to a single effective date per execution. The framework injects `ifw_effective_date` filtering at the DataSourcing layer.

**Evidence:** V1 output for any given date contains only rows where `ifw_effective_date` matches the execution date. Confirmed across 2024-10-01 and 2024-12-31.

---

## Business Rules

### BRD-OFS-003: Aggregation by Fee Waived Status
Output is aggregated by `fee_waived`, producing one row per distinct fee_waived value with:
- `total_fees`: sum of fee_amount, rounded to 2 decimal places
- `event_count`: count of events
- `avg_fee`: average fee_amount, rounded to 2 decimal places

**Evidence:** V1 SQL `GROUP BY ae.fee_waived, ae.ifw_effective_date`. Output contains 2 data rows per date (fee_waived=0 and fee_waived=1).

### BRD-OFS-004: Total Fees Calculation
Total fees per group is calculated as `ROUND(SUM(fee_amount), 2)`.

**Evidence:** V1 SQL `ROUND(SUM(ae.fee_amount), 2) AS total_fees`. V1 output for 2024-10-01: fee_waived=0 shows total_fees=35, fee_waived=1 shows total_fees=0.

### BRD-OFS-005: Event Count
Event count per group is `COUNT(*)` -- the raw number of overdraft events in each fee_waived category.

**Evidence:** V1 SQL `COUNT(*) AS event_count`. V1 output for 2024-10-01: fee_waived=0 has event_count=1, fee_waived=1 has event_count=2.

### BRD-OFS-006: Average Fee Calculation
Average fee per group is calculated as `ROUND(AVG(fee_amount), 2)`.

**Evidence:** V1 SQL `ROUND(AVG(ae.fee_amount), 2) AS avg_fee`. V1 output for 2024-10-01: fee_waived=0 shows avg_fee=35, fee_waived=1 shows avg_fee=0.

### BRD-OFS-007: Ordering
Output rows are ordered by `fee_waived` ascending (0 before 1).

**Evidence:** V1 SQL `ORDER BY ae.fee_waived`. V1 output consistently shows fee_waived=0 row first.

### BRD-OFS-008: ifw_effective_date from Source
The `ifw_effective_date` column in the output comes from the overdraft_events table (injected by the framework at DataSourcing).

**Evidence:** V1 SQL accesses `ae.ifw_effective_date` and groups by it. Every row for a given execution date shares the same `ifw_effective_date` value.

---

## Output Format

### BRD-OFS-009: File Format
Output is CSV with LF line endings, comma-delimited, no quoting (unless field contains comma).

**Evidence:** V1 job conf `CsvFileWriter` specifies `lineEnding: LF`, `includeHeader: true`. Binary inspection of V1 output confirms `\n` line endings.

### BRD-OFS-010: Header Row
Output includes a single header row as the first line.

**Evidence:** V1 job conf `includeHeader: true`. V1 output first line: `fee_waived,total_fees,event_count,avg_fee,ifw_effective_date,etl_effective_date`.

### BRD-OFS-011: Column Schema
Output contains 6 columns in this order: `fee_waived`, `total_fees`, `event_count`, `avg_fee`, `ifw_effective_date`, `etl_effective_date`.

**Evidence:** V1 output header and data rows. The first 5 are from the transformation SQL, `etl_effective_date` is appended automatically by the framework.

### BRD-OFS-012: Row Count
Output contains exactly 2 data rows (one per fee_waived value) plus 1 header for every effective date. No trailer.

**Evidence:** V1 output for 2024-10-01 and 2024-12-31 both contain 3 lines (1 header + 2 data). V1 job conf has no `trailerFormat` field.

### BRD-OFS-013: Output Path
Output path follows the pattern: `{outputDirectory}/overdraft_fee_summary/overdraft_fee_summary/{YYYY-MM-DD}/overdraft_fee_summary.csv`.

**Evidence:** V1 job conf `CsvFileWriter` specifies `jobDirName: overdraft_fee_summary`, `outputTableDirName: overdraft_fee_summary`, `fileName: overdraft_fee_summary.csv`.

### BRD-OFS-014: Write Mode
Output uses Overwrite mode -- each execution replaces any existing file for that date.

**Evidence:** V1 job conf `writeMode: Overwrite`.
