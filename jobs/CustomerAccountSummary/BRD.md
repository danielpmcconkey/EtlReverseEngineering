# CustomerAccountSummary -- Business Requirements Document

**Job:** CustomerAccountSummary
**Source V1 conf:** `/workspace/MockEtlFramework/JobExecutor/Jobs/customer_account_summary.json`
**Effective dates:** 2024-10-01 through 2024-12-31 (92 dates)

---

## Data Sources

### BRD-CAS-001: Primary Source -- Customers
The job sources from `datalake.customers` with 3 columns: `id`, `first_name`, `last_name`.

**Evidence:** V1 job conf first `DataSourcing` module specifies schema `datalake`, table `customers`, with these exact 3 columns.

### BRD-CAS-002: Secondary Source -- Accounts
The job sources from `datalake.accounts` with 5 columns: `account_id`, `customer_id`, `account_type`, `account_status`, `current_balance`.

**Evidence:** V1 job conf second `DataSourcing` module specifies schema `datalake`, table `accounts`, with these exact 5 columns.

### BRD-CAS-003: Effective Date Scoping
Data from both sources is scoped to a single effective date per execution. The framework injects `ifw_effective_date` filtering at the DataSourcing layer.

**Evidence:** V1 output for any given date contains only rows matching that execution date.

---

## Business Rules

### BRD-CAS-004: Customer-Account Join
Each customer is LEFT JOINed to their accounts on `customers.id = accounts.customer_id`. Customers without accounts are retained with zero counts/balances.

**Evidence:** V1 SQL uses `LEFT JOIN accounts a ON c.id = a.customer_id`. Output shows customers with `account_count = 0` and `active_balance = 0.00`.

### BRD-CAS-005: Aggregation per Customer
Results are grouped by customer (`id`, `first_name`, `last_name`), producing one row per customer with:
- `account_count`: COUNT of all accounts (active and inactive)
- `active_balance`: SUM of `current_balance` for accounts where `account_status = 'Active'`, rounded to 2 decimal places. Inactive accounts contribute 0.

**Evidence:** V1 SQL: `COUNT(a.account_id) AS account_count, ROUND(SUM(CASE WHEN a.account_status = 'Active' THEN a.current_balance ELSE 0 END), 2) AS active_balance`.

### BRD-CAS-006: Output Ordering
Rows are ordered ascending by `customer_id` (aliased from `c.id`).

**Evidence:** V1 SQL includes `ORDER BY c.id`. V1 output confirms ascending order.

---

## Output Format

### BRD-CAS-007: File Format
Output is CSV with LF line endings, comma-delimited.

**Evidence:** V1 job conf `CsvFileWriter` specifies `lineEnding: LF`, `includeHeader: true`.

### BRD-CAS-008: Header Row
Output includes a single header row as the first line.

**Evidence:** V1 job conf `includeHeader: true`. V1 output first line: `customer_id,first_name,last_name,account_count,active_balance,etl_effective_date`.

### BRD-CAS-009: Column Schema
Output contains 6 columns in this order: `customer_id`, `first_name`, `last_name`, `account_count`, `active_balance`, `etl_effective_date`.

**Evidence:** V1 output header. The first 5 are from the SQL transformation, `etl_effective_date` is appended automatically by the framework.

### BRD-CAS-010: Row Count
Output contains exactly 2230 data rows (plus 1 header) for every effective date in the range.

**Evidence:** `wc -l` on V1 output for 2024-10-01 returns 2231 lines.

### BRD-CAS-011: No Trailer
Output has no trailer row.

**Evidence:** V1 output last line is a data row. V1 job conf has no trailer configuration.

### BRD-CAS-012: Output Path
Output path follows the pattern: `{outputDirectory}/customer_account_summary/customer_account_summary/{YYYY-MM-DD}/customer_account_summary.csv`.

**Evidence:** V1 job conf `CsvFileWriter` specifies `jobDirName: customer_account_summary`, `outputTableDirName: customer_account_summary`, `fileName: customer_account_summary.csv`.

### BRD-CAS-013: Write Mode
Output uses Overwrite mode -- each execution replaces any existing file for that date.

**Evidence:** V1 job conf `writeMode: Overwrite`.

---

## Notes

### BRD-CAS-014: External Module Not Used
An external module `CustomerAccountSummaryBuilder.cs` exists in `/workspace/MockEtlFramework/ExternalModules/` but is NOT referenced by the V1 job conf. The V1 job uses a SQL Transformation module instead. The external module is ignored for RE purposes.

**Evidence:** V1 job conf modules list contains only `DataSourcing`, `Transformation`, and `CsvFileWriter` types. No `External` module type present.
