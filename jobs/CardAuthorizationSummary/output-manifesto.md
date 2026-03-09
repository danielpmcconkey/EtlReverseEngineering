# CardAuthorizationSummary -- Output Manifesto

**Job:** CardAuthorizationSummary_RE

---

## Outputs

### card_authorization_summary.csv

| Property | Value |
|----------|-------|
| Path | `{ETL_RE_OUTPUT}/card_authorization_summary/card_authorization_summary/{YYYY-MM-DD}/card_authorization_summary.csv` |
| Format | CSV |
| Delimiter | Comma |
| Line ending | LF |
| Header | Yes (1 row) |
| Trailer | Yes -- `TRAILER\|{row_count}\|{date}` |
| Data rows | 2 per date (one per card type) |
| Write mode | Overwrite |

### Column Schema

| Position | Column | Type | Source |
|----------|--------|------|--------|
| 1 | card_type | text | datalake.cards (aggregation key via JOIN) |
| 2 | total_count | integer | COUNT(*) per card type |
| 3 | approved_count | integer | SUM(CASE WHEN authorization_status = 'Approved') |
| 4 | declined_count | integer | SUM(CASE WHEN authorization_status = 'Declined') |
| 5 | approval_rate | integer | Integer division: approved_count / total_count (always 0) |
| 6 | ifw_effective_date | date | Framework injection |
| 7 | etl_effective_date | date | Framework auto-append |

### Sample Row
```
Credit,535,501,34,0,2024-10-01,2024-10-01
```

### Trailer Format
```
TRAILER|2|2024-10-01
```
The trailer contains the pipe-delimited literal "TRAILER", the data row count (always 2), and the effective date. This trailer is deterministic -- no runtime timestamps.
