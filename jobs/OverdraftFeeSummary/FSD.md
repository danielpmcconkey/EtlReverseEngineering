# OverdraftFeeSummary -- Functional Specification Document

**Job:** OverdraftFeeSummary_RE
**Traces to:** BRD (jobs/OverdraftFeeSummary/BRD.md)

---

## Data Sourcing

### FSD-OFS-001: Source Configuration
Source `datalake.overdraft_events` with columns: `fee_amount`, `fee_waived`.

**Traces to:** BRD-OFS-001, BRD-OFS-002
**Change from V1:** Removed `overdraft_id`, `account_id`, `customer_id`, `overdraft_amount`, `event_timestamp` from sourced columns (AP4 remediation). V1 sourced 7 columns; RE sources 2. Of the 5 removed columns:
- `account_id`, `customer_id`, `event_timestamp`: never referenced in SQL or output
- `overdraft_amount`: never referenced in SQL or output
- `overdraft_id`: only referenced in dead ROW_NUMBER ORDER BY clause (AP8 -- removed)

---

## Transformation

### FSD-OFS-002: SQL Transformation
Aggregate overdraft events by fee_waived status with SUM, COUNT, AVG, ROUND.

```sql
SELECT oe.fee_waived,
  ROUND(SUM(oe.fee_amount), 2) AS total_fees,
  COUNT(*) AS event_count,
  ROUND(AVG(oe.fee_amount), 2) AS avg_fee,
  oe.ifw_effective_date
FROM overdraft_events oe
GROUP BY oe.fee_waived, oe.ifw_effective_date
ORDER BY oe.fee_waived
```

**Traces to:** BRD-OFS-003, BRD-OFS-004, BRD-OFS-005, BRD-OFS-006, BRD-OFS-007, BRD-OFS-008

**Changes from V1:**
- **AP4 remediation:** 5 unused columns removed from DataSourcing. None referenced in the SQL or output.
- **AP8 remediation:** Removed entire `all_events` CTE. V1 SQL wrapped the query in `WITH all_events AS (SELECT ..., ROW_NUMBER() OVER (PARTITION BY ifw_effective_date ORDER BY overdraft_id) AS rn ...) SELECT ... FROM all_events ae ...`. The ROW_NUMBER (`rn`) was never referenced in the outer query -- never filtered on, never selected, never grouped by. The CTE was pure overhead. RE replaces with a direct query against `overdraft_events`.

**Output equivalence:** The CTE passed through all rows unfiltered (no WHERE clause, no rn filter). The outer query performed identical GROUP BY / SUM / COUNT / AVG / ROUND. Removing the CTE wrapper produces algebraically identical results. Verified via Proofmark 92/92 PASS.

### FSD-OFS-003: No External Module Required
The job requires no C# External module. All logic is expressible in SQL.

**Traces to:** BRD-OFS-003
**DELIV-05 note:** Satisfied trivially -- no external module exists in V1, none needed in RE.

---

## Output

### FSD-OFS-004: CSV Writer Configuration
- `includeHeader: true` (BRD-OFS-010)
- `writeMode: Overwrite` (BRD-OFS-014)
- `lineEnding: LF` (BRD-OFS-009)
- No trailer (BRD-OFS-012)
- `outputDirectory: {ETL_RE_OUTPUT}` (BRD-OFS-013)
- `jobDirName: overdraft_fee_summary`
- `fileName: overdraft_fee_summary.csv`
- `outputTableDirName: overdraft_fee_summary`

**Traces to:** BRD-OFS-009 through BRD-OFS-014
**Change from V1:** `outputDirectory` changed from `Output/curated` to `{ETL_RE_OUTPUT}` to write to RE output tree instead of V1 output tree.

### FSD-OFS-005: Output Schema
6 columns: `fee_waived`, `total_fees`, `event_count`, `avg_fee`, `ifw_effective_date`, `etl_effective_date`.

**Traces to:** BRD-OFS-011
**Change from V1:** None. Column list and order are identical. `etl_effective_date` is appended automatically by the framework.
