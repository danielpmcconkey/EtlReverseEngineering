# SecuritiesDirectory -- Business Requirements Document

**Job:** SecuritiesDirectory
**Source V1 conf:** `/workspace/MockEtlFramework/JobExecutor/Jobs/securities_directory.json`
**Effective dates:** 2024-10-01 through 2024-12-31 (92 dates)

---

## Data Sources

### BRD-SD-001: Primary Source -- Securities
The job sources from `datalake.securities` with 6 columns: `security_id`, `ticker`, `security_name`, `security_type`, `sector`, `exchange`.

**Evidence:** V1 job conf first `DataSourcing` module specifies schema `datalake`, table `securities`, with these exact 6 columns.

### BRD-SD-002: Dead Source -- Holdings (AP1)
The V1 job conf sources from `datalake.holdings` with 6 columns: `holding_id`, `investment_id`, `security_id`, `customer_id`, `quantity`, `current_value`. However, this source is NEVER referenced in the transformation SQL. No column or alias from `holdings` appears in any SELECT, JOIN, WHERE, or GROUP BY clause.

**Evidence:** V1 SQL references only `securities s` -- no reference to `holdings` or any alias thereof. This is anti-pattern AP1 (Dead-End Sourcing).

### BRD-SD-003: Effective Date Scoping
Data is scoped to a single effective date per execution. The framework injects `ifw_effective_date` filtering at the DataSourcing layer.

**Evidence:** V1 output for any given date contains only rows where `ifw_effective_date` matches the execution date.

---

## Business Rules

### BRD-SD-004: Simple Directory Listing
The output is a direct listing of all securities, with no aggregation, filtering, or joining. All rows from the securities source are passed through.

**Evidence:** V1 SQL: `SELECT s.security_id, s.ticker, s.security_name, s.security_type, s.sector, s.exchange, s.ifw_effective_date FROM securities s ORDER BY s.security_id`.

### BRD-SD-005: Output Ordering
Rows are ordered ascending by `security_id`.

**Evidence:** V1 SQL includes `ORDER BY s.security_id`. V1 output confirms ascending order (security_id 1 through 50).

---

## Output Format

### BRD-SD-006: File Format
Output is CSV with LF line endings, comma-delimited.

**Evidence:** V1 job conf `CsvFileWriter` specifies `lineEnding: LF`, `includeHeader: true`.

### BRD-SD-007: Header Row
Output includes a single header row as the first line.

**Evidence:** V1 job conf `includeHeader: true`. V1 output first line: `security_id,ticker,security_name,security_type,sector,exchange,ifw_effective_date,etl_effective_date`.

### BRD-SD-008: Column Schema
Output contains 8 columns in this order: `security_id`, `ticker`, `security_name`, `security_type`, `sector`, `exchange`, `ifw_effective_date`, `etl_effective_date`.

**Evidence:** V1 output header. The first 7 are from the SQL transformation, `etl_effective_date` is appended automatically by the framework.

### BRD-SD-009: Row Count
Output contains exactly 50 data rows (plus 1 header) for every effective date in the range.

**Evidence:** `wc -l` on V1 output for 2024-10-01 returns 51 lines.

### BRD-SD-010: No Trailer
Output has no trailer row.

**Evidence:** V1 output last line is a data row for security_id 50. V1 job conf has no trailer configuration.

### BRD-SD-011: Output Path
Output path follows the pattern: `{outputDirectory}/securities_directory/securities_directory/{YYYY-MM-DD}/securities_directory.csv`.

**Evidence:** V1 job conf `CsvFileWriter` specifies `jobDirName: securities_directory`, `outputTableDirName: securities_directory`, `fileName: securities_directory.csv`.

### BRD-SD-012: Write Mode
Output uses Overwrite mode -- each execution replaces any existing file for that date.

**Evidence:** V1 job conf `writeMode: Overwrite`.
