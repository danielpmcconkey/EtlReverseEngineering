# DailyWireVolume -- Business Requirements Document

**Job:** DailyWireVolume
**Source V1 conf:** `/workspace/MockEtlFramework/JobExecutor/Jobs/daily_wire_volume.json`
**Effective dates:** 2024-10-01 through 2024-12-31 (92 dates)
**Write mode:** Append (cumulative output)

---

## Data Source

### BRD-DWV-001: Source Table
The job sources from `datalake.wire_transfers` with 6 columns: `wire_id`, `customer_id`, `direction`, `amount`, `status`, `wire_timestamp`.

**Evidence:** V1 job conf `DataSourcing` module specifies schema `datalake`, table `wire_transfers`, with these exact 6 columns.

### BRD-DWV-002: Full Date Range Sourcing
Data is sourced across the entire date range (2024-10-01 through 2024-12-31) via `minEffectiveDate` and `maxEffectiveDate` in the DataSourcing module. This is intentional -- the job aggregates wire transfer counts and amounts per date across the full range.

**Evidence:** V1 job conf DataSourcing specifies `"minEffectiveDate": "2024-10-01"`, `"maxEffectiveDate": "2024-12-31"`.

---

## Business Rules

### BRD-DWV-003: Daily Wire Volume Aggregation
The output must contain one row per `ifw_effective_date`, showing the count of wire transfers and the rounded total amount for that date. Aggregation spans the full date range.

**Evidence:** V1 SQL: `SELECT ifw_effective_date AS wire_date, COUNT(*) AS wire_count, ROUND(SUM(amount), 2) AS total_amount, ifw_effective_date FROM wire_transfers WHERE ifw_effective_date >= '2024-10-01' AND ifw_effective_date <= '2024-12-31' GROUP BY ifw_effective_date ORDER BY ifw_effective_date`.

### BRD-DWV-004: Output Ordering
Rows are ordered ascending by `ifw_effective_date` (aliased as `wire_date`).

**Evidence:** V1 SQL includes `ORDER BY ifw_effective_date`. V1 output confirms ascending chronological order.

### BRD-DWV-005: Constant Output Per Execution
Each execution of this job produces the same 92 data rows (one per date in the range), regardless of the effective date. The SQL aggregates the full range every time.

**Evidence:** V1 output for 2024-10-01 has 92 data rows. The Append mode cumulation adds another 92 rows per execution, resulting in 92*N data rows on date N (1 header + 92*92 = 8465 lines on 2024-12-31).

---

## Output Format

### BRD-DWV-006: File Format
Output is CSV with LF line endings, comma-delimited, no quoting.

**Evidence:** V1 job conf `CsvFileWriter` specifies `lineEnding: LF`, `includeHeader: true`.

### BRD-DWV-007: Header Row
Output includes a single header row as the first line.

**Evidence:** V1 job conf `includeHeader: true`. V1 output first line: `wire_date,wire_count,total_amount,ifw_effective_date,etl_effective_date`.

### BRD-DWV-008: Column Schema
Output contains 5 columns in this order: `wire_date`, `wire_count`, `total_amount`, `ifw_effective_date`, `etl_effective_date`.

**Evidence:** V1 output header. The first 3 are SQL aliases, `ifw_effective_date` is the grouping column, `etl_effective_date` is appended automatically by the framework.

### BRD-DWV-009: Cumulative Row Count (Append Mode)
Row count grows cumulatively: 92 data rows on date 1, 184 on date 2, ..., 8464 on date 92. Total lines per file = 1 (header) + 92 * (date ordinal).

**Evidence:** V1 output: Oct 1 = 93 lines, Oct 2 = 185, Dec 31 = 8465.

### BRD-DWV-010: No Trailer
Output has no trailer row.

**Evidence:** V1 output last line is a data row. No trailer configuration in V1 job conf.

### BRD-DWV-011: Output Path
Output path follows: `{outputDirectory}/daily_wire_volume/daily_wire_volume/{YYYY-MM-DD}/daily_wire_volume.csv`.

**Evidence:** V1 job conf `CsvFileWriter`: `jobDirName: daily_wire_volume`, `outputTableDirName: daily_wire_volume`, `fileName: daily_wire_volume.csv`.

### BRD-DWV-012: Write Mode
Output uses Append mode. Each execution's output includes all prior executions' data plus the current execution's data. The framework handles prior partition lookup and union.

**Evidence:** V1 job conf `writeMode: Append`.
