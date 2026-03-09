# FeeWaiverAnalysis -- Functional Specification Document

**Job:** FeeWaiverAnalysis_RE
**Traces to:** BRD (jobs/FeeWaiverAnalysis/BRD.md)

---

## Data Sourcing

### FSD-FWA-001: Overdraft Events Source Configuration
Source `datalake.overdraft_events` with columns: `account_id`, `overdraft_amount`, `fee_amount`, `fee_waived`.

**Traces to:** BRD-FWA-001, BRD-FWA-003
**Change from V1:** Removed `overdraft_id`, `customer_id`, `event_timestamp` from sourced columns (AP4 remediation). V1 sourced 7 columns; RE sources 4. None of the removed columns are referenced in the transformation SQL or output. `account_id` is retained because it's needed for the LEFT JOIN ON clause. `overdraft_amount` is retained because it's sourced in V1 (conservative posture).

### FSD-FWA-002: Accounts Source Configuration
Source `datalake.accounts` with columns: `account_id`.

**Traces to:** BRD-FWA-002, BRD-FWA-003
**Change from V1:** Removed `customer_id`, `account_type`, `account_status`, `interest_rate`, `credit_limit`, `apr` from sourced columns (AP4 remediation). V1 sourced 7 columns; RE sources 1. All 6 removed columns are never referenced in the transformation SQL or output. `account_id` is retained because it's needed for the LEFT JOIN ON clause.

**AP1 note:** The entire accounts DataSourcing is arguably dead (AP1) since no accounts columns appear in the output. However, the LEFT JOIN itself could theoretically affect row counts. Investigation (BRD-FWA-005) confirmed it does NOT -- but we retain it for safety.

---

## Transformation

### FSD-FWA-003: SQL Transformation
LEFT JOIN overdraft_events to accounts, aggregate by fee_waived status with null-safe SUM/AVG.

```sql
SELECT oe.fee_waived,
  COUNT(*) AS event_count,
  ROUND(SUM(CASE WHEN oe.fee_amount IS NULL THEN 0.0 ELSE oe.fee_amount END), 2) AS total_fees,
  ROUND(AVG(CASE WHEN oe.fee_amount IS NULL THEN 0.0 ELSE oe.fee_amount END), 2) AS avg_fee,
  oe.ifw_effective_date
FROM overdraft_events oe
LEFT JOIN accounts a ON oe.account_id = a.account_id AND oe.ifw_effective_date = a.ifw_effective_date
GROUP BY oe.fee_waived, oe.ifw_effective_date
ORDER BY oe.fee_waived
```

**Traces to:** BRD-FWA-004, BRD-FWA-005, BRD-FWA-006, BRD-FWA-007, BRD-FWA-008, BRD-FWA-009

**Changes from V1:**
- **AP4 remediation:** 3 unused columns removed from overdraft_events DataSourcing (`overdraft_id`, `customer_id`, `event_timestamp`). 6 unused columns removed from accounts DataSourcing (all except `account_id`). None referenced in SQL.
- **LEFT JOIN RETAINED:** Despite being functionally dead (no accounts columns in SELECT/WHERE/GROUP BY), the LEFT JOIN is preserved exactly as V1. Investigation confirmed no duplicate (account_id, ifw_effective_date) pairs exist in accounts, so the JOIN does not inflate counts. Removing it would produce identical output but adds unnecessary risk.

**Output equivalence:** AP4 column removal is DataSourcing-only. LEFT JOIN preserved exactly. The SELECT column list, GROUP BY, and ORDER BY are identical to V1.

### FSD-FWA-004: No External Module Required
The job requires no C# External module. All logic is expressible in SQL.

**Traces to:** BRD-FWA-006

---

## Output

### FSD-FWA-005: CSV Writer Configuration
- `includeHeader: true` (BRD-FWA-011)
- `writeMode: Overwrite` (BRD-FWA-015)
- `lineEnding: LF` (BRD-FWA-010)
- No trailer (BRD-FWA-013)
- `outputDirectory: {ETL_RE_OUTPUT}` (BRD-FWA-014)
- `jobDirName: fee_waiver_analysis`
- `fileName: fee_waiver_analysis.csv`
- `outputTableDirName: fee_waiver_analysis`

**Traces to:** BRD-FWA-010 through BRD-FWA-015
**Change from V1:** `outputDirectory` changed from `Output/curated` to `{ETL_RE_OUTPUT}` to write to RE output tree instead of V1 output tree.

### FSD-FWA-006: Output Schema
6 columns: `fee_waived`, `event_count`, `total_fees`, `avg_fee`, `ifw_effective_date`, `etl_effective_date`.

**Traces to:** BRD-FWA-012
**Change from V1:** None. Column list and order are identical. `etl_effective_date` is appended automatically by the framework.
