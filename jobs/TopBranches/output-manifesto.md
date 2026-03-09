# TopBranches -- Output Manifesto

**Job:** TopBranches_RE

---

## Outputs

### top_branches.csv

| Property | Value |
|----------|-------|
| Path | `{ETL_RE_OUTPUT}/top_branches/top_branches/{YYYY-MM-DD}/top_branches.csv` |
| Format | CSV |
| Delimiter | Comma |
| Line ending | LF |
| Header | Yes (1 row) |
| Trailer | Yes -- `CONTROL\|{date}\|{row_count}\|{timestamp}` (NON-DETERMINISTIC) |
| Data rows | 40 per date (all branches ranked) |
| Write mode | Overwrite |

### Column Schema

| Position | Column | Type | Source |
|----------|--------|------|--------|
| 1 | branch_id | integer | datalake.branch_visits (aggregation key) |
| 2 | branch_name | text | datalake.branches (via JOIN) |
| 3 | total_visits | integer | COUNT(*) per branch |
| 4 | rank | integer | RANK() OVER (ORDER BY total_visits DESC) |
| 5 | ifw_effective_date | date | Framework injection |
| 6 | etl_effective_date | date | Framework auto-append |

### Sample Row
```
4,San Francisco CA Branch,10,1,2024-10-01,2024-10-01
```

### Trailer Format
```
CONTROL|2024-10-01|40|2026-03-08T17:52:27Z
```
The trailer contains pipe-delimited: literal "CONTROL", effective date, data row count (always 40), and a runtime ISO timestamp. The timestamp is non-deterministic and differs between V1 and RE runs.
