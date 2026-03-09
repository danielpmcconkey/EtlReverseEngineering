# SecuritiesDirectory — Functional Specification Document

**Traces to:** BRD.md in this directory

---

## Specifications

### FSD-1: Data Sourcing (traces to BRD-1)
Source a single table: `datalake.securities` with columns: security_id, ticker, security_name, security_type, sector, exchange. The framework auto-includes `ifw_effective_date`.

**Change from V1:** Removed `holdings` DataSourcing module (AP1 remediation).

### FSD-2: Transformation (traces to BRD-1, BRD-2, BRD-3)
SQL: `SELECT s.security_id, s.ticker, s.security_name, s.security_type, s.sector, s.exchange, s.ifw_effective_date FROM securities s ORDER BY s.security_id`

No change from V1. The SQL is clean — no anti-patterns in the query itself.

### FSD-3: Writer Configuration (traces to BRD-4, BRD-5)
- Type: CsvFileWriter
- Source: `securities_dir` (transformation result)
- Header: yes
- Write mode: Overwrite
- Line ending: LF
- Output path: `Output/curated_re/securities_directory/securities_directory/{date}/securities_directory.csv`

**Change from V1:** Output directory is `curated_re` instead of `curated`.

### FSD-4: Expected Output Shape (traces to BRD-1, BRD-2)
- 51 lines per file (1 header + 50 data rows)
- 8 columns: security_id, ticker, security_name, security_type, sector, exchange, ifw_effective_date, etl_effective_date
- Deterministic across all 92 dates (only date columns change)
