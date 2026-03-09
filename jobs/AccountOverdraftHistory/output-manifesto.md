# AccountOverdraftHistory — Output Manifesto

**Job:** AccountOverdraftHistory_RE

---

## Outputs

### account_overdraft_history (Parquet directory)

| Property | Value |
|----------|-------|
| Path | `{ETL_RE_OUTPUT}/account_overdraft_history/account_overdraft_history/{YYYY-MM-DD}/account_overdraft_history/` |
| Format | Parquet |
| Partitions | 50 (part-00000 through part-00049) |
| Data rows | 2-3 per date (variable) |
| Write mode | Overwrite |

### Column Schema

| Position | Column | Type | Source |
|----------|--------|------|--------|
| 1 | overdraft_id | integer | datalake.overdraft_events |
| 2 | account_id | integer | datalake.overdraft_events |
| 3 | customer_id | integer | datalake.overdraft_events |
| 4 | account_type | text | datalake.accounts (via JOIN) |
| 5 | overdraft_amount | decimal | datalake.overdraft_events |
| 6 | fee_amount | decimal | datalake.overdraft_events |
| 7 | fee_waived | integer | datalake.overdraft_events |
| 8 | ifw_effective_date | date | Framework injection |
| 9 | etl_effective_date | date | Framework auto-append |
