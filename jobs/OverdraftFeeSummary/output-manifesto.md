# OverdraftFeeSummary -- Output Manifesto

**Job:** OverdraftFeeSummary_RE

---

## Outputs

### overdraft_fee_summary.csv

| Property | Value |
|----------|-------|
| Path | `{ETL_RE_OUTPUT}/overdraft_fee_summary/overdraft_fee_summary/{YYYY-MM-DD}/overdraft_fee_summary.csv` |
| Format | CSV |
| Delimiter | Comma |
| Line ending | LF |
| Header | Yes (1 row) |
| Trailer | None |
| Data rows | 2 per date (one per fee_waived value) |
| Write mode | Overwrite |

### Column Schema

| Position | Column | Type | Source |
|----------|--------|------|--------|
| 1 | fee_waived | boolean (rendered as 0/1) | datalake.overdraft_events (aggregation key) |
| 2 | total_fees | numeric(2dp) | ROUND(SUM(fee_amount), 2) per group |
| 3 | event_count | integer | COUNT(*) per group |
| 4 | avg_fee | numeric(2dp) | ROUND(AVG(fee_amount), 2) per group |
| 5 | ifw_effective_date | date | Framework injection |
| 6 | etl_effective_date | date | Framework auto-append |

### Sample Row
```
0,35,1,35,2024-10-01,2024-10-01
```
