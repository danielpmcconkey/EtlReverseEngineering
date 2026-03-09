# PreferenceChangeCount — Output Manifesto

**Job:** PreferenceChangeCount_RE

---

## Outputs

### preference_change_count (Parquet directory)

| Property | Value |
|----------|-------|
| Path | `{ETL_RE_OUTPUT}/preference_change_count/preference_change_count/{YYYY-MM-DD}/preference_change_count/` |
| Format | Parquet |
| Partitions | 1 (single part file) |
| Data rows | 2230 per date (stable) |
| Write mode | Overwrite |

### Column Schema

| Position | Column | Type | Source |
|----------|--------|------|--------|
| 1 | customer_id | integer | datalake.customer_preferences |
| 2 | preference_count | integer | Computed: COUNT(*) |
| 3 | has_email_opt_in | integer | Computed: MAX(CASE WHEN MARKETING_EMAIL...) |
| 4 | has_sms_opt_in | integer | Computed: MAX(CASE WHEN MARKETING_SMS...) |
| 5 | ifw_effective_date | date | Framework injection |
| 6 | etl_effective_date | date | Framework auto-append |
