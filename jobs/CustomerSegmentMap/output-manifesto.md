# CustomerSegmentMap -- Output Manifesto

**Job:** CustomerSegmentMap_RE

---

## Outputs

### customer_segment_map.csv

| Property | Value |
|----------|-------|
| Path | `{ETL_RE_OUTPUT}/customer_segment_map/customer_segment_map/{YYYY-MM-DD}/customer_segment_map.csv` |
| Format | CSV |
| Delimiter | Comma |
| Line ending | LF |
| Header | Yes (1 row) |
| Trailer | No |
| Data rows (Oct 1) | 2982 |
| Data rows (Dec 31) | 274344 (cumulative) |
| Write mode | Append |

### Column Schema

| Position | Column | Type | Source |
|----------|--------|------|--------|
| 1 | customer_id | integer | datalake.customers_segments |
| 2 | segment_id | integer | datalake.customers_segments / datalake.segments (JOIN key) |
| 3 | segment_name | text | datalake.segments |
| 4 | segment_code | text | datalake.segments |
| 5 | ifw_effective_date | date | Framework injection |
| 6 | etl_effective_date | date | Framework auto-append |

### Sample Row (from Oct 1 output)
```
1001,1,US retail banking,USRET,2024-10-01,2024-10-01
```
