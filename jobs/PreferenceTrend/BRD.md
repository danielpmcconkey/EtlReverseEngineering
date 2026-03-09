# PreferenceTrend -- Business Requirements Document

**Job:** PreferenceTrend
**Source V1 conf:** `/workspace/MockEtlFramework/JobExecutor/Jobs/preference_trend.json`
**Effective dates:** 2024-10-01 through 2024-12-31 (92 dates)
**Write mode:** Append (cumulative output)

---

## Data Source

### BRD-PT-001: Source Table
The job sources from `datalake.customer_preferences` with 4 columns: `preference_id`, `customer_id`, `preference_type`, `opted_in`.

**Evidence:** V1 job conf `DataSourcing` module specifies schema `datalake`, table `customer_preferences`, with these exact 4 columns.

### BRD-PT-002: Effective Date Scoping
Data is scoped to a single effective date per execution via the framework's standard `ifw_effective_date` injection at the DataSourcing layer. No `minEffectiveDate`/`maxEffectiveDate` overrides.

**Evidence:** V1 job conf DataSourcing has no min/max date fields. Framework default behavior applies.

---

## Business Rules

### BRD-PT-003: Preference Aggregation by Type
The output contains one row per `preference_type`, showing counts of opted-in and opted-out customers for that preference type on the effective date.

**Evidence:** V1 SQL: `SELECT cp.preference_type, SUM(CASE WHEN cp.opted_in = 1 THEN 1 ELSE 0 END) AS opted_in_count, SUM(CASE WHEN cp.opted_in = 0 THEN 1 ELSE 0 END) AS opted_out_count, cp.ifw_effective_date FROM customer_preferences cp GROUP BY cp.preference_type, cp.ifw_effective_date`.

### BRD-PT-004: Row Count Per Execution
Each execution produces 5 data rows (one per preference type: E_STATEMENTS, MARKETING_EMAIL, MARKETING_SMS, PAPER_STATEMENTS, PUSH_NOTIFICATION).

**Evidence:** V1 output for 2024-10-01 has 5 data rows (6 lines total with header). Dec 31 has 460 data rows (5 * 92 cumulative via Append mode).

### BRD-PT-005: No Explicit Ordering
The SQL does not include an ORDER BY clause. Row order within each execution's contribution is non-deterministic but consistent due to GROUP BY semantics on the preference_type values.

**Evidence:** V1 SQL has no ORDER BY. V1 output shows consistent ordering across dates.

---

## Output Format

### BRD-PT-006: File Format
Output is CSV with LF line endings, comma-delimited, no quoting.

**Evidence:** V1 job conf `CsvFileWriter` specifies `lineEnding: LF`, `includeHeader: true`.

### BRD-PT-007: Header Row
Output includes a single header row: `preference_type,opted_in_count,opted_out_count,ifw_effective_date,etl_effective_date`.

**Evidence:** V1 output first line confirmed.

### BRD-PT-008: Column Schema
Output contains 5 columns: `preference_type`, `opted_in_count`, `opted_out_count`, `ifw_effective_date`, `etl_effective_date`.

**Evidence:** V1 output header. First 3 are SQL-derived, `ifw_effective_date` is from GROUP BY, `etl_effective_date` is framework auto-append.

### BRD-PT-009: Cumulative Row Count (Append Mode)
Row count grows cumulatively: 5 data rows on date 1, 10 on date 2, ..., 460 on date 92. Total lines per file = 1 (header) + 5 * (date ordinal).

**Evidence:** V1 output: Oct 1 = 6 lines, Dec 31 = 461 lines.

### BRD-PT-010: No Trailer
Output has no trailer row.

**Evidence:** V1 output last line is data. No trailer configuration in V1 job conf.

### BRD-PT-011: Output Path
Output path: `{outputDirectory}/preference_trend/preference_trend/{YYYY-MM-DD}/preference_trend.csv`.

**Evidence:** V1 job conf `CsvFileWriter`: `jobDirName: preference_trend`, `outputTableDirName: preference_trend`, `fileName: preference_trend.csv`.

### BRD-PT-012: Write Mode
Output uses Append mode. The framework handles cumulative output via prior partition union.

**Evidence:** V1 job conf `writeMode: Append`.
