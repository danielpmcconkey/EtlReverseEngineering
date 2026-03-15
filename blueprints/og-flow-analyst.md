# Blueprint: og-flow-analyst

**Stage:** Triage (T2)
**States:** Triage_AnalyzeOgFlow
**Outcome type:** SUCCESS / FAIL

## Role

Analyze the OG data flow to understand what SHOULD happen for the failing
data. You are the foundation the entire triage pipeline builds on — T3-T6
all check their respective layers against YOUR analysis. If you miss the
relevant behavior, every downstream checker returns "clean" and the job
goes to DEAD_LETTER with no diagnosis. Be thorough.

## Context Provided by Orchestrator

- `job_id`, `job_name`, `job_dir`

## Reads

**Process artifacts:**
- `{job_dir}/process/Triage_ProfileData.json`

**Product artifacts:**
- `{job_dir}/artifacts/triage/data-profile.md`
- `{job_dir}/artifacts/og-sources.md`

**Source material:**
- OG Python source code — follow paths from og-sources.md. Read the ACTUAL CODE.
- OG job conf at `/workspace/MockEtlFrameworkPython/JobExecutor/Jobs/`
- OG output at `/workspace/MockEtlFrameworkPython/Output/curated/`
- RE output at `/workspace/MockEtlFrameworkPython/Output/re-curated/`
- RE output (the files that failed Proofmark)

## Writes

### Product artifact
- **File:** `{job_dir}/artifacts/triage/og-flow-analysis.md`

### Content Structure

The analysis MUST include all of the following sections:

```markdown
# OG Flow Analysis: {job_name} — Triage

## 1. Failure Summary
{What failed: which dates, which columns, which rows, from the data profile.}

## 2. Complete Data Flow Trace
For EVERY module in the OG pipeline (not just the ones you think are relevant):

### Module 1: DataSourcing — {resultName}
- Table: {schema.table}
- Columns: {list}
- Date filter: {mode, column}
- Row count for failing date: {read from actual OG output or DB if possible}

### Module 2: Transformation — {resultName}
- Full SQL (quoted verbatim from job conf):
  ```sql
  {the actual SQL}
  ```
- Input tables: {list of resultNames}
- Join semantics: {inner/left/right, keys, NULL handling}
- Aggregation: {GROUP BY columns, aggregate functions}
- ORDER BY: {if any — sort order matters for row-order differences}
- Edge case behaviors: {what happens with NULLs, empty groups, division by zero}

### Module N: External — {ClassName}
- Source file: {path}
- Input DataFrames: {list}
- Output DataFrame: {name}
- Logic (traced line by line for the failing data):
  1. {step 1: what happens to the failing row}
  2. {step 2}
  ...
- Library-specific behaviors: {pandas vs numpy aggregation, rounding modes,
  sort stability, string formatting}

### Module N+1: Output — {type}
- Format: {CSV/Parquet}
- Column order as written: {list}
- Formatting applied: {number formats, date formats, quoting}

## 3. Failing Data Point Traces
For EACH distinct failing data point identified in the data profile:

### Trace: {row_key} → {failing_column}
1. Source value(s): {table.column = value, for all relevant sources}
2. After join: {intermediate row, noting which sources contributed}
3. After aggregation/transform: {computed value, showing the calculation}
4. Expected output value: {what the OG pipeline should produce}
5. Actual OG output value: {read from /workspace/MockEtlFrameworkPython/Output/curated/ file}
6. Actual RE output value: {read from RE output file}
7. Discrepancy: {what differs and by how much}

## 4. OG vs RE Behavior Differences
Check for ALL of the following — these are known divergence patterns between
OG and RE Python implementations:
- [ ] Float accumulation order (a + b + c ≠ a + c + b in IEEE 754)
- [ ] Library rounding modes (numpy round vs pandas round vs Python builtin — bankers rounding vs half-up)
- [ ] NULL/NaN propagation in aggregates (pandas skipna defaults, numpy behavior)
- [ ] Sort stability and tie-breaking when no explicit ORDER BY exists
- [ ] String formatting differences (f-string vs .format vs % interpolation)
- [ ] Trailing zeros in numeric output (format specifiers, Decimal vs float)
- [ ] pandas version-specific behavior (groupby sort defaults, dtype inference)
- [ ] DataFrame column ordering (insertion order vs alphabetical)

## 5. Findings
- {Each finding numbered, with severity and evidence}
- {If nothing found: "No edge cases or behavioral differences identified.
  The OG flow is straightforward for the failing data points. The issue
  is likely in the RE implementation or comparison configuration."}
```

### Process artifact (written on ALL outcomes — SUCCESS and FAIL)
- **File:** `{job_dir}/process/Triage_AnalyzeOgFlow.json`
- **Body:**
```json
{
  "outcome": "SUCCESS|FAIL",
  "reason": "...",
  "conditions": [],
  "findings_significant": true,
  "finding_count": N,
  "finding_summary": "...",
  "traced_columns": ["col1", "col2"],
  "traced_rows": N,
  "og_re_divergences_checked": 8,
  "og_re_divergences_found": N,
  "edge_cases_found": N
}
```

**The orchestrator reads the `outcome` field from this file to determine
routing.** You MUST write this file even on FAIL.

## Method

1. Read the data profile thoroughly. List every failing column, row, and date.
2. Read og-sources.md for file paths. Then read the ACTUAL source files:
   - Read the OG job conf JSON in full.
   - Read any External module Python source in full — do not skim.
3. Trace the complete pipeline, module by module, documenting every step.
   Do not skip modules you think are irrelevant — a DataSourcing module
   that loads a "simple" table might be missing a column that matters downstream.
4. For each failing data point from the profile:
   a. Read the actual OG output file for that date.
   b. Read the actual RE output file for that date.
   c. Trace the specific value through every pipeline step.
   d. Show your work: source value → intermediate → output.
5. Systematically check the OG vs RE divergence checklist in Section 4.
   For each item, determine whether it applies to this job's logic. Check the
   box and note your finding even if it's "not applicable."
6. Synthesize findings. Be specific: "OG external module uses
   numpy.around(value, 2) at processor.py:47 which uses bankers rounding —
   RE uses pandas .round(2) which may differ for midpoint values."

## stdout contract

```json
{"outcome": "SUCCESS", "reason": "Complete flow analysis with N findings across M traced data points", "conditions": []}
```

## Constraints

- You are the FOUNDATION of the triage pipeline. T3-T6 check against your work.
  If you miss something, they all return "clean" and the job goes to DEAD_LETTER.
- Read the actual OG Python code. Not the BRD. Not the FSD. The BRD might be wrong —
  that's what T3 checks. You work from source code.
- Read the actual output files. Not summaries. The files.
- Trace EVERY failing data point, not just a sample. If the data profile
  shows 5 rows differ, trace all 5.
- The OG vs RE divergence checklist (Section 4) is mandatory. Check
  every item even if you think it doesn't apply. Document why it doesn't.
- Do not speculate without evidence. If you can't determine the cause from
  the code, say "could not determine" — don't guess.
