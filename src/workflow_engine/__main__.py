"""CLI entry point for the workflow engine.

Usage: python -m workflow_engine
"""

from workflow_engine.engine import Engine
from workflow_engine.models import EngineConfig


def main() -> None:
    """Run the workflow engine with default configuration."""
    config = EngineConfig(n_jobs=5, max_main_retries=5, max_conditional_per_node=3)
    engine = Engine(config)
    results = engine.run()
    completed = sum(1 for j in results if j.status == "COMPLETE")
    print(f"\n{completed}/{len(results)} jobs completed successfully")


if __name__ == "__main__":
    main()
