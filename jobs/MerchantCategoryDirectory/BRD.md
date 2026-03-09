# MerchantCategoryDirectory -- Business Requirements Document

**Job:** MerchantCategoryDirectory
**Source V1 conf:** `/workspace/MockEtlFramework/JobExecutor/Jobs/merchant_category_directory.json`
**Effective dates:** 2024-10-01 through 2024-12-31 (92 dates)
**Write mode:** Append (cumulative output)

---

## Data Sources

### BRD-MCD-001: Primary Source Table
The job sources from `datalake.merchant_categories` with 3 columns: `mcc_code`, `mcc_description`, `risk_level`.

**Evidence:** V1 job conf `DataSourcing` module specifies schema `datalake`, table `merchant_categories`, with these exact 3 columns.

### BRD-MCD-002: Dead-End Source (AP1)
The V1 job conf also sources `datalake.cards` with 3 columns: `card_id`, `customer_id`, `card_type`. However, the SQL transformation never references the `cards` result set -- the SELECT only uses `merchant_categories mc`. This is dead-end sourcing (AP1).

**Evidence:** V1 SQL: `SELECT mc.mcc_code, mc.mcc_description, mc.risk_level, mc.ifw_effective_date FROM merchant_categories mc`. No reference to `cards` anywhere in the query.

### BRD-MCD-003: Effective Date Scoping
Data is scoped to a single effective date per execution via standard framework injection.

**Evidence:** No min/max overrides in V1 DataSourcing.

---

## Business Rules

### BRD-MCD-004: Merchant Category Listing
The output is a simple listing of merchant categories with their MCC code, description, and risk level. No aggregation, no joins, no filtering beyond effective date scoping.

**Evidence:** V1 SQL is a direct SELECT from `merchant_categories` with no WHERE, GROUP BY, or JOIN.

### BRD-MCD-005: Row Count Per Execution
Each execution produces 20 data rows (one per merchant category).

**Evidence:** V1 output for 2024-10-01 has 20 data rows (21 lines with header). Dec 31 has 1840 data rows (20 * 92 cumulative).

---

## Output Format

### BRD-MCD-006: File Format
Output is CSV with LF line endings, comma-delimited, no quoting.

**Evidence:** V1 job conf `CsvFileWriter` specifies `lineEnding: LF`, `includeHeader: true`.

### BRD-MCD-007: Header Row
Output includes a single header row: `mcc_code,mcc_description,risk_level,ifw_effective_date,etl_effective_date`.

**Evidence:** V1 output first line confirmed.

### BRD-MCD-008: Column Schema
Output contains 5 columns: `mcc_code`, `mcc_description`, `risk_level`, `ifw_effective_date`, `etl_effective_date`.

**Evidence:** V1 output header. First 3 are source columns, `ifw_effective_date` from the SQL SELECT, `etl_effective_date` is framework auto-append.

### BRD-MCD-009: Cumulative Row Count (Append Mode)
Row count grows cumulatively: 20 data rows on date 1, 40 on date 2, ..., 1840 on date 92. Total lines = 1 (header) + 20 * (date ordinal).

**Evidence:** V1 output: Oct 1 = 21 lines, Dec 31 = 1841 lines.

### BRD-MCD-010: No Trailer
No trailer row.

**Evidence:** V1 output last line is data. No trailer configuration.

### BRD-MCD-011: Output Path
Output path: `{outputDirectory}/merchant_category_directory/merchant_category_directory/{YYYY-MM-DD}/merchant_category_directory.csv`.

**Evidence:** V1 job conf `CsvFileWriter` specifies matching directory/file names.

### BRD-MCD-012: Write Mode
Output uses Append mode.

**Evidence:** V1 job conf `writeMode: Append`.
