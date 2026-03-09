# CardStatusSnapshot -- Anti-Pattern Assessment

**Job:** CardStatusSnapshot (V1) -> CardStatusSnapshot_RE (RE)
**Assessed against:** Master Anti-Pattern List (AP1-AP10)

---

## Summary

| AP | Name | Finding | Action |
|----|------|---------|--------|
| AP1 | Dead-End Sourcing | Clean (post-AP4) | None |
| AP2 | Duplicated Logic | Clean | None |
| AP3 | Unnecessary External Module | N/A | None |
| AP4 | Unused Columns | **FOUND** | Remediated |
| AP5 | Asymmetric Null/Default Handling | Clean | None |
| AP6 | Row-by-Row Iteration | N/A | None |
| AP7 | Magic Values | Clean | None |
| AP8 | Complex/Dead SQL | Clean | None |
| AP9 | Misleading Names | Clean | None |
| AP10 | Over-Sourcing Date Ranges | Clean | None |

---

## Detailed Findings

### AP1 -- Dead-End Sourcing
**Finding:** Clean (after AP4 remediation). Single DataSourcing module (`datalake.cards`). Post-remediation, the one sourced column (`card_status`) is used in the transformation SQL GROUP BY and appears in the output.

### AP2 -- Duplicated Logic
**Finding:** Clean. No other job produces card status aggregation. CardStatusSnapshot is the sole producer of this output.

### AP3 -- Unnecessary External Module
**Finding:** N/A. No External module in V1. Job uses SQL Transformation only, which is appropriate for the GROUP BY aggregation logic.

### AP4 -- Unused Columns
**Finding:** **FOUND.**

V1 DataSourcing sources 6 columns. Of these, 5 are never referenced in the transformation SQL or output:

| Column | Referenced in SQL? | In output? | Verdict |
|--------|--------------------|------------|---------|
| card_id | No | No | Unused |
| customer_id | No | No | Unused |
| card_type | No | No | Unused |
| card_number_masked | No | No | Unused |
| expiration_date | No | No | Unused |

**Remediation:** Removed all 5 columns from DataSourcing. RE sources only `card_status`. This reduces data transfer from 6 to 1 column and makes the sourcing contract honest about what the job actually needs.

Note: The plan identified 4 unused columns, but `card_type` is also sourced and never used. All 5 non-`card_status` columns are removed.

### AP5 -- Asymmetric Null/Default Handling
**Finding:** Clean. Simple COUNT(*) aggregation with no null handling concerns.

### AP6 -- Row-by-Row Iteration
**Finding:** N/A. No External module, no foreach loops. Pure SQL transformation.

### AP7 -- Magic Values
**Finding:** Clean. No hardcoded thresholds, magic numbers, or unexplained constants.

### AP8 -- Complex/Dead SQL
**Finding:** Clean. The SQL is a straightforward GROUP BY with COUNT(*). No CTEs, no window functions, no dead code.

### AP9 -- Misleading Names
**Finding:** Clean. Job name "CardStatusSnapshot" accurately describes the output: a snapshot of card counts by status.

### AP10 -- Over-Sourcing Date Ranges
**Finding:** Clean. DataSourcing is scoped by the framework's effective date injection.
