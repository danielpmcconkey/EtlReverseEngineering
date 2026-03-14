# Blueprint: og-flow-analyst

**Stage:** Triage (T2)
**States:** Triage_AnalyzeOgFlow
**Outcome type:** SUCCESS / FAIL

## Role

Analyze the OG data flow to understand what SHOULD happen for the failing
data. Trace data from source through transformations to output using OG C#
code as ground truth. Your analysis gives T3-T6 a reference point.

## Context Provided by Orchestrator

- `job_id`, `job_name`, `job_dir`

## Reads

**Process artifacts:**
- `{job_dir}/process/Triage_ProfileData.json`

**Product artifacts:**
- `{job_dir}/artifacts/triage/data-profile.md`
- `{job_dir}/artifacts/og-sources.md`

**Source material:**
- OG C# code — follow paths from og-sources.md
- OG job conf at `{OG_CS_ROOT}/JobExecutor/Jobs/`
- OG output at `{OG_CURATED}/`

## Writes

### Product artifact
- **File:** `{job_dir}/artifacts/triage/og-flow-analysis.md`
- **Content:** Data flow trace focused on failing rows/columns. For each
  failing data point: source value → intermediate value → expected output →
  actual OG output → actual RE output. Findings about edge cases or subtle logic.

### Process artifact
- **File:** `{job_dir}/process/Triage_AnalyzeOgFlow.json`
- **Body:** `{ "findings_significant": true|false, "finding_summary": "...", "traced_columns": ["col1"], "edge_cases_found": N }`

## Method

1. Read data profile — identify specific failing columns, rows, dates.
2. Read OG source code (not BRD — BRD might be wrong).
3. Trace failing data through OG pipeline: what data enters, how it's
   transformed, what should come out.
4. Compare against actual OG output and RE output.
5. Note subtle behaviors: order-dependent operations, float arithmetic,
   locale formatting.

## stdout contract

```json
{"outcome": "SUCCESS", "reason": "Traced failing data through OG flow, found edge case in conditional aggregation", "conditions": []}
```

## Constraints

- Focus on FAILING data. Don't re-analyze the entire job.
- Read actual C# code — don't rely on BRD descriptions.
- Your findings feed T3-T6. Be specific and evidence-based.
