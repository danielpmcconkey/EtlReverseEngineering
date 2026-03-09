# DailyWireVolume -- Functional Specification Document

**Job:** DailyWireVolume_RE
**Traces to:** BRD (jobs/DailyWireVolume/BRD.md)

---

## Data Sourcing

### FSD-DWV-001: Source Configuration
Source `datalake.wire_transfers` with columns: `wire_id`, `customer_id`, `direction`, `amount`, `status`, `wire_timestamp`. Full date range via `minEffectiveDate: 2024-10-01`, `maxEffectiveDate: 2024-12-31`.

**Traces to:** BRD-DWV-001, BRD-DWV-002
**Change from V1:** None. DataSourcing module is identical.

---

## Transformation

### FSD-DWV-002: SQL Transformation
Aggregate wire transfers per date across the full date range:

```sql
SELECT ifw_effective_date AS wire_date, COUNT(*) AS wire_count, ROUND(SUM(amount), 2) AS total_amount, ifw_effective_date FROM wire_transfers WHERE ifw_effective_date >= '2024-10-01' AND ifw_effective_date <= '2024-12-31' GROUP BY ifw_effective_date ORDER BY ifw_effective_date
```

**Traces to:** BRD-DWV-003, BRD-DWV-004, BRD-DWV-005
**Change from V1:** None. SQL is identical. The WHERE clause is technically redundant with DataSourcing's min/maxEffectiveDate (AP10), but is load-bearing -- removing it would change nothing since DataSourcing already scopes the data. Kept for safety.

### FSD-DWV-003: No External Module Required
All logic is expressible in SQL. No C# External module.

**Traces to:** BRD-DWV-003
**DELIV-05 note:** Satisfied trivially -- no external module exists in V1, none needed in RE.

---

## Output

### FSD-DWV-004: CSV Writer Configuration
- `includeHeader: true` (BRD-DWV-007)
- `writeMode: Append` (BRD-DWV-012)
- `lineEnding: LF` (BRD-DWV-006)
- `outputDirectory: {ETL_RE_OUTPUT}` (BRD-DWV-011)
- `jobDirName: daily_wire_volume`
- `fileName: daily_wire_volume.csv`
- `outputTableDirName: daily_wire_volume`

**Traces to:** BRD-DWV-006 through BRD-DWV-012
**Change from V1:** `outputDirectory` changed from `Output/curated` to `{ETL_RE_OUTPUT}` to write to RE output tree.

### FSD-DWV-005: Output Schema
5 columns: `wire_date`, `wire_count`, `total_amount`, `ifw_effective_date`, `etl_effective_date`.

**Traces to:** BRD-DWV-008
**Change from V1:** None. Column list and order are identical.
