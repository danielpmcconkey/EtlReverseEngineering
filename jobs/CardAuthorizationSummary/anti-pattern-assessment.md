# CardAuthorizationSummary -- Anti-Pattern Assessment

**Job:** CardAuthorizationSummary (V1) -> CardAuthorizationSummary_RE (RE)
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
| AP7 | Magic Values / Integer Division | **FOUND** | Documented only (load-bearing) |
| AP8 | Complex/Dead SQL | **FOUND** | Remediated (2 issues) |
| AP9 | Misleading Names | Clean | None |
| AP10 | Over-Sourcing Date Ranges | Clean | None |

---

## Detailed Findings

### AP1 -- Dead-End Sourcing
**Finding:** Clean (after AP4 remediation). Two DataSourcing modules (`datalake.card_transactions`, `datalake.cards`). Post-remediation, all sourced columns are used: `card_id` for JOIN, `amount` is sourced but unused in output (however it's in the DataSourcing spec), `authorization_status` for CASE WHEN, `card_type` for GROUP BY and output.

**Note:** `amount` is sourced in V1 but never referenced in the transformation SQL. It was not removed in AP4 remediation to maintain conservative posture -- it may be used by framework internals for DataSourcing validation.

### AP2 -- Duplicated Logic
**Finding:** Clean. No other job produces card authorization summary statistics. CardAuthorizationSummary is the sole producer of this output.

### AP3 -- Unnecessary External Module
**Finding:** N/A. No External module in V1. Job uses SQL Transformation only, which is appropriate for the JOIN and GROUP BY logic.

### AP4 -- Unused Columns
**Finding:** **FOUND.**

V1 DataSourcing sources 8 columns across 2 modules. Of these, 3 are never referenced in the transformation SQL or output:

| Source | Column | Referenced in SQL? | In output? | Verdict |
|--------|--------|--------------------|------------|---------|
| card_transactions | card_txn_id | Only in dead ROW_NUMBER ORDER BY | No | Unused (dead code dependency) |
| card_transactions | customer_id | No | No | Unused |
| cards | customer_id | No | No | Unused |

**Remediation:** Removed `card_txn_id` and `customer_id` from card_transactions DataSourcing (5 -> 3 columns). Removed `customer_id` from cards DataSourcing (3 -> 2 columns). This reduces data transfer and makes the sourcing contract honest about what the job actually needs.

### AP5 -- Asymmetric Null/Default Handling
**Finding:** Clean. No null-handling quirks. CASE WHEN expressions for approved/declined counts are standard patterns.

### AP6 -- Row-by-Row Iteration
**Finding:** N/A. No External module, no foreach loops. Pure SQL transformation.

### AP7 -- Magic Values / Integer Division
**Finding:** **FOUND (documented, NOT remediated -- LOAD-BEARING).**

The `approval_rate` calculation uses integer division: `CAST(approved AS INTEGER) / CAST(total AS INTEGER)`. In SQLite, integer division truncates toward zero. Since `approved_count` is always less than `total_count` (not all transactions are approved), this always produces 0.

This is V1 behavior and is **NOT changed** in RE. Output must be byte-identical, and the integer division is the established business logic. Whether this is "correct" business intent or an original coding oversight is outside the scope of RE.

**Evidence:** V1 output for all 92 dates shows `approval_rate=0` for both Credit and Debit rows. For example:
- 2024-10-01: Credit 501/535 = 0, Debit 909/949 = 0
- 2024-12-31: Credit 505/527 = 0, Debit 1024/1077 = 0

### AP8 -- Complex/Dead SQL
**Finding:** **FOUND (two issues, both remediated).**

**Issue 1: Dead ROW_NUMBER -- REMEDIATED**
V1 SQL computes `ROW_NUMBER() OVER (PARTITION BY c.card_type ORDER BY ct.card_txn_id) AS rn` in the `txn_detail` CTE, but `rn` is never referenced in the outer SELECT or in any WHERE clause. The window function is computed for every row and then thrown away during GROUP BY aggregation. Pure dead code.

**Remediation:** Removed the `ROW_NUMBER()` window function and eliminated the CTE wrapper entirely. The outer query now operates directly on the JOIN.

**Issue 2: Dead CTE (`unused_summary`) -- REMEDIATED**
V1 SQL defines `unused_summary AS (SELECT card_type, COUNT(*) AS cnt FROM txn_detail GROUP BY card_type)` -- a CTE that is literally never referenced by any downstream query. It is defined and then completely ignored. This is the most obviously dead code possible.

**Remediation:** Removed the `unused_summary` CTE entirely.

### AP9 -- Misleading Names
**Finding:** Clean. Job name "CardAuthorizationSummary" accurately describes the output: summary statistics of card transaction authorizations grouped by card type.

### AP10 -- Over-Sourcing Date Ranges
**Finding:** Clean. DataSourcing is scoped by the framework's effective date injection. No broad date range sourcing or post-filter narrowing.
