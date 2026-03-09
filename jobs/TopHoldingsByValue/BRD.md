# TopHoldingsByValue -- Business Requirements Document

**Job:** TopHoldingsByValue
**Source V1 conf:** `/workspace/MockEtlFramework/JobExecutor/Jobs/top_holdings_by_value.json`
**Effective dates:** 2024-10-01 through 2024-12-31 (92 dates)

---

## Data Sources

### BRD-THV-001: Holdings Source Table
The job sources from `datalake.holdings` with 6 columns: `holding_id`, `investment_id`, `security_id`, `customer_id`, `quantity`, `current_value`.

**Evidence:** V1 job conf first `DataSourcing` module specifies schema `datalake`, table `holdings`, with these exact 6 columns.

### BRD-THV-002: Securities Source Table
The job sources from `datalake.securities` with 5 columns: `security_id`, `ticker`, `security_name`, `security_type`, `sector`.

**Evidence:** V1 job conf second `DataSourcing` module specifies schema `datalake`, table `securities`, with these exact 5 columns.

### BRD-THV-003: Effective Date Scoping
Both data sources are scoped to a single effective date per execution. The framework injects `ifw_effective_date` filtering at the DataSourcing layer.

**Evidence:** V1 output for any given date contains only rows where `ifw_effective_date` matches the execution date.

---

## Business Rules

### BRD-THV-004: Security Value Aggregation
Holdings are aggregated by `security_id` per effective date, computing:
- `total_held_value`: SUM of `current_value` across all holders
- `holder_count`: COUNT of holdings for that security

**Evidence:** V1 SQL `security_totals` CTE: `SELECT h.security_id, SUM(h.current_value) AS total_held_value, COUNT(*) AS holder_count, h.ifw_effective_date FROM holdings h GROUP BY h.security_id, h.ifw_effective_date`.

### BRD-THV-005: Securities Join
Aggregated holdings are joined to securities to enrich with `ticker`, `security_name`, and `sector`. Join is on `security_id` AND `ifw_effective_date`.

**Evidence:** V1 SQL `ranked` CTE: `JOIN securities s ON st.security_id = s.security_id AND st.ifw_effective_date = s.ifw_effective_date`.

### BRD-THV-006: Ranking by Value
Securities are ranked by `total_held_value` descending using `ROW_NUMBER()`. This produces a unique integer rank per security per date.

**Evidence:** V1 SQL: `ROW_NUMBER() OVER (ORDER BY st.total_held_value DESC) AS rank`.

### BRD-THV-007: Rank Bucketing
The integer rank is converted to string buckets via CASE:
- Rank 1-5: `'Top 5'`
- Rank 6-10: `'Top 10'`
- Rank 11-20: `'Top 20'`

The output `rank` column contains these CASE strings, NOT the ROW_NUMBER integer.

**Evidence:** V1 SQL outer SELECT: `CASE WHEN r.rank <= 5 THEN 'Top 5' WHEN r.rank <= 10 THEN 'Top 10' WHEN r.rank <= 20 THEN 'Top 20' ELSE 'Other' END AS rank`.

### BRD-THV-008: Top 20 Filter
Only securities with rank <= 20 are included in the output. The `'Other'` bucket from BRD-THV-007 is never reached because of this WHERE filter.

**Evidence:** V1 SQL: `WHERE r.rank <= 20`. Output contains exactly 20 rows per date.

### BRD-THV-009: Output Ordering
Rows are ordered by rank ascending (integer rank from ROW_NUMBER, applied before CASE bucketing).

**Evidence:** V1 SQL: `ORDER BY r.rank`.

---

## Output Format

### BRD-THV-010: File Format
Output is Parquet format with 50 part files per date directory.

**Evidence:** V1 job conf `ParquetFileWriter` with `numParts: 50`.

### BRD-THV-011: Column Schema
Output contains 9 columns: `security_id`, `ticker`, `security_name`, `sector`, `total_held_value`, `holder_count`, `rank`, `ifw_effective_date`, `etl_effective_date`.

**Evidence:** V1 SQL SELECT clause produces 8 columns. The framework auto-appends `etl_effective_date`. The `rank` column is the CASE string, not the integer.

### BRD-THV-012: Row Count
Output contains exactly 20 data rows per date (top 20 securities by held value).

**Evidence:** V1 output inspection. WHERE clause guarantees exactly 20 (assuming >= 20 securities exist, which is true in this dataset).

### BRD-THV-013: Output Path
Output path follows the pattern: `{outputDirectory}/top_holdings_by_value/top_holdings_by_value/{YYYY-MM-DD}/top_holdings_by_value/part-*.parquet`.

**Evidence:** V1 job conf `ParquetFileWriter` specifies `jobDirName: top_holdings_by_value`, `outputTableDirName: top_holdings_by_value`, `fileName: top_holdings_by_value`.

### BRD-THV-014: Write Mode
Output uses Overwrite mode -- each execution replaces any existing directory for that date.

**Evidence:** V1 job conf `writeMode: Overwrite`.

### BRD-THV-015: Part File Count
Exactly 50 part files per date directory, matching V1 configuration.

**Evidence:** V1 conf `numParts: 50`. V1 output directory listing confirms 50 part files.
