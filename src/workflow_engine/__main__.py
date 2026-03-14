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
    args = parser.parse_args()

    config = EngineConfig(
        n_jobs=args.n_jobs,
        max_main_retries=args.max_retries,
        max_conditional_per_node=args.max_conditional,
    )
    engine = Engine(config)
    results = engine.run(args.manifest_path)
    completed = sum(1 for j in results if j.status == "COMPLETE")
    print(f"\n{completed}/{len(results)} jobs completed successfully")


if __name__ == "__main__":
    main()
