# FeeWaiverAnalysis -- Test Strategy

**Job:** FeeWaiverAnalysis_RE
**Traces to:** FSD (jobs/FeeWaiverAnalysis/FSD.md), BRD (jobs/FeeWaiverAnalysis/BRD.md)

---

## Primary Validation

### Proofmark Byte-Identical Comparison
**Method:** Proofmark CSV comparison across all 92 effective dates (2024-10-01 through 2024-12-31).

**Config:** `proofmark-configs/FeeWaiverAnalysis.yaml` (header_rows: 1, trailer_rows: 0)

**LHS (V1):** `{ETL_ROOT}/Output/curated/fee_waiver_analysis/fee_waiver_analysis/{date}/fee_waiver_analysis.csv`
**RHS (RE):** `{ETL_RE_OUTPUT}/fee_waiver_analysis/fee_waiver_analysis/{date}/fee_waiver_analysis.csv`

**Pass criteria:** 92/92 PASS. Zero tolerance for differences.

**Trailer handling:** No trailer in this job. Proofmark config uses `trailer_rows: 0`.

---

## Coverage Matrix

| Dimension | Coverage | Notes |
|-----------|----------|-------|
| Effective dates | 92/92 | Oct 1 - Dec 31, 2024 |
| Data rows per date | 1-2 | One per fee_waived value (0 and/or 1) |
| Columns | 6 | 5 from SQL + etl_effective_date |
| Line endings | LF | Verified via V1 conf |
| Header | Present | Single header row |
| Trailer | None | V1 has no trailerFormat |

---

## Traceability

| Test Aspect | Traces to FSD | Traces to BRD |
|-------------|---------------|---------------|
| Row content match | FSD-FWA-003 | BRD-FWA-006, BRD-FWA-007 |
| Column schema match | FSD-FWA-006 | BRD-FWA-012 |
| Header presence | FSD-FWA-005 | BRD-FWA-011 |
| Line ending format | FSD-FWA-005 | BRD-FWA-010 |
| Row count | FSD-FWA-003 | BRD-FWA-013 |
| Output path | FSD-FWA-005 | BRD-FWA-014 |
| Ordering | FSD-FWA-003 | BRD-FWA-008 |
| LEFT JOIN disposition | FSD-FWA-003 | BRD-FWA-005 |

---

## Risk Assessment

**Low risk.** FeeWaiverAnalysis has a suspicious LEFT JOIN that warranted investigation, but the investigation confirmed it is harmless:
- No duplicate (account_id, ifw_effective_date) pairs in accounts -- JOIN does not inflate counts
- LEFT JOIN retained in RE for safety -- removing it would produce identical output
- AP4 remediation removes unused columns from both DataSourcing modules -- cannot affect SQL output
- Null-safe CASE WHEN for fee_amount preserved exactly as V1
- Key lesson from ComplianceResolutionTime (Phase 1): always verify JOIN impact before removing
