# CardAuthorizationSummary -- Business Requirements Document

**Job:** CardAuthorizationSummary
**Source V1 conf:** `/workspace/MockEtlFramework/JobExecutor/Jobs/card_authorization_summary.json`
**Effective dates:** 2024-10-01 through 2024-12-31 (92 dates)

---

## Data Sources

### BRD-CAUTH-001: Card Transactions Source
The job sources from `datalake.card_transactions` with 5 columns: `card_txn_id`, `card_id`, `customer_id`, `amount`, `authorization_status`.

**Evidence:** V1 job conf first `DataSourcing` module specifies schema `datalake`, table `card_transactions`, with these exact 5 columns.

### BRD-CAUTH-002: Cards Source
The job sources from `datalake.cards` with 3 columns: `card_id`, `customer_id`, `card_type`.

**Evidence:** V1 job conf second `DataSourcing` module specifies schema `datalake`, table `cards`, with these exact 3 columns.

### BRD-CAUTH-003: Effective Date Scoping
Data is scoped to a single effective date per execution. The framework injects `ifw_effective_date` filtering at the DataSourcing layer for both sources.

**Evidence:** V1 output for any given date contains only rows where `ifw_effective_date` matches the execution date. Confirmed across 2024-10-01 and 2024-12-31.

### BRD-CAUTH-004: Join Relationship
Card transactions are joined to cards on `card_id` to obtain `card_type` for aggregation. This is an INNER JOIN -- only transactions with a matching card record appear in output.

**Evidence:** V1 SQL `INNER JOIN cards c ON ct.card_id = c.card_id`.

---

## Business Rules

### BRD-CAUTH-005: Aggregation by Card Type
Output is aggregated by `card_type`, producing one row per distinct card type with:
- `total_count`: count of all transactions of that type
- `approved_count`: count of transactions with `authorization_status = 'Approved'`
- `declined_count`: count of transactions with `authorization_status = 'Declined'`
- `approval_rate`: integer division of approved_count / total_count

**Evidence:** V1 SQL `GROUP BY td.card_type, td.ifw_effective_date`. Output contains 2 data rows (Credit and Debit) for every effective date.

### BRD-CAUTH-006: Approval Rate -- Integer Division (AP7 Load-Bearing)
The `approval_rate` is calculated as `CAST(approved_count AS INTEGER) / CAST(total_count AS INTEGER)`. In SQLite, integer division truncates toward zero. Since approved_count < total_count for all dates, this always produces 0.

**THIS IS LOAD-BEARING.** The V1 output shows `approval_rate=0` for every row on every date. This is not a bug to fix -- it IS the V1 behavior.

**Evidence:** V1 SQL `CAST(SUM(CASE WHEN td.authorization_status = 'Approved' THEN 1 ELSE 0 END) AS INTEGER) / CAST(COUNT(*) AS INTEGER) AS approval_rate`. V1 output for 2024-10-01: Credit shows 501/535 = 0, Debit shows 909/949 = 0. V1 output for 2024-12-31: Credit shows 505/527 = 0, Debit shows 1024/1077 = 0.

### BRD-CAUTH-007: ifw_effective_date from Source
The `ifw_effective_date` column in the output comes from `card_transactions` via the `txn_detail` CTE (injected by the framework at DataSourcing).

**Evidence:** V1 SQL accesses `ct.ifw_effective_date` and groups by it. Every row for a given execution date shares the same `ifw_effective_date` value.

---

## Output Format

### BRD-CAUTH-008: File Format
Output is CSV with LF line endings, comma-delimited, no quoting (unless field contains comma).

**Evidence:** V1 job conf `CsvFileWriter` specifies `lineEnding: LF`, `includeHeader: true`. Binary inspection of V1 output confirms `\n` line endings.

### BRD-CAUTH-009: Header Row
Output includes a single header row as the first line.

**Evidence:** V1 job conf `includeHeader: true`. V1 output first line: `card_type,total_count,approved_count,declined_count,approval_rate,ifw_effective_date,etl_effective_date`.

### BRD-CAUTH-010: Column Schema
Output contains 7 columns in this order: `card_type`, `total_count`, `approved_count`, `declined_count`, `approval_rate`, `ifw_effective_date`, `etl_effective_date`.

**Evidence:** V1 output header and data rows. The first 6 are from the transformation SQL, `etl_effective_date` is appended automatically by the framework.

### BRD-CAUTH-011: Row Count
Output contains exactly 2 data rows (one per card type: Credit, Debit) plus 1 header and 1 trailer for every effective date.

**Evidence:** V1 output for 2024-10-01 and 2024-12-31 both contain 4 lines (1 header + 2 data + 1 trailer).

### BRD-CAUTH-012: Trailer Format
Output includes a trailer row in the format `TRAILER|{row_count}|{date}` where `row_count` is the number of data rows (always 2) and `date` is the effective date.

**Evidence:** V1 job conf `trailerFormat: "TRAILER|{row_count}|{date}"`. V1 output last line for 2024-10-01: `TRAILER|2|2024-10-01`. This trailer is DETERMINISTIC -- no runtime timestamps.

### BRD-CAUTH-013: Output Path
Output path follows the pattern: `{outputDirectory}/card_authorization_summary/card_authorization_summary/{YYYY-MM-DD}/card_authorization_summary.csv`.

**Evidence:** V1 job conf `CsvFileWriter` specifies `jobDirName: card_authorization_summary`, `outputTableDirName: card_authorization_summary`, `fileName: card_authorization_summary.csv`.

### BRD-CAUTH-014: Write Mode
Output uses Overwrite mode -- each execution replaces any existing file for that date.

**Evidence:** V1 job conf `writeMode: Overwrite`.
