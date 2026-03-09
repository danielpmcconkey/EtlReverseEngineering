# CustomerSegmentMap -- Functional Specification Document

**Job:** CustomerSegmentMap_RE
**Traces to:** BRD (jobs/CustomerSegmentMap/BRD.md)

---

## Data Sourcing

### FSD-CSM-001: Source Configuration
Two DataSourcing modules:
1. `datalake.customers_segments` with columns: `customer_id`, `segment_id`
2. `datalake.segments` with columns: `segment_id`, `segment_name`, `segment_code`

Standard effective date scoping for both.

**Traces to:** BRD-CSM-001, BRD-CSM-002, BRD-CSM-004
**Change from V1:** Removed `datalake.branches` DataSourcing module (AP1 remediation). The `branches` result set was never referenced in the SQL transformation. See BRD-CSM-003.

---

## Transformation

### FSD-CSM-002: SQL Transformation
Join customer-segment assignments with segment details:

```sql
SELECT cs.customer_id, cs.segment_id, s.segment_name, s.segment_code, cs.ifw_effective_date FROM customers_segments cs JOIN segments s ON cs.segment_id = s.segment_id AND cs.ifw_effective_date = s.ifw_effective_date ORDER BY cs.customer_id, cs.segment_id
```

**Traces to:** BRD-CSM-005, BRD-CSM-006, BRD-CSM-007
**Change from V1:** None. SQL is identical (it never referenced `branches`).

### FSD-CSM-003: No External Module Required
All logic is expressible in SQL.

**Traces to:** BRD-CSM-005
**DELIV-05 note:** Satisfied trivially.

---

## Output

### FSD-CSM-004: CSV Writer Configuration
- `includeHeader: true` (BRD-CSM-009)
- `writeMode: Append` (BRD-CSM-014)
- `lineEnding: LF` (BRD-CSM-008)
- `outputDirectory: {ETL_RE_OUTPUT}` (BRD-CSM-013)
- `jobDirName: customer_segment_map`
- `fileName: customer_segment_map.csv`
- `outputTableDirName: customer_segment_map`

**Traces to:** BRD-CSM-008 through BRD-CSM-014
**Change from V1:** `outputDirectory` changed to `{ETL_RE_OUTPUT}`.

### FSD-CSM-005: Output Schema
6 columns: `customer_id`, `segment_id`, `segment_name`, `segment_code`, `ifw_effective_date`, `etl_effective_date`.

**Traces to:** BRD-CSM-010
**Change from V1:** None.
