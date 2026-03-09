# FeeWaiverAnalysis -- Anti-Pattern Assessment

**Job:** FeeWaiverAnalysis (V1) -> FeeWaiverAnalysis_RE (RE)
**Assessed against:** Master Anti-Pattern List (AP1-AP10)

---

## Summary

| AP | Name | Finding | Action |
|----|------|---------|--------|
| AP1 | Dead-End Sourcing | **FOUND** | Documented only (retained for safety) |
| AP2 | Duplicated Logic | Clean | None |
| AP3 | Unnecessary External Module | N/A | None |
| AP4 | Unused Columns | **FOUND** | Remediated |
| AP5 | Asymmetric Null/Default Handling | Documented | None (V1 behavior preserved) |
| AP6 | Row-by-Row Iteration | N/A | None |
| AP7 | Magic Values | Clean | None |
| AP8 | Complex/Dead SQL | Clean | None |
| AP9 | Misleading Names | Clean | None |
| AP10 | Over-Sourcing Date Ranges | Clean | None |

---

## Detailed Findings

### AP1 -- Dead-End Sourcing
**Finding:** **FOUND (documented, NOT remediated).**

The entire `accounts` DataSourcing module is effectively dead. ZERO columns from `accounts` appear in the SELECT, WHERE, GROUP BY, or ORDER BY clauses. The LEFT JOIN connects the data but no accounts data is ever used.

**Investigation:** Per Phase 1 lesson (ComplianceResolutionTime cartesian join inflated counts by 115x), we investigated whether the LEFT JOIN affects output:

```sql
SELECT account_id, ifw_effective_date, COUNT(*)
FROM datalake.accounts
GROUP BY account_id, ifw_effective_date
HAVING COUNT(*) > 1;
```

**Result:** Zero rows returned. Each (account_id, ifw_effective_date) pair is unique in the accounts table. Therefore the LEFT JOIN:
- Does NOT inflate event_count (no duplicate matching)
- Does NOT affect total_fees or avg_fee (LEFT JOIN preserves all overdraft_events rows)
- Is functionally a no-op

**Disposition:** Retain the accounts DataSourcing and LEFT JOIN in RE for safety. Removing would produce identical output but adds risk with zero benefit. Document as AP1 finding.

### AP2 -- Duplicated Logic
**Finding:** Clean. FeeWaiverAnalysis and OverdraftFeeSummary both source from `datalake.overdraft_events` but produce different outputs: FeeWaiverAnalysis includes overdraft_amount in DataSourcing and uses a LEFT JOIN to accounts; OverdraftFeeSummary is a standalone aggregation. They are independent jobs.

### AP3 -- Unnecessary External Module
**Finding:** N/A. No External module in V1. Job uses SQL Transformation only, which is appropriate for the JOIN and GROUP BY logic.

### AP4 -- Unused Columns
**Finding:** **FOUND.**

V1 DataSourcing sources 14 columns across 2 modules. Of these, 9 are never referenced in the transformation SQL or output:

**From overdraft_events (7 sourced, 3 unused):**

| Column | Referenced in SQL? | In output? | Verdict |
|--------|--------------------|------------|---------|
| overdraft_id | No | No | Unused |
| customer_id | No | No | Unused |
| event_timestamp | No | No | Unused |

**From accounts (7 sourced, 6 unused):**

| Column | Referenced in SQL? | In output? | Verdict |
|--------|--------------------|------------|---------|
| customer_id | No | No | Unused |
| account_type | No | No | Unused |
| account_status | No | No | Unused |
| interest_rate | No | No | Unused |
| credit_limit | No | No | Unused |
| apr | No | No | Unused |

**Remediation:** Removed 3 columns from overdraft_events DataSourcing (7 -> 4). Removed 6 columns from accounts DataSourcing (7 -> 1, keeping only `account_id` for the JOIN ON clause). Total: 14 -> 5 sourced columns.

### AP5 -- Asymmetric Null/Default Handling
**Finding:** Documented (not changed). The `CASE WHEN oe.fee_amount IS NULL THEN 0.0 ELSE oe.fee_amount END` pattern explicitly handles NULL fee amounts by treating them as 0.0. This is V1 behavior and is preserved exactly. Note: SQLite's SUM and AVG typically ignore NULLs, so this CASE expression may produce different results than a bare `SUM(fee_amount)` if NULL values exist (0.0 contributes to AVG denominator whereas NULL does not).

### AP6 -- Row-by-Row Iteration
**Finding:** N/A. No External module, no foreach loops. Pure SQL transformation.

### AP7 -- Magic Values
**Finding:** Clean. No hardcoded thresholds, magic numbers, or unexplained constants. The `0.0` in the CASE expression is a standard null-to-zero coercion. The `2` in ROUND(,2) is a standard decimal precision parameter.

### AP8 -- Complex/Dead SQL
**Finding:** Clean. The SQL is straightforward -- a single LEFT JOIN with GROUP BY aggregation. No dead CTEs, no unused window functions. The LEFT JOIN itself is functionally dead (AP1) but is not "complex/dead SQL" in the AP8 sense.

### AP9 -- Misleading Names
**Finding:** Clean. Job name "FeeWaiverAnalysis" accurately describes the output: analysis of overdraft events grouped by fee waiver status.

### AP10 -- Over-Sourcing Date Ranges
**Finding:** Clean. DataSourcing is scoped by the framework's effective date injection. No broad date range sourcing or post-filter narrowing.
