# FeeWaiverAnalysis -- Output Manifesto

**Job:** FeeWaiverAnalysis_RE

---

## Outputs

### fee_waiver_analysis.csv

| Property | Value |
|----------|-------|
| Path | `{ETL_RE_OUTPUT}/fee_waiver_analysis/fee_waiver_analysis/{YYYY-MM-DD}/fee_waiver_analysis.csv` |
| Format | CSV |
| Delimiter | Comma |
| Line ending | LF |
| Header | Yes (1 row) |
| Trailer | None |
| Data rows | 1-2 per date (one per fee_waived value) |
| Write mode | Overwrite |

### Column Schema

| Position | Column | Type | Source |
|----------|--------|------|--------|
| 1 | fee_waived | boolean (rendered as 0/1) | datalake.overdraft_events (aggregation key) |
| 2 | event_count | integer | COUNT(*) per group |
| 3 | total_fees | numeric(2dp) | ROUND(SUM(CASE WHEN fee_amount IS NULL THEN 0.0 ELSE fee_amount END), 2) |
| 4 | avg_fee | numeric(2dp) | ROUND(AVG(CASE WHEN fee_amount IS NULL THEN 0.0 ELSE fee_amount END), 2) |
| 5 | ifw_effective_date | date | Framework injection |
| 6 | etl_effective_date | date | Framework auto-append |

### Sample Row
```
0,1,35,35,2024-10-01,2024-10-01
```
