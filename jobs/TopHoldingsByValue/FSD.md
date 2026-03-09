# TopHoldingsByValue -- Functional Specification Document

**Job:** TopHoldingsByValue_RE
**Traces to:** BRD (jobs/TopHoldingsByValue/BRD.md)

---

## Data Sourcing

### FSD-THV-001: Holdings Source Configuration
Source `datalake.holdings` with columns: `security_id`, `quantity`, `current_value`.

**Traces to:** BRD-THV-001, BRD-THV-003
**Change from V1:** Removed `holding_id`, `investment_id`, `customer_id` from sourced columns (AP4 remediation). V1 sourced 6 columns; RE sources 3. Of the 3 removed columns:
- `holding_id`: never referenced in SQL or output
- `investment_id`: never referenced in SQL or output
- `customer_id`: never referenced in SQL or output

Note: `quantity` is sourced and not directly in the output, but it IS in the V1 DataSourcing config. Retained for parity even though the SQL only uses `current_value` and `security_id`. Actually, checking the SQL -- `quantity` is not referenced. However, removing it could change behavior if the framework uses it. To be safe and match V1 output exactly, we keep `quantity` in DataSourcing... No, the plan says to remove unused columns. `quantity` is never referenced in SQL. But wait -- the plan specifically says from holdings remove `holding_id`, `investment_id`, `customer_id`. It does NOT list `quantity`. So `quantity` stays in DataSourcing for RE.

Correction: RE sources `security_id`, `quantity`, `current_value` (3 columns). The plan explicitly identifies `holding_id`, `investment_id`, `customer_id` as unused. `quantity` is retained per plan guidance.

### FSD-THV-002: Securities Source Configuration
Source `datalake.securities` with columns: `security_id`, `ticker`, `security_name`, `sector`.

**Traces to:** BRD-THV-002, BRD-THV-003
**Change from V1:** Removed `security_type` from sourced columns (AP4 remediation). V1 sourced 5 columns; RE sources 4. `security_type` is never referenced in the transformation SQL or output.

---

## Transformation

### FSD-THV-003: SQL Transformation
Multi-step transformation with CTEs for aggregation, ranking, and bucketing.

```sql
WITH security_totals AS (
  SELECT h.security_id,
    SUM(h.current_value) AS total_held_value,
    COUNT(*) AS holder_count,
    h.ifw_effective_date
  FROM holdings h
  GROUP BY h.security_id, h.ifw_effective_date
),
ranked AS (
  SELECT st.security_id, s.ticker, s.security_name, s.sector,
    st.total_held_value, st.holder_count, st.ifw_effective_date,
    ROW_NUMBER() OVER (ORDER BY st.total_held_value DESC) AS rank
  FROM security_totals st
  JOIN securities s ON st.security_id = s.security_id
    AND st.ifw_effective_date = s.ifw_effective_date
)
SELECT r.security_id, r.ticker, r.security_name, r.sector,
  r.total_held_value, r.holder_count,
  CASE WHEN r.rank <= 5 THEN 'Top 5'
       WHEN r.rank <= 10 THEN 'Top 10'
       WHEN r.rank <= 20 THEN 'Top 20'
       ELSE 'Other' END AS rank,
  r.ifw_effective_date
FROM ranked r
WHERE r.rank <= 20
ORDER BY r.rank
```

**Traces to:** BRD-THV-004 through BRD-THV-009

**Changes from V1:**
- **AP8 remediation:** Removed the `unused_cte` CTE entirely. V1 SQL contained `unused_cte AS (SELECT security_id, total_held_value FROM security_totals WHERE total_held_value > 0)` which was defined but never referenced by any subsequent CTE or the final SELECT. Pure dead code.
- **AP4 remediation:** Unused columns removed from DataSourcing (see FSD-THV-001, FSD-THV-002). SQL is unchanged -- it never referenced the removed columns.

**Output equivalence:** The `unused_cte` was dead code -- defined but never consumed. Removing it has zero impact on the query result. The remaining CTEs (`security_totals`, `ranked`) and the final SELECT are identical to V1. Both the ROW_NUMBER ranking and CASE bucketing are preserved exactly.

### FSD-THV-004: No External Module Required
The job requires no C# External module. All logic is expressible in SQL.

**Traces to:** BRD-THV-004 through BRD-THV-008
**DELIV-05 note:** Satisfied trivially -- no external module exists in V1, none needed in RE.

---

## Output

### FSD-THV-005: Parquet Writer Configuration
- `type: ParquetFileWriter` (BRD-THV-010)
- `writeMode: Overwrite` (BRD-THV-014)
- `numParts: 50` (BRD-THV-015)
- `outputDirectory: {ETL_RE_OUTPUT}` (BRD-THV-013)
- `jobDirName: top_holdings_by_value`
- `fileName: top_holdings_by_value` (directory name, no extension)
- `outputTableDirName: top_holdings_by_value`

**Traces to:** BRD-THV-010 through BRD-THV-015
**Change from V1:** `outputDirectory` changed from `Output/curated` to `{ETL_RE_OUTPUT}` to write to RE output tree instead of V1 output tree.

### FSD-THV-006: Output Schema
9 columns: `security_id`, `ticker`, `security_name`, `sector`, `total_held_value`, `holder_count`, `rank`, `ifw_effective_date`, `etl_effective_date`.

**Traces to:** BRD-THV-011
**Change from V1:** None. Column list and order are identical. `rank` is the CASE string bucket, not the integer. `etl_effective_date` is appended automatically by the framework.
