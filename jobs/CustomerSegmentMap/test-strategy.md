# CustomerSegmentMap -- Test Strategy

**Job:** CustomerSegmentMap_RE
**Traces to:** FSD (jobs/CustomerSegmentMap/FSD.md), BRD (jobs/CustomerSegmentMap/BRD.md)

---

## Primary Validation

### Proofmark Byte-Identical Comparison
**Method:** Proofmark CSV comparison across all 92 effective dates.

**Config:** `proofmark-configs/CustomerSegmentMap.yaml` (header_rows: 1, trailer_rows: 0)

**LHS (V1):** `{ETL_ROOT}/Output/curated/customer_segment_map/customer_segment_map/{date}/customer_segment_map.csv`
**RHS (RE):** `{ETL_RE_OUTPUT}/customer_segment_map/customer_segment_map/{date}/customer_segment_map.csv`

**Pass criteria:** 92/92 PASS.

---

## Coverage Matrix

| Dimension | Coverage | Notes |
|-----------|----------|-------|
| Effective dates | 92/92 | Oct 1 - Dec 31, 2024 |
| Data rows on Oct 1 | 2982 | Customer-segment pairs |
| Data rows on Dec 31 | 274344 | 2982 * 92 cumulative |
| Columns | 6 | customer_id + segment_id + segment_name + segment_code + ifw_effective_date + etl_effective_date |
| Line endings | LF | Per V1 conf |
| Header | Present | Single header row |
| Trailer | None | No trailer |

---

## Traceability

| Test Aspect | Traces to FSD | Traces to BRD |
|-------------|---------------|---------------|
| Row content match | FSD-CSM-002 | BRD-CSM-005, BRD-CSM-006 |
| Column schema match | FSD-CSM-005 | BRD-CSM-010 |
| Cumulative row count | FSD-CSM-004 | BRD-CSM-011 |
| AP1 remediation safe | FSD-CSM-001 | BRD-CSM-003 |

---

## Risk Assessment

**Low risk.** AP1 remediation removes dead `branches` sourcing that was never referenced in SQL. The JOIN between `customers_segments` and `segments` is straightforward. Output is unaffected by removing the dead sourcing.
