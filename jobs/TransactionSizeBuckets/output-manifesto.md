# TransactionSizeBuckets -- Output Manifesto

**Job:** TransactionSizeBuckets_RE

---

## Outputs

### transaction_size_buckets.csv

| Property | Value |
|----------|-------|
| Path | `{ETL_RE_OUTPUT}/transaction_size_buckets/transaction_size_buckets/{YYYY-MM-DD}/transaction_size_buckets.csv` |
| Format | CSV |
| Delimiter | Comma |
| Line ending | LF |
| Header | Yes (1 row) |
| Trailer | No |
| Data rows | 5 per date |
| Write mode | Overwrite |

### Column Schema

| Position | Column | Type | Source |
|----------|--------|------|--------|
| 1 | amount_bucket | text | CASE bucketing on amount |
| 2 | txn_count | integer | COUNT(*) per bucket |
| 3 | total_amount | numeric(2) | ROUND(SUM(amount), 2) |
| 4 | avg_amount | numeric(2) | ROUND(AVG(amount), 2) |
| 5 | ifw_effective_date | date | Framework injection |
| 6 | etl_effective_date | date | Framework auto-append |

### Sample Row
```
0-25,1523,15234.56,10.0,2024-10-01,2024-10-01
```
