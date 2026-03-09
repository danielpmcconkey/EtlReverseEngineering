# ComplianceResolutionTime -- Output Manifesto

**Job:** ComplianceResolutionTime_RE

---

## Outputs

### compliance_resolution_time.csv

| Property | Value |
|----------|-------|
| Path | `{ETL_RE_OUTPUT}/compliance_resolution_time/compliance_resolution_time/{YYYY-MM-DD}/compliance_resolution_time.csv` |
| Format | CSV |
| Delimiter | Comma |
| Line ending | LF |
| Header | Yes (1 row) |
| Trailer | Yes -- `TRAILER\|{row_count}\|{date}` |
| Data rows | 5 per date (one per event type) |
| Write mode | Overwrite |

### Column Schema

| Position | Column | Type | Source |
|----------|--------|------|--------|
| 1 | event_type | text | datalake.compliance_events (aggregation key) |
| 2 | resolved_count | integer | COUNT(*) of resolved events per type |
| 3 | total_days | integer | SUM(days_to_resolve) per type |
| 4 | avg_resolution_days | integer | Integer division: total_days / resolved_count |
| 5 | ifw_effective_date | date | Framework injection |
| 6 | etl_effective_date | date | Framework auto-append |

### Sample Row
```
AML_FLAG,1380,23920,17,2024-10-01,2024-10-01
```

### Trailer Format
```
TRAILER|5|2024-10-01
```
The trailer contains the pipe-delimited literal "TRAILER", the data row count (always 5), and the effective date.
