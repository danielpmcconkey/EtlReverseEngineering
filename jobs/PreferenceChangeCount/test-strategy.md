# PreferenceChangeCount — Test Strategy

**Job:** PreferenceChangeCount_RE
**Traces to:** FSD (jobs/PreferenceChangeCount/FSD.md), BRD (jobs/PreferenceChangeCount/BRD.md)

---

## Primary Validation

### Proofmark Byte-Identical Comparison
**Method:** Proofmark Parquet comparison across all 92 effective dates (2024-10-01 through 2024-12-31).

**Config:** `proofmark-configs/PreferenceChangeCount.yaml` (reader: parquet)

**LHS (V1):** `{ETL_ROOT}/Output/curated/preference_change_count/preference_change_count/{date}/preference_change_count`
**RHS (RE):** `{ETL_RE_OUTPUT}/preference_change_count/preference_change_count/{date}/preference_change_count`

**Pass criteria:** 92/92 PASS. Zero tolerance for differences.

---

## Coverage Matrix

| Dimension | Coverage | Notes |
|-----------|----------|-------|
| Effective dates | 92/92 | Oct 1 - Dec 31, 2024 |
| Data rows per date | 2230 | Stable across all dates |
| Columns | 6 | 5 from SQL SELECT + etl_effective_date |
| Format | Parquet | 1 part (not 50 like other Parquet jobs) |
| Header | N/A | Parquet has schema metadata |
| Trailer | N/A | No trailer in Parquet format |

---

## Traceability

| Test Aspect | Traces to FSD | Traces to BRD |
|-------------|---------------|---------------|
| Row content match | FSD-PCC-003 | BRD-PCC-004, BRD-PCC-005, BRD-PCC-006 |
| Column schema match | FSD-PCC-006 | BRD-PCC-009 |
| Partition count | FSD-PCC-005 | BRD-PCC-008 |
| Row count per date | FSD-PCC-003 | BRD-PCC-010 |
| Output path | FSD-PCC-005 | BRD-PCC-011 |

---

## Risk Assessment

**Medium risk.** PreferenceChangeCount has the most anti-patterns in Tier 2 (AP1 + AP4 + AP8), but all are clearly dead:
- AP1: customers table entirely unreferenced in SQL (safe to remove)
- AP4: updated_date and preference_id only used in dead RANK
- AP8: RANK() computed but never consumed
- The 1-partition Parquet output is unusual but matches V1 exactly
- All remediations are removals of dead code/data, not functional changes
