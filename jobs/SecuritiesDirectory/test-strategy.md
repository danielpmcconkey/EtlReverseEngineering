# SecuritiesDirectory — Test Strategy

**Traces to:** FSD.md, BRD.md in this directory

---

## Approach

Proofmark strict comparison of RE output vs V1 output across all 92 dates (2024-10-01 through 2024-12-31). No fuzzy columns, no excluded columns — the output should be byte-identical.

### TST-1: Strict Column Match (traces to FSD-4)
All 8 columns compared strictly. No tolerances needed — this is a reference table with no computed values.

### TST-2: Full Date Coverage (traces to BRD-5)
All 92 dates must PASS. Since each date is independent (Overwrite mode), failures are isolated.

### TST-3: Row Count Validation (traces to FSD-4)
Each date should produce exactly 50 data rows.

## Pass Criteria

100% PASS across all 92 dates in Proofmark. Zero exceptions.
