# CardAuthorizationSummary -- Functional Specification Document

**Job:** CardAuthorizationSummary_RE
**Traces to:** BRD (jobs/CardAuthorizationSummary/BRD.md)

---

## Data Sourcing

### FSD-CAUTH-001: Card Transactions Source Configuration
Source `datalake.card_transactions` with columns: `card_id`, `amount`, `authorization_status`.

**Traces to:** BRD-CAUTH-001, BRD-CAUTH-003
**Change from V1:** Removed `card_txn_id` and `customer_id` from sourced columns (AP4 remediation). V1 sourced 5 columns; RE sources 3. Neither column is referenced in the transformation SQL or output:
- `card_txn_id`: was only used in dead ROW_NUMBER ORDER BY clause (AP8 -- removed)
- `customer_id`: never referenced anywhere in the SQL

### FSD-CAUTH-002: Cards Source Configuration
Source `datalake.cards` with columns: `card_id`, `card_type`.

**Traces to:** BRD-CAUTH-002, BRD-CAUTH-003
**Change from V1:** Removed `customer_id` from sourced columns (AP4 remediation). V1 sourced 3 columns; RE sources 2. `customer_id` from cards is never referenced in the transformation SQL or output.

---

## Transformation

### FSD-CAUTH-003: SQL Transformation
Join card_transactions to cards on card_id, aggregate by card_type with transaction counts and integer division approval rate.

```sql
SELECT c.card_type,
  COUNT(*) AS total_count,
  SUM(CASE WHEN ct.authorization_status = 'Approved' THEN 1 ELSE 0 END) AS approved_count,
  SUM(CASE WHEN ct.authorization_status = 'Declined' THEN 1 ELSE 0 END) AS declined_count,
  CAST(SUM(CASE WHEN ct.authorization_status = 'Approved' THEN 1 ELSE 0 END) AS INTEGER) / CAST(COUNT(*) AS INTEGER) AS approval_rate,
  ct.ifw_effective_date
FROM card_transactions ct
INNER JOIN cards c ON ct.card_id = c.card_id
GROUP BY c.card_type, ct.ifw_effective_date
```

**Traces to:** BRD-CAUTH-004, BRD-CAUTH-005, BRD-CAUTH-006, BRD-CAUTH-007

**Changes from V1:**
- **AP4 remediation:** `card_txn_id` and `customer_id` removed from card_transactions DataSourcing; `customer_id` removed from cards DataSourcing. None referenced in transformation SQL.
- **AP8 remediation (ROW_NUMBER):** V1 SQL computed `ROW_NUMBER() OVER (PARTITION BY c.card_type ORDER BY ct.card_txn_id) AS rn` in the `txn_detail` CTE, but `rn` was never referenced in the outer SELECT or any WHERE clause. Removed entirely.
- **AP8 remediation (dead CTE):** V1 SQL defined `unused_summary AS (SELECT card_type, COUNT(*) AS cnt FROM txn_detail GROUP BY card_type)` -- a CTE that was literally never referenced by any downstream query. Pure dead code. Removed entirely.
- **AP7 preserved (integer division):** `CAST(... AS INTEGER) / CAST(... AS INTEGER)` is preserved exactly. This produces `approval_rate=0` for all rows on all dates because approved < total. This IS the V1 behavior and must not be changed.

**Output equivalence:** ROW_NUMBER removal has no effect (never filtered on). Dead CTE removal has no effect (never referenced). AP4 column removal is DataSourcing-only. Integer division preserved exactly. The SELECT column list and GROUP BY are identical to V1.

### FSD-CAUTH-004: No External Module Required
The job requires no C# External module. All logic is expressible in SQL.

**Traces to:** BRD-CAUTH-005

---

## Output

### FSD-CAUTH-005: CSV Writer Configuration
- `includeHeader: true` (BRD-CAUTH-009)
- `writeMode: Overwrite` (BRD-CAUTH-014)
- `lineEnding: LF` (BRD-CAUTH-008)
- `trailerFormat: "TRAILER|{row_count}|{date}"` (BRD-CAUTH-012)
- `outputDirectory: {ETL_RE_OUTPUT}` (BRD-CAUTH-013)
- `jobDirName: card_authorization_summary`
- `fileName: card_authorization_summary.csv`
- `outputTableDirName: card_authorization_summary`

**Traces to:** BRD-CAUTH-008 through BRD-CAUTH-014
**Change from V1:** `outputDirectory` changed from `Output/curated` to `{ETL_RE_OUTPUT}` to write to RE output tree instead of V1 output tree.

### FSD-CAUTH-006: Output Schema
7 columns: `card_type`, `total_count`, `approved_count`, `declined_count`, `approval_rate`, `ifw_effective_date`, `etl_effective_date`.

**Traces to:** BRD-CAUTH-010
**Change from V1:** None. Column list and order are identical. `etl_effective_date` is appended automatically by the framework.
