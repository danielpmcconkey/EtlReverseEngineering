# PreferenceTrend -- Output Manifesto

**Job:** PreferenceTrend_RE

---

## Outputs

### preference_trend.csv

| Property | Value |
|----------|-------|
| Path | `{ETL_RE_OUTPUT}/preference_trend/preference_trend/{YYYY-MM-DD}/preference_trend.csv` |
| Format | CSV |
| Delimiter | Comma |
| Line ending | LF |
| Header | Yes (1 row) |
| Trailer | No |
| Data rows (Oct 1) | 5 |
| Data rows (Dec 31) | 460 (cumulative) |
| Write mode | Append |

### Column Schema

| Position | Column | Type | Source |
|----------|--------|------|--------|
| 1 | preference_type | text | GROUP BY column |
| 2 | opted_in_count | integer | SUM(CASE opted_in = 1) |
| 3 | opted_out_count | integer | SUM(CASE opted_in = 0) |
| 4 | ifw_effective_date | date | GROUP BY column |
| 5 | etl_effective_date | date | Framework auto-append |

### Sample Row (from Oct 1 output)
```
E_STATEMENTS,1806,424,2024-10-01,2024-10-01
```
