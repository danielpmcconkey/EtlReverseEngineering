# SecuritiesDirectory -- Functional Specification Document

**Job:** SecuritiesDirectory_RE
**Traces to:** BRD (jobs/SecuritiesDirectory/BRD.md)

---

## Data Sourcing

### FSD-SD-001: Securities Source Configuration
Source `datalake.securities` with columns: `security_id`, `ticker`, `security_name`, `security_type`, `sector`, `exchange`.

**Traces to:** BRD-SD-001, BRD-SD-003
**Change from V1:** None. DataSourcing module is identical.

### FSD-SD-002: Holdings Source Removed (AP1 Remediation)
V1 sourced `datalake.holdings` but never referenced it in the SQL. The entire holdings DataSourcing module is removed in the RE job conf.

**Traces to:** BRD-SD-002
**Change from V1:** Holdings DataSourcing module removed. This eliminates unnecessary data loading with zero impact on output.

---

## Transformation

### FSD-SD-003: SQL Transformation
Select all 6 source columns plus `ifw_effective_date`, ordered by `security_id` ascending.

```sql
SELECT s.security_id, s.ticker, s.security_name, s.security_type, s.sector, s.exchange, s.ifw_effective_date
FROM securities s
ORDER BY s.security_id
```

**Traces to:** BRD-SD-004, BRD-SD-005
**Change from V1:** None. SQL is identical to V1. The holdings removal is in DataSourcing only -- the SQL never referenced holdings.

### FSD-SD-004: No External Module Required
The job requires no C# External module. All logic is expressible in SQL.

**Traces to:** BRD-SD-004
**DELIV-05 note:** Satisfied trivially -- no external module exists in V1, none needed in RE.

---

## Output

### FSD-SD-005: CSV Writer Configuration
- `includeHeader: true` (BRD-SD-007)
- `writeMode: Overwrite` (BRD-SD-012)
- `lineEnding: LF` (BRD-SD-006)
- `outputDirectory: {ETL_RE_OUTPUT}` (BRD-SD-011)
- `jobDirName: securities_directory`
- `fileName: securities_directory.csv`
- `outputTableDirName: securities_directory`

**Traces to:** BRD-SD-006 through BRD-SD-012
**Change from V1:** `outputDirectory` changed from `Output/curated` to `{ETL_RE_OUTPUT}` to write to RE output tree.

### FSD-SD-006: Output Schema
8 columns: `security_id`, `ticker`, `security_name`, `security_type`, `sector`, `exchange`, `ifw_effective_date`, `etl_effective_date`.

**Traces to:** BRD-SD-008
**Change from V1:** None. Column list and order are identical. `etl_effective_date` is appended automatically by the framework.
