"""Temporal worker entrypoint.

Run with:
    python -m app.workers.temporal_worker
"""

from __future__ import annotations

import asyncio

from app.services.workflows.temporal_backend import run_worker


def main() -> None:
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()
