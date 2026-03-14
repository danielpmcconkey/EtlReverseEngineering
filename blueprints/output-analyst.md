# Blueprint: output-analyst

**Stage:** Plan
**States:** InventoryOutputs
**Outcome type:** SUCCESS / FAIL

## Role

Analyze and catalog everything an ETL job produces — both what the conf says
it should produce and what the OG output files actually contain. Your inventory
is the "answer key" all downstream artifacts are measured against.

## Context Provided by Orchestrator

- `job_id`, `job_name`, `og_conf_path`, `job_dir`

## Reads

**Process artifacts:**
- `{job_dir}/process/LocateOgSourceFiles.json`

**Product artifacts:**
- `{job_dir}/artifacts/og-sources.md`

**Source material:**
- OG job conf at `og_conf_path`
- OG curated output at `{OG_CURATED}/{job_dir_name}/`

## Writes

### Product artifact
- **File:** `{job_dir}/artifacts/output-inventory.md`
- **Content:** For each output module: format (CSV/Parquet/DataFrameWriter),
  column schema from actual output files, sample values, row counts, path
  pattern, write mode, trailer format. Always examine real output files.

### Process artifact
- **File:** `{job_dir}/process/InventoryOutputs.json`
- **Body:** `{ "output_count": N, "output_types": ["csv"], "columns": ["col1", "col2"], "sample_date": "2024-10-01" }`

## Method

1. Read `og-sources.md` for the module pipeline.
2. Read the job conf. Identify output-producing modules: CsvFileWriter,
   ParquetFileWriter, DataFrameWriter, or External modules that produce output.
3. For each output module, extract config: path, write mode, columns,
   header/trailer settings.
4. Examine actual OG output at `{OG_CURATED}/{job_dir_name}/`:
   a. List date subdirectories.
   b. Read a sample file — document actual column headers, row count, sample values.
   c. Note the schema as observed in the real file.
5. Note discrepancies between conf and actual output.
6. Write artifacts.

## stdout contract

```json
{"outcome": "SUCCESS", "reason": "Inventoried N outputs for {job_name}", "conditions": []}
```

## Constraints

- Document what the job ACTUALLY produces, not what you think it should.
- Always examine real output files — don't just trust the conf.
- Include sample values for every column. Downstream agents need these.
