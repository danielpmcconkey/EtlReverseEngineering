# Blueprint: source-analyst

**Stage:** Plan
**States:** InventoryDataSources
**Outcome type:** SUCCESS / FAIL

## Role

Catalog every data source an ETL job reads from: tables, columns, filters,
date resolution modes, and join relationships. Your inventory tells downstream
agents exactly what data goes in.

## Context Provided by Orchestrator

- `job_id`, `job_name`, `og_conf_path`, `job_dir`

## Reads

**Process artifacts:**
- `{job_dir}/process/LocateOgSourceFiles.json`

**Product artifacts:**
- `{job_dir}/artifacts/og-sources.md`

**Source material:**
- OG job conf at `og_conf_path`

## Writes

### Product artifact
- **File:** `{job_dir}/artifacts/data-sources.md`
- **Content:** Per DataSourcing module: schema, table, columns, date mode,
  date column, filters. Join relationships inferred from Transformation SQL.
  External module data access patterns.

### Process artifact
- **File:** `{job_dir}/process/InventoryDataSources.json`
- **Body:** `{ "source_count": N, "tables": ["datalake.customers", "datalake.accounts"], "date_filtered_count": N }`

## Method

1. Read `og-sources.md` for pipeline overview.
2. Read job conf. For each `DataSourcing` module extract: schema, table,
   columns, resultName, date resolution properties.
3. Read Transformation module SQL to understand joins. Document join types,
   keys, aggregation.
4. For External modules, check `og-sources.md` for DataFrame consumption.
5. Write artifacts.

## stdout contract

```json
{"outcome": "SUCCESS", "reason": "Inventoried N data sources for {job_name}", "conditions": []}
```

## Constraints

- Document data access as it IS, not as it should be.
- Pay attention to date resolution modes — critical for correctness.
- If a source has no date filtering, note that explicitly.
