# PreferenceChangeCount — Business Requirements Document

**Job:** PreferenceChangeCount
**Source V1 conf:** `/workspace/MockEtlFramework/JobExecutor/Jobs/preference_change_count.json`
**Effective dates:** 2024-10-01 through 2024-12-31 (92 dates)

---

## Data Sources

### BRD-PCC-001: Customer Preferences Source
The job sources from `datalake.customer_preferences` with 5 columns: `preference_id`, `customer_id`, `preference_type`, `opted_in`, `updated_date`.

**Evidence:** V1 job conf `DataSourcing` module specifies schema `datalake`, table `customer_preferences`, with these exact 5 columns.

### BRD-PCC-002: Customers Source (Dead-End)
The job sources from `datalake.customers` with 4 columns: `id`, `prefix`, `first_name`, `last_name`.

**Evidence:** V1 job conf second `DataSourcing` module specifies schema `datalake`, table `customers`, with these exact 4 columns. However, NO columns from this table are referenced anywhere in the transformation SQL. This is a dead-end source (AP1).

### BRD-PCC-003: Effective Date Scoping
Data is scoped to a single effective date per execution. The framework injects `ifw_effective_date` filtering at the DataSourcing layer.

**Evidence:** V1 output for any given date contains only rows where `ifw_effective_date` matches the execution date.

---

## Business Rules

### BRD-PCC-004: Preference Count per Customer
For each customer, count the total number of preference records for that effective date.

**Evidence:** V1 SQL: `COUNT(*) AS preference_count` in a `GROUP BY customer_id, ifw_effective_date`.

### BRD-PCC-005: Email Opt-In Flag
For each customer, determine if they have opted into marketing email. Value is 1 if any preference record has `preference_type = 'MARKETING_EMAIL'` and `opted_in = 1`, otherwise 0.

**Evidence:** V1 SQL: `MAX(CASE WHEN preference_type = 'MARKETING_EMAIL' AND opted_in = 1 THEN 1 ELSE 0 END) AS has_email_opt_in`.

### BRD-PCC-006: SMS Opt-In Flag
For each customer, determine if they have opted into marketing SMS. Value is 1 if any preference record has `preference_type = 'MARKETING_SMS'` and `opted_in = 1`, otherwise 0.

**Evidence:** V1 SQL: `MAX(CASE WHEN preference_type = 'MARKETING_SMS' AND opted_in = 1 THEN 1 ELSE 0 END) AS has_sms_opt_in`.

### BRD-PCC-007: Dead RANK Computation (V1 Artifact)
V1 SQL computes `RANK() OVER (PARTITION BY customer_id, preference_type ORDER BY preference_id) AS rnk` but the `rnk` column is never used for filtering, output, or any downstream computation. This is dead computation (AP8).

**Evidence:** V1 SQL defines `rnk` in the `all_prefs` CTE but the `summary` CTE and final SELECT never reference `rnk`. The RANK() function runs but its output is discarded.

---

## Output Format

### BRD-PCC-008: File Format
Output is Parquet format with 1 partition.

**Evidence:** V1 job conf uses `ParquetFileWriter` with `numParts: 1`. This is the only Tier 2 Parquet job with a single partition (all others use 50).

### BRD-PCC-009: Column Schema
Output contains 6 columns in this order: `customer_id`, `preference_count`, `has_email_opt_in`, `has_sms_opt_in`, `ifw_effective_date`, `etl_effective_date`.

**Evidence:** V1 SQL SELECT list. `etl_effective_date` is appended automatically by the framework.

### BRD-PCC-010: Row Count
Output contains 2230 data rows per effective date (stable across all dates).

**Evidence:** V1 output inspection shows consistent 2230 rows (one per customer with preferences).

### BRD-PCC-011: Output Path
Output path follows the pattern: `{outputDirectory}/preference_change_count/preference_change_count/{YYYY-MM-DD}/preference_change_count/` (directory containing `part-*.parquet` files).

**Evidence:** V1 job conf `ParquetFileWriter` specifies `jobDirName: preference_change_count`, `outputTableDirName: preference_change_count`, `fileName: preference_change_count`.

### BRD-PCC-012: Write Mode
Output uses Overwrite mode -- each execution replaces any existing output for that date.

**Evidence:** V1 job conf `writeMode: Overwrite`.
