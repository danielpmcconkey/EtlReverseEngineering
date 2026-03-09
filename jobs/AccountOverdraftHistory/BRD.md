# AccountOverdraftHistory — Business Requirements Document

**Job:** AccountOverdraftHistory
**Source V1 conf:** `/workspace/MockEtlFramework/JobExecutor/Jobs/account_overdraft_history.json`
**Effective dates:** 2024-10-01 through 2024-12-31 (92 dates)

---

## Data Sources

### BRD-AOH-001: Overdraft Events Source
The job sources from `datalake.overdraft_events` with 7 columns: `overdraft_id`, `account_id`, `customer_id`, `overdraft_amount`, `fee_amount`, `fee_waived`, `event_timestamp`.

**Evidence:** V1 job conf `DataSourcing` module specifies schema `datalake`, table `overdraft_events`, with these exact 7 columns.

### BRD-AOH-002: Accounts Source
The job sources from `datalake.accounts` with 6 columns: `account_id`, `customer_id`, `account_type`, `account_status`, `interest_rate`, `credit_limit`.

**Evidence:** V1 job conf second `DataSourcing` module specifies schema `datalake`, table `accounts`, with these exact 6 columns.

### BRD-AOH-003: Effective Date Scoping
Data is scoped to a single effective date per execution. The framework injects `ifw_effective_date` filtering at the DataSourcing layer for both sources.

**Evidence:** V1 output for any given date contains only rows where `ifw_effective_date` matches the execution date.

---

## Business Rules

### BRD-AOH-004: Account Type Enrichment
Each overdraft event is enriched with the `account_type` from the accounts table by joining on `account_id` and `ifw_effective_date`.

**Evidence:** V1 SQL: `JOIN accounts a ON oe.account_id = a.account_id AND oe.ifw_effective_date = a.ifw_effective_date`. The `account_type` column appears in the SELECT list sourced from `a.account_type`.

### BRD-AOH-005: Inner Join Semantics
Only overdraft events with a matching account record (same account_id and effective date) are included in output. Events without a matching account are excluded.

**Evidence:** V1 SQL uses `JOIN` (inner), not `LEFT JOIN`. An overdraft event with no matching account for that date would be dropped.

### BRD-AOH-006: Output Ordering
Rows are ordered by `ifw_effective_date` ascending, then `overdraft_id` ascending.

**Evidence:** V1 SQL: `ORDER BY oe.ifw_effective_date, oe.overdraft_id`.

---

## Output Format

### BRD-AOH-007: File Format
Output is Parquet format with 50 partitions (parts).

**Evidence:** V1 job conf uses `ParquetFileWriter` with `numParts: 50`.

### BRD-AOH-008: Column Schema
Output contains 9 columns in this order: `overdraft_id`, `account_id`, `customer_id`, `account_type`, `overdraft_amount`, `fee_amount`, `fee_waived`, `ifw_effective_date`, `etl_effective_date`.

**Evidence:** V1 SQL SELECT list. `etl_effective_date` is appended automatically by the framework.

### BRD-AOH-009: Row Count
Output contains 2-3 data rows per effective date (varies by date).

**Evidence:** V1 output inspection across multiple dates shows variable row counts in the 2-3 range.

### BRD-AOH-010: Output Path
Output path follows the pattern: `{outputDirectory}/account_overdraft_history/account_overdraft_history/{YYYY-MM-DD}/account_overdraft_history/` (directory containing `part-*.parquet` files).

**Evidence:** V1 job conf `ParquetFileWriter` specifies `jobDirName: account_overdraft_history`, `outputTableDirName: account_overdraft_history`, `fileName: account_overdraft_history`.

### BRD-AOH-011: Write Mode
Output uses Overwrite mode -- each execution replaces any existing output for that date.

**Evidence:** V1 job conf `writeMode: Overwrite`.
