import asyncio
import argparse
from .pipeline.main import run_pipeline
from .dashboard.main import app
from .scheduler.celery_app import discover_trending_manga_task
from uvicorn import run as uvicorn_run


def main():
    parser = argparse.ArgumentParser(description="Manga Video Pipeline CLI")
    parser.add_argument(
        "command",
        choices=["run-pipeline", "start-server", "discover-trending"],
        help="Command to execute"
    )
    
    args = parser.parse_args()
    
    if args.command == "run-pipeline":
        print("Starting manga video pipeline...")
        asyncio.run(run_pipeline())
    elif args.command == "start-server":
        print("Starting dashboard server...")
        uvicorn_run(app, host="0.0.0.0", port=8000)
    elif args.command == "discover-trending":
        print("Discovering trending manga...")
        result = discover_trending_manga_task.delay()
        print(f"Started discovery task with ID: {result.id}")


if __name__ == "__main__":
    main()