# TransactionSizeBuckets -- Business Requirements Document

**Job:** TransactionSizeBuckets
**Source V1 conf:** `/workspace/MockEtlFramework/JobExecutor/Jobs/transaction_size_buckets.json`
**Effective dates:** 2024-10-01 through 2024-12-31 (92 dates)

---

## Data Sources

### BRD-TSB-001: Primary Source -- Transactions
The job sources from `datalake.transactions` with 4 columns: `transaction_id`, `account_id`, `txn_type`, `amount`.

**Evidence:** V1 job conf first `DataSourcing` module specifies schema `datalake`, table `transactions`, with these exact 4 columns.

### BRD-TSB-002: Dead Source -- Accounts (AP1)
The V1 job conf sources from `datalake.accounts` with 3 columns: `account_id`, `customer_id`, `account_type`. However, this source is NEVER referenced in the transformation SQL. No column or alias from `accounts` appears in any SELECT, JOIN, WHERE, or GROUP BY clause.

**Evidence:** V1 SQL references only `transactions t` -- no reference to `accounts` or any alias thereof. This is anti-pattern AP1 (Dead-End Sourcing).

### BRD-TSB-003: Effective Date Scoping
Data is scoped to a single effective date per execution. The framework injects `ifw_effective_date` filtering at the DataSourcing layer.

**Evidence:** V1 output for any given date contains only rows where `ifw_effective_date` matches the execution date.

---

## Business Rules

### BRD-TSB-004: Amount Bucketing
Each transaction is classified into one of 5 amount buckets based on the `amount` field:
- `0-25`: amount >= 0 AND amount < 25
- `25-100`: amount >= 25 AND amount < 100
- `100-500`: amount >= 100 AND amount < 500
- `500-1000`: amount >= 500 AND amount < 1000
- `1000+`: amount >= 1000 (or any amount not matching above ranges)

**Evidence:** V1 SQL CASE statement defines these exact 5 buckets with these boundary conditions.

### BRD-TSB-005: Aggregation per Bucket
Results are grouped by `amount_bucket` and `ifw_effective_date`, producing one row per bucket per date with:
- `txn_count`: COUNT of all transactions in the bucket
- `total_amount`: SUM of `amount` for all transactions in the bucket, rounded to 2 decimal places
- `avg_amount`: AVG of `amount` for all transactions in the bucket, rounded to 2 decimal places

**Evidence:** V1 SQL: `COUNT(*) AS txn_count, ROUND(SUM(b.amount), 2) AS total_amount, ROUND(AVG(b.amount), 2) AS avg_amount`.

### BRD-TSB-006: Dead ROW_NUMBER (AP8)
V1 SQL computes a `ROW_NUMBER() OVER (PARTITION BY t.account_id ORDER BY t.amount DESC) AS rn` in the `txn_detail` CTE. This value is never used in any subsequent WHERE, SELECT, GROUP BY, or ORDER BY clause. It is dead computation.

**Evidence:** The `rn` column from `txn_detail` is not referenced in the `bucketed` or `summary` CTEs, nor in the final SELECT.

### BRD-TSB-007: Unused Source Columns (AP4)
From `transactions`: `transaction_id`, `account_id`, and `txn_type` are sourced but only `amount` (and framework-injected `ifw_effective_date`) is used in the final aggregation. `transaction_id` and `account_id` appear in intermediate CTEs but contribute nothing to the final output.

**Evidence:** The `bucketed` CTE selects `transaction_id`, `account_id`, and `amount` from `txn_detail`, but the `summary` CTE only uses `amount_bucket`, `amount`, and `ifw_effective_date`.

### BRD-TSB-008: Output Ordering
Rows are ordered by `ifw_effective_date` ascending, then `amount_bucket` ascending (alphabetical).

**Evidence:** V1 SQL includes `ORDER BY s.ifw_effective_date, s.amount_bucket`. V1 output confirms this order.

---

## Output Format

### BRD-TSB-009: File Format
Output is CSV with LF line endings, comma-delimited.

**Evidence:** V1 job conf `CsvFileWriter` specifies `lineEnding: LF`, `includeHeader: true`.

### BRD-TSB-010: Header Row
Output includes a single header row as the first line.

**Evidence:** V1 job conf `includeHeader: true`. V1 output first line: `amount_bucket,txn_count,total_amount,avg_amount,ifw_effective_date,etl_effective_date`.

### BRD-TSB-011: Column Schema
Output contains 6 columns in this order: `amount_bucket`, `txn_count`, `total_amount`, `avg_amount`, `ifw_effective_date`, `etl_effective_date`.

**Evidence:** V1 output header. The first 5 are from the SQL transformation, `etl_effective_date` is appended automatically by the framework.

### BRD-TSB-012: Row Count
Output contains exactly 5 data rows (plus 1 header) for every effective date in the range, one per amount bucket.

**Evidence:** `wc -l` on V1 output for 2024-10-01 returns 6 lines.

### BRD-TSB-013: No Trailer
Output has no trailer row.

**Evidence:** V1 output last line is a data row. V1 job conf has no trailer configuration.

### BRD-TSB-014: Output Path
Output path follows the pattern: `{outputDirectory}/transaction_size_buckets/transaction_size_buckets/{YYYY-MM-DD}/transaction_size_buckets.csv`.

**Evidence:** V1 job conf `CsvFileWriter` specifies `jobDirName: transaction_size_buckets`, `outputTableDirName: transaction_size_buckets`, `fileName: transaction_size_buckets.csv`.

### BRD-TSB-015: Write Mode
Output uses Overwrite mode -- each execution replaces any existing file for that date.

**Evidence:** V1 job conf `writeMode: Overwrite`.
