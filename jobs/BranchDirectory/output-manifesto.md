# BranchDirectory — Output Manifesto

**Job:** BranchDirectory_RE

---

## Outputs

### branch_directory.csv

| Property | Value |
|----------|-------|
| Path | `{ETL_RE_OUTPUT}/branch_directory/branch_directory/{YYYY-MM-DD}/branch_directory.csv` |
| Format | CSV |
| Delimiter | Comma |
| Line ending | CRLF |
| Header | Yes (1 row) |
| Trailer | No |
| Data rows | 40 per date |
| Write mode | Overwrite |

### Column Schema

| Position | Column | Type | Source |
|----------|--------|------|--------|
| 1 | branch_id | integer | datalake.branches |
| 2 | branch_name | text | datalake.branches |
| 3 | address_line1 | text | datalake.branches |
| 4 | city | text | datalake.branches |
| 5 | state_province | text | datalake.branches |
| 6 | postal_code | text | datalake.branches |
| 7 | country | text | datalake.branches |
| 8 | ifw_effective_date | date | Framework injection |
| 9 | etl_effective_date | date | Framework auto-append |

### Sample Row
```
1,Columbus OH Branch,100 E Broad St,Columbus,OH,43215,US,2024-10-01,2024-10-01
```
