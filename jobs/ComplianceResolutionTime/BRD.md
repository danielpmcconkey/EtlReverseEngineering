# ComplianceResolutionTime -- Business Requirements Document

**Job:** ComplianceResolutionTime
**Source V1 conf:** `/workspace/MockEtlFramework/JobExecutor/Jobs/compliance_resolution_time.json`
**Effective dates:** 2024-10-01 through 2024-12-31 (92 dates)

---

## Data Source

### BRD-CRT-001: Source Table
The job sources from `datalake.compliance_events` with 6 columns: `event_id`, `customer_id`, `event_type`, `event_date`, `status`, `review_date`.

**Evidence:** V1 job conf `DataSourcing` module specifies schema `datalake`, table `compliance_events`, with these exact 6 columns.

### BRD-CRT-002: Effective Date Scoping
Data is scoped to a single effective date per execution. The framework injects `ifw_effective_date` filtering at the DataSourcing layer.

**Evidence:** V1 output for any given date contains only rows where `ifw_effective_date` matches the execution date. Confirmed across 2024-10-01 and 2024-12-31.

---

## Business Rules

### BRD-CRT-003: Filter to Resolved Events
Only events with `status = 'Cleared'` and `review_date IS NOT NULL` are included in the output. These represent compliance events that were resolved (cleared with a known resolution date).

**Evidence:** V1 SQL `WHERE status = 'Cleared' AND review_date IS NOT NULL` in the `resolved` CTE.

### BRD-CRT-004: Days to Resolve Calculation
For each qualifying event, the resolution time is calculated as `julianday(review_date) - julianday(event_date)`, cast to INTEGER. This yields whole-number calendar days between event creation and resolution.

**Evidence:** V1 SQL `CAST(julianday(review_date) - julianday(event_date) AS INTEGER) AS days_to_resolve`.

### BRD-CRT-005: Aggregation by Event Type
Output is aggregated by `event_type`, producing one row per distinct event type with:
- `resolved_count`: count of resolved events
- `total_days`: sum of days_to_resolve across all resolved events of that type
- `avg_resolution_days`: integer division of total_days / resolved_count

**Evidence:** V1 SQL `GROUP BY resolved.event_type`. Output contains 5 rows corresponding to 5 distinct event types: AML_FLAG, ID_VERIFICATION, KYC_REVIEW, PEP_CHECK, SANCTIONS_SCREEN.

### BRD-CRT-006: Integer Division for Average
The average resolution days uses integer division: `CAST(SUM(days_to_resolve) AS INTEGER) / CAST(COUNT(*) AS INTEGER)`. This truncates rather than rounds, producing whole numbers that may differ from a floating-point average.

**Evidence:** V1 SQL performs `CAST(SUM(...) AS INTEGER) / CAST(COUNT(*) AS INTEGER)`. V1 output for AML_FLAG shows `avg_resolution_days = 17` (23920 / 1380 = 17.333... truncated to 17). This is intentional V1 behavior.

### BRD-CRT-007: ifw_effective_date from Source
The `ifw_effective_date` column in the output comes from the `compliance_events` table (injected by the framework at DataSourcing).

**Evidence:** V1 SQL accesses `compliance_events.ifw_effective_date` and groups by it. Every row for a given execution date shares the same `ifw_effective_date` value.

---

## Output Format

### BRD-CRT-008: File Format
Output is CSV with LF line endings, comma-delimited, no quoting (unless field contains comma).

**Evidence:** V1 job conf `CsvFileWriter` specifies `lineEnding: LF`, `includeHeader: true`. Binary inspection of V1 output confirms `\n` line endings.

### BRD-CRT-009: Header Row
Output includes a single header row as the first line.

**Evidence:** V1 job conf `includeHeader: true`. V1 output first line: `event_type,resolved_count,total_days,avg_resolution_days,ifw_effective_date,etl_effective_date`.

### BRD-CRT-010: Column Schema
Output contains 6 columns in this order: `event_type`, `resolved_count`, `total_days`, `avg_resolution_days`, `ifw_effective_date`, `etl_effective_date`.

**Evidence:** V1 output header and data rows. The first 5 are from the transformation SQL, `etl_effective_date` is appended automatically by the framework.

### BRD-CRT-011: Row Count
Output contains exactly 5 data rows (one per event type) plus 1 header and 1 trailer for every effective date.

**Evidence:** V1 output for 2024-10-01 and 2024-12-31 both contain 7 lines (1 header + 5 data + 1 trailer).

### BRD-CRT-012: Trailer Format
Output includes a trailer row in the format `TRAILER|{row_count}|{date}` where `row_count` is the number of data rows (5) and `date` is the effective date.

**Evidence:** V1 job conf `trailerFormat: "TRAILER|{row_count}|{date}"`. V1 output last line for 2024-10-01: `TRAILER|5|2024-10-01`.

### BRD-CRT-013: Output Path
Output path follows the pattern: `{outputDirectory}/compliance_resolution_time/compliance_resolution_time/{YYYY-MM-DD}/compliance_resolution_time.csv`.

**Evidence:** V1 job conf `CsvFileWriter` specifies `jobDirName: compliance_resolution_time`, `outputTableDirName: compliance_resolution_time`, `fileName: compliance_resolution_time.csv`.

### BRD-CRT-014: Write Mode
Output uses Overwrite mode -- each execution replaces any existing file for that date.

**Evidence:** V1 job conf `writeMode: Overwrite`.
