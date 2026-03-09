# SecuritiesDirectory — Business Requirements Document

**Job ID:** 110
**Source Job Conf:** `MockEtlFramework/JobExecutor/Jobs/securities_directory.json`

---

## Requirements

### BRD-1: Securities Reference Output
The system shall produce a daily securities directory listing all securities with their identifying attributes (security_id, ticker, security_name, security_type, sector, exchange).

**Evidence:** Transformation SQL selects these 6 columns plus ifw_effective_date from the `securities` DataSourcing result. Output is 50 rows (one per security), stable across all 92 dates.

### BRD-2: Daily Date Stamping
Each output row shall include the effective date of the ETL run as both `ifw_effective_date` (sourced from datalake) and `etl_effective_date` (auto-added by CsvFileWriter).

**Evidence:** Output CSV has 8 columns: the 6 securities fields plus these two date columns, both matching the run date.

### BRD-3: Ordered Output
Output rows shall be ordered by `security_id` ascending.

**Evidence:** Transformation SQL contains `ORDER BY s.security_id`.

### BRD-4: CSV Format
Output shall be CSV with header row, LF line endings, no trailer.

**Evidence:** Writer config: `includeHeader: true`, `lineEnding: "LF"`, `writeMode: "Overwrite"`.

### BRD-5: Overwrite Mode
Each date's output is independent — no accumulation across dates.

**Evidence:** `writeMode: "Overwrite"` in writer config.

---

## Anti-Patterns Identified

### AP1 — Dead-End Sourcing
The V1 config sources the `holdings` table (holding_id, investment_id, security_id, customer_id, quantity, current_value) but never references `holdings` in the Transformation SQL. This is pure wasted I/O.

**Remediation:** Remove the `holdings` DataSourcing module entirely from the RE config.
