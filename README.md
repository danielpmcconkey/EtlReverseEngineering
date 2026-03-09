# EtlReverseEngineering

Reverse engineering 105 ETL jobs from [MockEtlFramework](https://github.com/danielpmcconkey/MockEtlFramework) using AI-driven analysis.

## What This Is

POC5 in an ongoing effort to determine whether AI agents can reverse engineer an enterprise ETL portfolio — analyzing existing job configurations, identifying anti-patterns, producing clean rewrites, and proving correctness through automated comparison testing.

## Structure

| Directory | Contents |
|-----------|----------|
| `job-confs/` | Rewritten `_re` job configurations |
| `jobs/{JobName}/` | Per-job BRD, FSD, and test strategy |
| `proofmark-configs/` | Comparison test configs for Proofmark |
| `.planning/` | GSD project planning artifacts |

## Related Repos

- [MockEtlFramework](https://github.com/danielpmcconkey/MockEtlFramework) — The ETL engine and original job configs
- [proofmark](https://github.com/danielpmcconkey/proofmark) — The comparison engine used for verification
