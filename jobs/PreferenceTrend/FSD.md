# PreferenceTrend -- Functional Specification Document

**Job:** PreferenceTrend_RE
**Traces to:** BRD (jobs/PreferenceTrend/BRD.md)

---

## Data Sourcing

### FSD-PT-001: Source Configuration
Source `datalake.customer_preferences` with columns: `preference_id`, `customer_id`, `preference_type`, `opted_in`. Standard effective date scoping (no min/max overrides).

**Traces to:** BRD-PT-001, BRD-PT-002
**Change from V1:** None. DataSourcing module is identical.

---

## Transformation

### FSD-PT-002: SQL Transformation
Aggregate preference opt-in/opt-out counts by type:

```sql
SELECT cp.preference_type, SUM(CASE WHEN cp.opted_in = 1 THEN 1 ELSE 0 END) AS opted_in_count, SUM(CASE WHEN cp.opted_in = 0 THEN 1 ELSE 0 END) AS opted_out_count, cp.ifw_effective_date FROM customer_preferences cp GROUP BY cp.preference_type, cp.ifw_effective_date
```

**Traces to:** BRD-PT-003, BRD-PT-004, BRD-PT-005
**Change from V1:** None. SQL is identical.

### FSD-PT-003: No External Module Required
All logic is expressible in SQL.

**Traces to:** BRD-PT-003
**DELIV-05 note:** Satisfied trivially.

---

## Output

### FSD-PT-004: CSV Writer Configuration
- `includeHeader: true` (BRD-PT-007)
- `writeMode: Append` (BRD-PT-012)
- `lineEnding: LF` (BRD-PT-006)
- `outputDirectory: {ETL_RE_OUTPUT}` (BRD-PT-011)
- `jobDirName: preference_trend`
- `fileName: preference_trend.csv`
- `outputTableDirName: preference_trend`

**Traces to:** BRD-PT-006 through BRD-PT-012
**Change from V1:** `outputDirectory` changed from `Output/curated` to `{ETL_RE_OUTPUT}`.

### FSD-PT-005: Output Schema
5 columns: `preference_type`, `opted_in_count`, `opted_out_count`, `ifw_effective_date`, `etl_effective_date`.

**Traces to:** BRD-PT-008
**Change from V1:** None.
