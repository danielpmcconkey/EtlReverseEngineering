# MerchantCategoryDirectory -- Test Strategy

**Job:** MerchantCategoryDirectory_RE
**Traces to:** FSD (jobs/MerchantCategoryDirectory/FSD.md), BRD (jobs/MerchantCategoryDirectory/BRD.md)

---

## Primary Validation

### Proofmark Byte-Identical Comparison
**Method:** Proofmark CSV comparison across all 92 effective dates.

**Config:** `proofmark-configs/MerchantCategoryDirectory.yaml` (header_rows: 1, trailer_rows: 0)

**LHS (V1):** `{ETL_ROOT}/Output/curated/merchant_category_directory/merchant_category_directory/{date}/merchant_category_directory.csv`
**RHS (RE):** `{ETL_RE_OUTPUT}/merchant_category_directory/merchant_category_directory/{date}/merchant_category_directory.csv`

**Pass criteria:** 92/92 PASS.

---

## Coverage Matrix

| Dimension | Coverage | Notes |
|-----------|----------|-------|
| Effective dates | 92/92 | Oct 1 - Dec 31, 2024 |
| Data rows on Oct 1 | 20 | 20 merchant categories |
| Data rows on Dec 31 | 1840 | 20 * 92 cumulative |
| Columns | 5 | mcc_code + mcc_description + risk_level + ifw_effective_date + etl_effective_date |
| Line endings | LF | Per V1 conf |
| Header | Present | Single header row |
| Trailer | None | No trailer |

---

## Traceability

| Test Aspect | Traces to FSD | Traces to BRD |
|-------------|---------------|---------------|
| Row content match | FSD-MCD-002 | BRD-MCD-004, BRD-MCD-005 |
| Column schema match | FSD-MCD-005 | BRD-MCD-008 |
| Cumulative row count | FSD-MCD-004 | BRD-MCD-009 |
| AP1 remediation safe | FSD-MCD-001 | BRD-MCD-002 |

---

## Risk Assessment

**Low risk.** AP1 remediation removes dead `cards` sourcing that was never referenced in SQL. Output is unaffected. Simple SELECT with no joins, aggregation, or business logic.
