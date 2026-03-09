# PreferenceTrend -- Test Strategy

**Job:** PreferenceTrend_RE
**Traces to:** FSD (jobs/PreferenceTrend/FSD.md), BRD (jobs/PreferenceTrend/BRD.md)

---

## Primary Validation

### Proofmark Byte-Identical Comparison
**Method:** Proofmark CSV comparison across all 92 effective dates.

**Config:** `proofmark-configs/PreferenceTrend.yaml` (header_rows: 1, trailer_rows: 0)

**LHS (V1):** `{ETL_ROOT}/Output/curated/preference_trend/preference_trend/{date}/preference_trend.csv`
**RHS (RE):** `{ETL_RE_OUTPUT}/preference_trend/preference_trend/{date}/preference_trend.csv`

**Pass criteria:** 92/92 PASS.

---

## Coverage Matrix

| Dimension | Coverage | Notes |
|-----------|----------|-------|
| Effective dates | 92/92 | Oct 1 - Dec 31, 2024 |
| Data rows on Oct 1 | 5 | 5 preference types |
| Data rows on Dec 31 | 460 | 5 * 92 cumulative (Append mode) |
| Columns | 5 | preference_type + opted_in_count + opted_out_count + ifw_effective_date + etl_effective_date |
| Line endings | LF | Per V1 conf |
| Header | Present | Single header row |
| Trailer | None | No trailer |

---

## Traceability

| Test Aspect | Traces to FSD | Traces to BRD |
|-------------|---------------|---------------|
| Row content match | FSD-PT-002 | BRD-PT-003, BRD-PT-004 |
| Column schema match | FSD-PT-005 | BRD-PT-008 |
| Header presence | FSD-PT-004 | BRD-PT-007 |
| Line ending format | FSD-PT-004 | BRD-PT-006 |
| Cumulative row count | FSD-PT-004 | BRD-PT-009 |
| No trailer | FSD-PT-004 | BRD-PT-010 |
| Append mode behavior | FSD-PT-004 | BRD-PT-012 |

---

## Risk Assessment

**Low risk.** Single source, simple GROUP BY, no joins, no trailer, no special features. Identical SQL to V1.
