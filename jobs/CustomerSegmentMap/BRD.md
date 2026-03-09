# CustomerSegmentMap -- Business Requirements Document

**Job:** CustomerSegmentMap
**Source V1 conf:** `/workspace/MockEtlFramework/JobExecutor/Jobs/customer_segment_map.json`
**Effective dates:** 2024-10-01 through 2024-12-31 (92 dates)
**Write mode:** Append (cumulative output)

---

## Data Sources

### BRD-CSM-001: Primary Source - Customer Segments
The job sources from `datalake.customers_segments` with 2 columns: `customer_id`, `segment_id`.

**Evidence:** V1 job conf `DataSourcing` module specifies schema `datalake`, table `customers_segments`.

### BRD-CSM-002: Lookup Source - Segments
The job sources from `datalake.segments` with 3 columns: `segment_id`, `segment_name`, `segment_code`.

**Evidence:** V1 job conf second `DataSourcing` module.

### BRD-CSM-003: Dead-End Source (AP1)
The V1 job conf also sources `datalake.branches` with 4 columns: `branch_id`, `branch_name`, `city`, `state_province`. However, the SQL transformation never references the `branches` result set. This is dead-end sourcing (AP1).

**Evidence:** V1 SQL: `SELECT cs.customer_id, cs.segment_id, s.segment_name, s.segment_code, cs.ifw_effective_date FROM customers_segments cs JOIN segments s ON cs.segment_id = s.segment_id AND cs.ifw_effective_date = s.ifw_effective_date ORDER BY cs.customer_id, cs.segment_id`. No reference to `branches` anywhere.

### BRD-CSM-004: Effective Date Scoping
Data is scoped to a single effective date per execution via standard framework injection.

**Evidence:** No min/max overrides in V1 DataSourcing.

---

## Business Rules

### BRD-CSM-005: Customer-Segment Mapping
The output maps each customer to their segment(s) by joining `customers_segments` with `segments` on `segment_id` and `ifw_effective_date`. A customer may appear in multiple rows if assigned to multiple segments.

**Evidence:** V1 SQL performs an INNER JOIN between `customers_segments cs` and `segments s` on both `segment_id` and `ifw_effective_date`.

### BRD-CSM-006: Output Ordering
Rows are ordered by `customer_id` ascending, then `segment_id` ascending.

**Evidence:** V1 SQL: `ORDER BY cs.customer_id, cs.segment_id`.

### BRD-CSM-007: Row Count Per Execution
Each execution produces 2982 data rows.

**Evidence:** V1 output for 2024-10-01 has 2982 data rows (2983 lines with header). Dec 31 has 274344 data rows (2982 * 92 cumulative).

---

## Output Format

### BRD-CSM-008: File Format
Output is CSV with LF line endings, comma-delimited, no quoting.

**Evidence:** V1 job conf `CsvFileWriter` specifies `lineEnding: LF`, `includeHeader: true`.

### BRD-CSM-009: Header Row
Output header: `customer_id,segment_id,segment_name,segment_code,ifw_effective_date,etl_effective_date`.

**Evidence:** V1 output first line confirmed.

### BRD-CSM-010: Column Schema
Output contains 6 columns: `customer_id`, `segment_id`, `segment_name`, `segment_code`, `ifw_effective_date`, `etl_effective_date`.

**Evidence:** V1 output header. First 4 are from SQL JOIN, `ifw_effective_date` from SELECT, `etl_effective_date` is framework auto-append.

### BRD-CSM-011: Cumulative Row Count (Append Mode)
Row count grows cumulatively: 2982 on date 1, 5964 on date 2, ..., 274344 on date 92.

**Evidence:** V1 output: Oct 1 = 2983 lines, Dec 31 = 274345 lines.

### BRD-CSM-012: No Trailer
No trailer row.

**Evidence:** No trailer configuration in V1 job conf.

### BRD-CSM-013: Output Path
Output path: `{outputDirectory}/customer_segment_map/customer_segment_map/{YYYY-MM-DD}/customer_segment_map.csv`.

**Evidence:** V1 job conf `CsvFileWriter` specifies matching directory/file names.

### BRD-CSM-014: Write Mode
Output uses Append mode.

**Evidence:** V1 job conf `writeMode: Append`.
