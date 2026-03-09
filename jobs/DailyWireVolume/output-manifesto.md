# DailyWireVolume -- Output Manifesto

**Job:** DailyWireVolume_RE

---

## Outputs

### daily_wire_volume.csv

| Property | Value |
|----------|-------|
| Path | `{ETL_RE_OUTPUT}/daily_wire_volume/daily_wire_volume/{YYYY-MM-DD}/daily_wire_volume.csv` |
| Format | CSV |
| Delimiter | Comma |
| Line ending | LF |
| Header | Yes (1 row) |
| Trailer | No |
| Data rows (Oct 1) | 92 |
| Data rows (Dec 31) | 8464 (cumulative) |
| Write mode | Append |

### Column Schema

| Position | Column | Type | Source |
|----------|--------|------|--------|
| 1 | wire_date | date | SQL alias of ifw_effective_date |
| 2 | wire_count | integer | COUNT(*) of wire_transfers |
| 3 | total_amount | numeric | ROUND(SUM(amount), 2) |
| 4 | ifw_effective_date | date | GROUP BY column |
| 5 | etl_effective_date | date | Framework auto-append |

### Sample Row (from Oct 1 output)
```
2024-10-01,40,1065142,2024-10-01,2024-10-01
```
