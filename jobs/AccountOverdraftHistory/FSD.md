# AccountOverdraftHistory — Functional Specification Document

**Job:** AccountOverdraftHistory_RE
**Traces to:** BRD (jobs/AccountOverdraftHistory/BRD.md)

---

## Data Sourcing

### FSD-AOH-001: Overdraft Events Source Configuration
Source `datalake.overdraft_events` with columns: `overdraft_id`, `account_id`, `customer_id`, `overdraft_amount`, `fee_amount`, `fee_waived`.

**Traces to:** BRD-AOH-001, BRD-AOH-003
**Change from V1:** Removed `event_timestamp` (AP4 remediation -- sourced but never referenced in transformation SQL or output).

### FSD-AOH-002: Accounts Source Configuration
Source `datalake.accounts` with columns: `account_id`, `account_type`.

**Traces to:** BRD-AOH-002, BRD-AOH-003
**Change from V1:** Removed `customer_id`, `account_status`, `interest_rate`, `credit_limit` (AP4 remediation -- sourced but only `account_type` and `account_id` are used in the JOIN/SELECT).

---

## Transformation

### FSD-AOH-003: SQL Transformation
Join overdraft events to accounts on `account_id` and `ifw_effective_date`, selecting overdraft details enriched with `account_type`.

```sql
SELECT oe.overdraft_id, oe.account_id, oe.customer_id, a.account_type,
       oe.overdraft_amount, oe.fee_amount, oe.fee_waived, oe.ifw_effective_date
FROM overdraft_events oe
JOIN accounts a ON oe.account_id = a.account_id AND oe.ifw_effective_date = a.ifw_effective_date
ORDER BY oe.ifw_effective_date, oe.overdraft_id
```

**Traces to:** BRD-AOH-004, BRD-AOH-005, BRD-AOH-006
**Change from V1:** None. SQL is identical -- the SELECT list and JOIN logic are unchanged. AP4 remediation only affects DataSourcing columns, not the transformation.

**Output equivalence:** Byte-identical. DataSourcing column removal does not affect transformation output since removed columns were never referenced in SQL.

### FSD-AOH-004: No External Module Required
The job requires no C# External module. All logic is expressible in SQL.

**Traces to:** BRD-AOH-004, BRD-AOH-005
**DELIV-05 note:** Satisfied trivially -- no external module exists in V1, none needed in RE.

---

## Output

### FSD-AOH-005: Parquet Writer Configuration
- `numParts: 50` (BRD-AOH-007)
- `writeMode: Overwrite` (BRD-AOH-011)
- `outputDirectory: {ETL_RE_OUTPUT}` (BRD-AOH-010)
- `jobDirName: account_overdraft_history`
- `fileName: account_overdraft_history`
- `outputTableDirName: account_overdraft_history`

**Traces to:** BRD-AOH-007 through BRD-AOH-011
**Change from V1:** `outputDirectory` changed from `Output/curated` to `{ETL_RE_OUTPUT}` to write to RE output tree instead of V1 output tree.

### FSD-AOH-006: Output Schema
9 columns: `overdraft_id`, `account_id`, `customer_id`, `account_type`, `overdraft_amount`, `fee_amount`, `fee_waived`, `ifw_effective_date`, `etl_effective_date`.

**Traces to:** BRD-AOH-008
**Change from V1:** None. Column list and order are identical. `etl_effective_date` is appended automatically by the framework.
