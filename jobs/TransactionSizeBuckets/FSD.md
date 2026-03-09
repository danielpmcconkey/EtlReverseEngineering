# TransactionSizeBuckets -- Functional Specification Document

**Job:** TransactionSizeBuckets_RE
**Traces to:** BRD (jobs/TransactionSizeBuckets/BRD.md)

---

## Data Sourcing

### FSD-TSB-001: Transactions Source Configuration
Source `datalake.transactions` with column: `amount`.

**Traces to:** BRD-TSB-001, BRD-TSB-003
**Change from V1:** AP4 remediation -- reduced from 4 columns (`transaction_id`, `account_id`, `txn_type`, `amount`) to 1 column (`amount`). Only `amount` is used in the final aggregation. The other 3 columns appeared in intermediate CTEs but contributed nothing to output.

### FSD-TSB-002: Accounts Source Removed (AP1 Remediation)
V1 sourced `datalake.accounts` but never referenced it in the SQL. The entire accounts DataSourcing module is removed in the RE job conf.

**Traces to:** BRD-TSB-002
**Change from V1:** Accounts DataSourcing module removed entirely. Zero impact on output.

---

## Transformation

### FSD-TSB-003: SQL Transformation
CASE-bucket transactions by amount, then aggregate per bucket.

```sql
WITH bucketed AS (
  SELECT t.amount, t.ifw_effective_date,
    CASE
      WHEN t.amount >= 0 AND t.amount < 25 THEN '0-25'
      WHEN t.amount >= 25 AND t.amount < 100 THEN '25-100'
      WHEN t.amount >= 100 AND t.amount < 500 THEN '100-500'
      WHEN t.amount >= 500 AND t.amount < 1000 THEN '500-1000'
      ELSE '1000+'
    END AS amount_bucket
  FROM transactions t
),
summary AS (
  SELECT b.amount_bucket, COUNT(*) AS txn_count,
         ROUND(SUM(b.amount), 2) AS total_amount,
         ROUND(AVG(b.amount), 2) AS avg_amount,
         b.ifw_effective_date
  FROM bucketed b
  GROUP BY b.amount_bucket, b.ifw_effective_date
)
SELECT s.amount_bucket, s.txn_count, s.total_amount, s.avg_amount, s.ifw_effective_date
FROM summary s
ORDER BY s.ifw_effective_date, s.amount_bucket
```

**Traces to:** BRD-TSB-004, BRD-TSB-005, BRD-TSB-008
**Change from V1:**
- AP8 remediation: Removed dead `txn_detail` CTE with `ROW_NUMBER() OVER (PARTITION BY t.account_id ORDER BY t.amount DESC) AS rn`. The `rn` column was never used for filtering or output. The `bucketed` CTE now selects directly from `transactions` instead of from `txn_detail`.
- AP4 remediation: Removed `transaction_id` and `account_id` from intermediate CTEs since they contributed nothing to the final output. Only `amount` and `ifw_effective_date` are needed.

**Output equivalence:** Byte-identical. The ROW_NUMBER was dead computation, and the removed columns were never used in GROUP BY or output.

### FSD-TSB-004: No External Module Required
The job requires no C# External module. All logic is expressible in SQL.

**Traces to:** BRD-TSB-004
**DELIV-05 note:** Satisfied trivially -- no external module exists in V1, none needed in RE.

---

## Output

### FSD-TSB-005: CSV Writer Configuration
- `includeHeader: true` (BRD-TSB-010)
- `writeMode: Overwrite` (BRD-TSB-015)
- `lineEnding: LF` (BRD-TSB-009)
- `outputDirectory: {ETL_RE_OUTPUT}` (BRD-TSB-014)
- `jobDirName: transaction_size_buckets`
- `fileName: transaction_size_buckets.csv`
- `outputTableDirName: transaction_size_buckets`

**Traces to:** BRD-TSB-009 through BRD-TSB-015
**Change from V1:** `outputDirectory` changed from `Output/curated` to `{ETL_RE_OUTPUT}` to write to RE output tree.

### FSD-TSB-006: Output Schema
6 columns: `amount_bucket`, `txn_count`, `total_amount`, `avg_amount`, `ifw_effective_date`, `etl_effective_date`.

**Traces to:** BRD-TSB-011
**Change from V1:** None. Column list and order are identical. `etl_effective_date` is appended automatically by the framework.
