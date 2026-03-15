"""CLI entry point for the workflow engine.

Usage: python -m workflow_engine manifest.json
"""

import argparse

from workflow_engine.engine import Engine
from workflow_engine.models import EngineConfig


def main() -> None:
    """Run the workflow engine with a job manifest."""
    parser = argparse.ArgumentParser(
        description="Run the ETL reverse-engineering workflow engine."
    )
    parser.add_argument(
        "manifest_path",
        help="Path to the job manifest JSON file.",
    )
    parser.add_argument(
        "--n-jobs", type=int, default=5, help="Number of concurrent workers (default: 5).",
    )
    parser.add_argument(
        "--max-retries", type=int, default=5, help="Max main retries per job (default: 5).",
    )
    parser.add_argument(
        "--max-conditional", type=int, default=3,
        help="Max consecutive conditionals per review node (default: 3).",
    )
    parser.add_argument(
        "--use-agents", action="store_true", default=True,
        help="Use real Claude CLI agents (default: True).",
    )
    parser.add_argument(
        "--stubs", action="store_true",
        help="Use stub nodes instead of agents (testing only).",
    )
    parser.add_argument(
        "--blueprints-dir", default="blueprints",
        help="Path to blueprint directory (default: blueprints).",
    )
    parser.add_argument(
        "--jobs-dir", default="jobs",
        help="Path to jobs output directory (default: jobs).",
    )
    parser.add_argument(
        "--model", default="sonnet",
        help="Claude model for agent invocations (default: sonnet).",
    )
    parser.add_argument(
        "--timeout", type=float, default=14400.0,
        help="Max seconds to wait for all jobs to complete (default: 14400).",
    )
    parser.add_argument(
        "--etl-start-date",
        help="First effective date for ETL execution and validation (YYYY-MM-DD).",
    )
    parser.add_argument(
        "--etl-end-date",
        help="Last effective date for ETL execution and validation (YYYY-MM-DD).",
    )
    args = parser.parse_args()

    config = EngineConfig(
        n_jobs=args.n_jobs,
        max_main_retries=args.max_retries,
        max_conditional_per_node=args.max_conditional,
        use_agents=not args.stubs,
        blueprints_dir=args.blueprints_dir,
        jobs_dir=args.jobs_dir,
        agent_model=args.model,
        etl_start_date=args.etl_start_date,
        etl_end_date=args.etl_end_date,
    )
    engine = Engine(config)
    results = engine.run(args.manifest_path, timeout=args.timeout)
    completed = sum(1 for j in results if j.status == "COMPLETE")
    print(f"\n{completed}/{len(results)} jobs completed successfully")


if __name__ == "__main__":
    main()
