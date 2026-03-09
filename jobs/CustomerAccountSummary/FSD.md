# CustomerAccountSummary -- Functional Specification Document

**Job:** CustomerAccountSummary_RE
**Traces to:** BRD (jobs/CustomerAccountSummary/BRD.md)

---

## Data Sourcing

### FSD-CAS-001: Customers Source Configuration
Source `datalake.customers` with columns: `id`, `first_name`, `last_name`.

**Traces to:** BRD-CAS-001, BRD-CAS-003
**Change from V1:** None. DataSourcing module is identical.

### FSD-CAS-002: Accounts Source Configuration
Source `datalake.accounts` with columns: `account_id`, `customer_id`, `account_type`, `account_status`, `current_balance`.

**Traces to:** BRD-CAS-002, BRD-CAS-003
**Change from V1:** None. DataSourcing module is identical.

---

## Transformation

### FSD-CAS-003: SQL Transformation
LEFT JOIN customers to accounts on `c.id = a.customer_id`. Group by customer, compute account count and active balance sum.

```sql
SELECT c.id AS customer_id, c.first_name, c.last_name,
       COUNT(a.account_id) AS account_count,
       ROUND(SUM(CASE WHEN a.account_status = 'Active' THEN a.current_balance ELSE 0 END), 2) AS active_balance
FROM customers c
LEFT JOIN accounts a ON c.id = a.customer_id
GROUP BY c.id, c.first_name, c.last_name
ORDER BY c.id
```

**Traces to:** BRD-CAS-004, BRD-CAS-005, BRD-CAS-006
**Change from V1:** None. SQL is identical to V1. No anti-patterns requiring remediation.

### FSD-CAS-004: No External Module Required
The job requires no C# External module. All logic is expressible in SQL. The existing `CustomerAccountSummaryBuilder.cs` in ExternalModules is not used by V1 and is ignored.

**Traces to:** BRD-CAS-014
**DELIV-05 note:** Satisfied trivially -- no external module in V1 conf, none needed in RE.

---

## Output

### FSD-CAS-005: CSV Writer Configuration
- `includeHeader: true` (BRD-CAS-008)
- `writeMode: Overwrite` (BRD-CAS-013)
- `lineEnding: LF` (BRD-CAS-007)
- `outputDirectory: {ETL_RE_OUTPUT}` (BRD-CAS-012)
- `jobDirName: customer_account_summary`
- `fileName: customer_account_summary.csv`
- `outputTableDirName: customer_account_summary`

**Traces to:** BRD-CAS-007 through BRD-CAS-013
**Change from V1:** `outputDirectory` changed from `Output/curated` to `{ETL_RE_OUTPUT}` to write to RE output tree.

### FSD-CAS-006: Output Schema
6 columns: `customer_id`, `first_name`, `last_name`, `account_count`, `active_balance`, `etl_effective_date`.

**Traces to:** BRD-CAS-009
**Change from V1:** None. Column list and order are identical. `etl_effective_date` is appended automatically by the framework.
