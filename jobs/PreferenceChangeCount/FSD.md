# PreferenceChangeCount — Functional Specification Document

**Job:** PreferenceChangeCount_RE
**Traces to:** BRD (jobs/PreferenceChangeCount/BRD.md)

---

## Data Sourcing

### FSD-PCC-001: Customer Preferences Source Configuration
Source `datalake.customer_preferences` with columns: `preference_id`, `customer_id`, `preference_type`, `opted_in`.

**Traces to:** BRD-PCC-001, BRD-PCC-003
**Change from V1:** Removed `updated_date` (AP4 remediation -- sourced but never referenced in transformation SQL or output).

### FSD-PCC-002: Customers Source Removed (AP1 Remediation)
V1 sourced `datalake.customers` with columns `id`, `prefix`, `first_name`, `last_name`. No columns from this table are referenced anywhere in the transformation SQL -- no JOIN condition, no WHERE clause, no SELECT. This is a complete dead-end source.

**Traces to:** BRD-PCC-002
**Change from V1:** Entire DataSourcing module removed. The customers table contributes nothing to the output. Same pattern as SecuritiesDirectory (dead holdings source) and TransactionSizeBuckets (dead accounts source).

---

## Transformation

### FSD-PCC-003: SQL Transformation
Aggregate customer preferences by customer_id, computing preference count and opt-in flags for email and SMS marketing.

```sql
WITH all_prefs AS (
  SELECT cp.customer_id, cp.preference_type, cp.opted_in, cp.ifw_effective_date
  FROM customer_preferences cp
),
summary AS (
  SELECT customer_id,
         COUNT(*) AS preference_count,
         MAX(CASE WHEN preference_type = 'MARKETING_EMAIL' AND opted_in = 1 THEN 1 ELSE 0 END) AS has_email_opt_in,
         MAX(CASE WHEN preference_type = 'MARKETING_SMS' AND opted_in = 1 THEN 1 ELSE 0 END) AS has_sms_opt_in,
         ifw_effective_date
  FROM all_prefs
  GROUP BY customer_id, ifw_effective_date
)
SELECT s.customer_id, s.preference_count, s.has_email_opt_in, s.has_sms_opt_in, s.ifw_effective_date
FROM summary s
```

**Traces to:** BRD-PCC-004, BRD-PCC-005, BRD-PCC-006, BRD-PCC-007
**Change from V1:** Removed `RANK() OVER (PARTITION BY cp.customer_id, cp.preference_type ORDER BY cp.preference_id) AS rnk` from the `all_prefs` CTE (AP8 remediation). The rank value was computed but never consumed -- not used in any WHERE clause, not in output, not referenced downstream. Removing it has no effect on the output.

**Output equivalence:** Byte-identical. The RANK() produced a column (`rnk`) that was immediately discarded by the downstream query. Removing it is functionally equivalent.

### FSD-PCC-004: No External Module Required
The job requires no C# External module. All logic is expressible in SQL.

**Traces to:** BRD-PCC-004 through BRD-PCC-006
**DELIV-05 note:** Satisfied trivially -- no external module exists in V1, none needed in RE.

---

## Output

### FSD-PCC-005: Parquet Writer Configuration
- `numParts: 1` (BRD-PCC-008) -- CRITICAL: only 1 partition, not 50
- `writeMode: Overwrite` (BRD-PCC-012)
- `outputDirectory: {ETL_RE_OUTPUT}` (BRD-PCC-011)
- `jobDirName: preference_change_count`
- `fileName: preference_change_count`
- `outputTableDirName: preference_change_count`

**Traces to:** BRD-PCC-008 through BRD-PCC-012
**Change from V1:** `outputDirectory` changed from `Output/curated` to `{ETL_RE_OUTPUT}` to write to RE output tree instead of V1 output tree.

### FSD-PCC-006: Output Schema
6 columns: `customer_id`, `preference_count`, `has_email_opt_in`, `has_sms_opt_in`, `ifw_effective_date`, `etl_effective_date`.

**Traces to:** BRD-PCC-009
**Change from V1:** None. Column list and order are identical. `etl_effective_date` is appended automatically by the framework.
