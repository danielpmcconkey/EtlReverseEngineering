# CustomerAccountSummary -- Output Manifesto

**Job:** CustomerAccountSummary_RE

---

## Outputs

### customer_account_summary.csv

| Property | Value |
|----------|-------|
| Path | `{ETL_RE_OUTPUT}/customer_account_summary/customer_account_summary/{YYYY-MM-DD}/customer_account_summary.csv` |
| Format | CSV |
| Delimiter | Comma |
| Line ending | LF |
| Header | Yes (1 row) |
| Trailer | No |
| Data rows | 2230 per date |
| Write mode | Overwrite |

### Column Schema

| Position | Column | Type | Source |
|----------|--------|------|--------|
| 1 | customer_id | integer | datalake.customers.id |
| 2 | first_name | text | datalake.customers |
| 3 | last_name | text | datalake.customers |
| 4 | account_count | integer | COUNT(accounts.account_id) |
| 5 | active_balance | numeric(2) | SUM(current_balance) WHERE status='Active' |
| 6 | etl_effective_date | date | Framework auto-append |

### Sample Row
```
1,John,Smith,3,15234.56,2024-10-01
```
