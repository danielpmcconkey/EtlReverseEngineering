# DailyWireVolume -- Test Strategy

**Job:** DailyWireVolume_RE
**Traces to:** FSD (jobs/DailyWireVolume/FSD.md), BRD (jobs/DailyWireVolume/BRD.md)

---

## Primary Validation

### Proofmark Byte-Identical Comparison
**Method:** Proofmark CSV comparison across all 92 effective dates (2024-10-01 through 2024-12-31).

**Config:** `proofmark-configs/DailyWireVolume.yaml` (header_rows: 1, trailer_rows: 0)

**LHS (V1):** `{ETL_ROOT}/Output/curated/daily_wire_volume/daily_wire_volume/{date}/daily_wire_volume.csv`
**RHS (RE):** `{ETL_RE_OUTPUT}/daily_wire_volume/daily_wire_volume/{date}/daily_wire_volume.csv`

**Pass criteria:** 92/92 PASS. Zero tolerance for differences.

---

## Coverage Matrix

| Dimension | Coverage | Notes |
|-----------|----------|-------|
| Effective dates | 92/92 | Oct 1 - Dec 31, 2024 |
| Data rows on Oct 1 | 92 | Full date range aggregated |
| Data rows on Dec 31 | 8464 | 92 * 92 cumulative (Append mode) |
| Columns | 5 | wire_date + wire_count + total_amount + ifw_effective_date + etl_effective_date |
| Line endings | LF | Verified via V1 conf |
| Header | Present | Single header row |
| Trailer | None | No trailer in V1 output |

---

## Traceability

| Test Aspect | Traces to FSD | Traces to BRD |
|-------------|---------------|---------------|
| Row content match | FSD-DWV-002 | BRD-DWV-003, BRD-DWV-004 |
| Column schema match | FSD-DWV-005 | BRD-DWV-008 |
| Header presence | FSD-DWV-004 | BRD-DWV-007 |
| Line ending format | FSD-DWV-004 | BRD-DWV-006 |
| Cumulative row count | FSD-DWV-004 | BRD-DWV-009 |
| No trailer | FSD-DWV-004 | BRD-DWV-010 |
| Output path | FSD-DWV-004 | BRD-DWV-011 |
| Append mode behavior | FSD-DWV-004 | BRD-DWV-012 |

---

## Risk Assessment

**Low risk.** DailyWireVolume is the simplest Append mode job:
- Single source table, no joins
- Simple GROUP BY aggregation
- Constant 92 rows per execution (full range query)
- No trailer, no special DataSourcing features
- AP10 identified but retained (redundant WHERE clause is harmless)
