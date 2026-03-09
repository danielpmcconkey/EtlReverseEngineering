# CardStatusSnapshot -- Business Requirements Document

**Job:** CardStatusSnapshot
**Source V1 conf:** `/workspace/MockEtlFramework/JobExecutor/Jobs/card_status_snapshot.json`
**Effective dates:** 2024-10-01 through 2024-12-31 (92 dates)

---

## Data Source

### BRD-CSS-001: Source Table
The job sources from `datalake.cards` with 6 columns: `card_id`, `customer_id`, `card_type`, `card_number_masked`, `expiration_date`, `card_status`.

**Evidence:** V1 job conf `DataSourcing` module specifies schema `datalake`, table `cards`, with these exact 6 columns.

### BRD-CSS-002: Effective Date Scoping
Data is scoped to a single effective date per execution. The framework injects `ifw_effective_date` filtering at the DataSourcing layer.

**Evidence:** V1 output for any given date contains only rows where `ifw_effective_date` matches the execution date.

---

## Business Rules

### BRD-CSS-003: Aggregation by Card Status
Output is aggregated by `card_status`, producing one row per distinct card_status value with:
- `card_count`: count of cards in that status

**Evidence:** V1 SQL `GROUP BY c.card_status, c.ifw_effective_date`. Output contains 3 data rows per date (3 distinct card statuses).

### BRD-CSS-004: Card Count Calculation
Card count per group is `COUNT(*)` -- the number of cards with each status for that effective date.

**Evidence:** V1 SQL `COUNT(*) AS card_count`.

### BRD-CSS-005: No Ordering Specified
V1 SQL does not include an explicit ORDER BY. Row order within the output depends on the execution engine's GROUP BY implementation.

**Evidence:** V1 SQL has GROUP BY but no ORDER BY clause.

### BRD-CSS-006: ifw_effective_date from Source
The `ifw_effective_date` column in the output comes from the cards table (injected by the framework at DataSourcing).

**Evidence:** V1 SQL accesses `c.ifw_effective_date` and groups by it.

---

## Output Format

### BRD-CSS-007: File Format
Output is Parquet format with 50 part files per date directory.

**Evidence:** V1 job conf `ParquetFileWriter` with `numParts: 50`.

### BRD-CSS-008: Column Schema
Output contains 4 columns: `card_status`, `card_count`, `ifw_effective_date`, `etl_effective_date`.

**Evidence:** V1 SQL SELECT produces `card_status`, `card_count`, `ifw_effective_date`. The framework auto-appends `etl_effective_date`.

### BRD-CSS-009: Row Count
Output contains exactly 3 data rows per date (one per card_status value).

**Evidence:** V1 output inspection across multiple dates confirms 3 rows consistently. This means 3 rows spread across 50 part files -- massively over-partitioned but correct per V1.

### BRD-CSS-010: Output Path
Output path follows the pattern: `{outputDirectory}/card_status_snapshot/card_status_snapshot/{YYYY-MM-DD}/card_status_snapshot/part-*.parquet`.

**Evidence:** V1 job conf `ParquetFileWriter` specifies `jobDirName: card_status_snapshot`, `outputTableDirName: card_status_snapshot`, `fileName: card_status_snapshot`. The `fileName` is a directory name containing part-*.parquet files.

### BRD-CSS-011: Write Mode
Output uses Overwrite mode -- each execution replaces any existing directory for that date.

**Evidence:** V1 job conf `writeMode: Overwrite`.

### BRD-CSS-012: Part File Count
Exactly 50 part files (`part-00000.parquet` through `part-00049.parquet`) regardless of data volume. With only 3 rows, most part files contain 0 rows.

**Evidence:** V1 output directory listing shows 50 part files. V1 conf `numParts: 50`.
