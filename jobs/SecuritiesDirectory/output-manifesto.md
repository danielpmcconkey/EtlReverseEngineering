# SecuritiesDirectory -- Output Manifesto

**Job:** SecuritiesDirectory_RE

---

## Outputs

### securities_directory.csv

| Property | Value |
|----------|-------|
| Path | `{ETL_RE_OUTPUT}/securities_directory/securities_directory/{YYYY-MM-DD}/securities_directory.csv` |
| Format | CSV |
| Delimiter | Comma |
| Line ending | LF |
| Header | Yes (1 row) |
| Trailer | No |
| Data rows | 50 per date |
| Write mode | Overwrite |

### Column Schema

| Position | Column | Type | Source |
|----------|--------|------|--------|
| 1 | security_id | integer | datalake.securities |
| 2 | ticker | text | datalake.securities |
| 3 | security_name | text | datalake.securities |
| 4 | security_type | text | datalake.securities |
| 5 | sector | text | datalake.securities |
| 6 | exchange | text | datalake.securities |
| 7 | ifw_effective_date | date | Framework injection |
| 8 | etl_effective_date | date | Framework auto-append |

### Sample Row
```
1,AAPL,Apple Inc,Stock,Technology,NASDAQ,2024-10-01,2024-10-01
```
