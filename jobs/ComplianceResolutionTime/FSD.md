# ComplianceResolutionTime -- Functional Specification Document

**Job:** ComplianceResolutionTime_RE
**Traces to:** BRD (jobs/ComplianceResolutionTime/BRD.md)

---

## Data Sourcing

### FSD-CRT-001: Source Configuration
Source `datalake.compliance_events` with columns: `event_id`, `event_type`, `event_date`, `status`, `review_date`.

**Traces to:** BRD-CRT-001, BRD-CRT-002
**Change from V1:** Removed `customer_id` from sourced columns (AP4 remediation). V1 sourced 6 columns; RE sources 5. `customer_id` was never referenced in the transformation SQL or output -- pure dead weight.

---

## Transformation

### FSD-CRT-002: SQL Transformation
Filter to resolved events, calculate resolution days, aggregate by event type, access `ifw_effective_date` directly from the filtered CTE.

```sql
WITH resolved AS (
  SELECT event_type,
    CAST(julianday(review_date) - julianday(event_date) AS INTEGER) AS days_to_resolve,
    ifw_effective_date
  FROM compliance_events
  WHERE status = 'Cleared' AND review_date IS NOT NULL
)
SELECT event_type,
  COUNT(*) AS resolved_count,
  SUM(days_to_resolve) AS total_days,
  CAST(SUM(days_to_resolve) AS INTEGER) / CAST(COUNT(*) AS INTEGER) AS avg_resolution_days,
  ifw_effective_date
FROM resolved
GROUP BY event_type, ifw_effective_date
```

**Traces to:** BRD-CRT-003, BRD-CRT-004, BRD-CRT-005, BRD-CRT-006, BRD-CRT-007

**Changes from V1:**
- **AP4 remediation:** `customer_id` not sourced (removed at DataSourcing layer), not referenced in SQL.
- **AP8 remediation (1):** Removed `JOIN compliance_events ON 1=1` cartesian join. V1 used this hack to access `compliance_events.ifw_effective_date` from the outer query, but `ifw_effective_date` is available on every row in `compliance_events`, including those already in the `resolved` CTE. RE accesses it directly from the CTE, eliminating the cartesian join.
- **AP8 remediation (2):** Removed `ROW_NUMBER() OVER (PARTITION BY event_type ORDER BY event_date) AS rn`. V1 computed this window function but never filtered on `rn` anywhere. The column was dead SQL -- computed and discarded during GROUP BY aggregation.
- **AP5 (documented, NOT changed):** Integer division `CAST(SUM(...) AS INTEGER) / CAST(COUNT(*) AS INTEGER)` is preserved exactly as V1. This truncates rather than rounds (e.g., 23920/1380 = 17.333... becomes 17). Changing this would break byte-identical output.

**Output equivalence:** The cartesian join `JOIN compliance_events ON 1=1` had no effect on GROUP BY results because `compliance_events.ifw_effective_date` is constant within a single execution date (all rows share the same value). Removing it and accessing `ifw_effective_date` directly produces identical aggregation results. The ROW_NUMBER was never filtered on, so removing it changes nothing.

### FSD-CRT-003: No External Module Required
The job requires no C# External module. All logic is expressible in SQL.

**Traces to:** BRD-CRT-005
**DELIV-05 note:** Satisfied trivially -- no external module exists in V1, none needed in RE.

---

## Output

### FSD-CRT-004: CSV Writer Configuration
- `includeHeader: true` (BRD-CRT-009)
- `writeMode: Overwrite` (BRD-CRT-014)
- `lineEnding: LF` (BRD-CRT-008)
- `trailerFormat: "TRAILER|{row_count}|{date}"` (BRD-CRT-012)
- `outputDirectory: {ETL_RE_OUTPUT}` (BRD-CRT-013)
- `jobDirName: compliance_resolution_time`
- `fileName: compliance_resolution_time.csv`
- `outputTableDirName: compliance_resolution_time`

**Traces to:** BRD-CRT-008 through BRD-CRT-014
**Change from V1:** `outputDirectory` changed from `Output/curated` to `{ETL_RE_OUTPUT}` to write to RE output tree instead of V1 output tree.

### FSD-CRT-005: Output Schema
6 columns: `event_type`, `resolved_count`, `total_days`, `avg_resolution_days`, `ifw_effective_date`, `etl_effective_date`.

**Traces to:** BRD-CRT-010
**Change from V1:** None. Column list and order are identical. `etl_effective_date` is appended automatically by the framework.
