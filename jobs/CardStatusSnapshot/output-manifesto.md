# CardStatusSnapshot -- Output Manifesto

**Job:** CardStatusSnapshot_RE

---

## Outputs

### card_status_snapshot (Parquet directory)

| Property | Value |
|----------|-------|
| Path | `{ETL_RE_OUTPUT}/card_status_snapshot/card_status_snapshot/{YYYY-MM-DD}/card_status_snapshot/` |
| Format | Parquet |
| Part files | 50 (`part-00000.parquet` through `part-00049.parquet`) |
| Data rows | 3 per date (one per card_status value) |
| Write mode | Overwrite |

### Column Schema

| Position | Column | Type | Source |
|----------|--------|------|--------|
| 1 | card_status | string | datalake.cards (aggregation key) |
| 2 | card_count | integer | COUNT(*) per group |
| 3 | ifw_effective_date | date | Framework injection |
| 4 | etl_effective_date | date | Framework auto-append |

### Notes
- 3 rows across 50 part files means most parts are empty. This matches V1 behavior.
- `fileName` is `card_status_snapshot` (a directory name), not a file with extension.
