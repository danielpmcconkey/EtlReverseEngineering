# TopHoldingsByValue -- Output Manifesto

**Job:** TopHoldingsByValue_RE

---

## Outputs

### top_holdings_by_value (Parquet directory)

| Property | Value |
|----------|-------|
| Path | `{ETL_RE_OUTPUT}/top_holdings_by_value/top_holdings_by_value/{YYYY-MM-DD}/top_holdings_by_value/` |
| Format | Parquet |
| Part files | 50 (`part-00000.parquet` through `part-00049.parquet`) |
| Data rows | 20 per date (top 20 securities by held value) |
| Write mode | Overwrite |

### Column Schema

| Position | Column | Type | Source |
|----------|--------|------|--------|
| 1 | security_id | integer | datalake.holdings (aggregation key) |
| 2 | ticker | string | datalake.securities (JOIN) |
| 3 | security_name | string | datalake.securities (JOIN) |
| 4 | sector | string | datalake.securities (JOIN) |
| 5 | total_held_value | numeric | SUM(current_value) per security |
| 6 | holder_count | integer | COUNT(*) per security |
| 7 | rank | string | CASE bucket: 'Top 5', 'Top 10', 'Top 20' |
| 8 | ifw_effective_date | date | Framework injection |
| 9 | etl_effective_date | date | Framework auto-append |

### Notes
- The `rank` column contains CASE string values ('Top 5', 'Top 10', 'Top 20'), NOT the ROW_NUMBER integer.
- ROW_NUMBER is used internally for ranking and filtering (WHERE rank <= 20) but the integer value is not in the output.
- `fileName` is `top_holdings_by_value` (a directory name), not a file with extension.
- Two data sources: `holdings` for aggregation, `securities` for enrichment via JOIN.
