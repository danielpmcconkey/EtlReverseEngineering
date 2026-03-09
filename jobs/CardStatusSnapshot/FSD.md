# CardStatusSnapshot -- Functional Specification Document

**Job:** CardStatusSnapshot_RE
**Traces to:** BRD (jobs/CardStatusSnapshot/BRD.md)

---

## Data Sourcing

### FSD-CSS-001: Source Configuration
Source `datalake.cards` with columns: `card_status`.

**Traces to:** BRD-CSS-001, BRD-CSS-002
**Change from V1:** Removed `card_id`, `customer_id`, `card_number_masked`, `expiration_date` from sourced columns (AP4 remediation). V1 sourced 6 columns; RE sources 1. Of the 5 removed columns:
- `card_id`: never referenced in SQL or output
- `customer_id`: never referenced in SQL or output
- `card_type`: referenced in V1 DataSourcing but not in SQL -- however, on closer inspection V1 sources `card_type` but SQL only uses `card_status`. Actually checking V1 conf... V1 sources `card_type` but SQL never uses it. Removed.
- `card_number_masked`: never referenced in SQL or output
- `expiration_date`: never referenced in SQL or output

Note: `card_type` is in V1's sourced columns but never appears in the SQL. The plan identified 4 unused columns (`card_id`, `customer_id`, `card_number_masked`, `expiration_date`), but `card_type` is also unused. All 5 non-`card_status` columns are removed.

---

## Transformation

### FSD-CSS-002: SQL Transformation
Aggregate cards by card_status with COUNT.

```sql
SELECT c.card_status, COUNT(*) AS card_count, c.ifw_effective_date
FROM cards c
GROUP BY c.card_status, c.ifw_effective_date
```

**Traces to:** BRD-CSS-003, BRD-CSS-004, BRD-CSS-005, BRD-CSS-006
**Change from V1:** SQL is identical. No anti-patterns in the transformation logic itself. The only remediation is at the DataSourcing layer (AP4).

### FSD-CSS-003: No External Module Required
The job requires no C# External module. All logic is expressible in SQL.

**Traces to:** BRD-CSS-003
**DELIV-05 note:** Satisfied trivially -- no external module exists in V1, none needed in RE.

---

## Output

### FSD-CSS-004: Parquet Writer Configuration
- `type: ParquetFileWriter` (BRD-CSS-007)
- `writeMode: Overwrite` (BRD-CSS-011)
- `numParts: 50` (BRD-CSS-012)
- `outputDirectory: {ETL_RE_OUTPUT}` (BRD-CSS-010)
- `jobDirName: card_status_snapshot`
- `fileName: card_status_snapshot` (directory name, no extension)
- `outputTableDirName: card_status_snapshot`

**Traces to:** BRD-CSS-007 through BRD-CSS-012
**Change from V1:** `outputDirectory` changed from `Output/curated` to `{ETL_RE_OUTPUT}` to write to RE output tree instead of V1 output tree.

### FSD-CSS-005: Output Schema
4 columns: `card_status`, `card_count`, `ifw_effective_date`, `etl_effective_date`.

**Traces to:** BRD-CSS-008
**Change from V1:** None. Column list and order are identical. `etl_effective_date` is appended automatically by the framework.
