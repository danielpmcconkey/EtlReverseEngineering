# MerchantCategoryDirectory -- Functional Specification Document

**Job:** MerchantCategoryDirectory_RE
**Traces to:** BRD (jobs/MerchantCategoryDirectory/BRD.md)

---

## Data Sourcing

### FSD-MCD-001: Source Configuration
Source `datalake.merchant_categories` with columns: `mcc_code`, `mcc_description`, `risk_level`. Standard effective date scoping.

**Traces to:** BRD-MCD-001, BRD-MCD-003
**Change from V1:** Removed `datalake.cards` DataSourcing module (AP1 remediation). The `cards` result set was never referenced in the SQL transformation. See BRD-MCD-002.

---

## Transformation

### FSD-MCD-002: SQL Transformation
Direct listing of merchant categories:

```sql
SELECT mc.mcc_code, mc.mcc_description, mc.risk_level, mc.ifw_effective_date FROM merchant_categories mc
```

**Traces to:** BRD-MCD-004, BRD-MCD-005
**Change from V1:** None. SQL is identical (it never referenced `cards`).

### FSD-MCD-003: No External Module Required
All logic is expressible in SQL.

**Traces to:** BRD-MCD-004
**DELIV-05 note:** Satisfied trivially.

---

## Output

### FSD-MCD-004: CSV Writer Configuration
- `includeHeader: true` (BRD-MCD-007)
- `writeMode: Append` (BRD-MCD-012)
- `lineEnding: LF` (BRD-MCD-006)
- `outputDirectory: {ETL_RE_OUTPUT}` (BRD-MCD-011)
- `jobDirName: merchant_category_directory`
- `fileName: merchant_category_directory.csv`
- `outputTableDirName: merchant_category_directory`

**Traces to:** BRD-MCD-006 through BRD-MCD-012
**Change from V1:** `outputDirectory` changed to `{ETL_RE_OUTPUT}`.

### FSD-MCD-005: Output Schema
5 columns: `mcc_code`, `mcc_description`, `risk_level`, `ifw_effective_date`, `etl_effective_date`.

**Traces to:** BRD-MCD-008
**Change from V1:** None.
