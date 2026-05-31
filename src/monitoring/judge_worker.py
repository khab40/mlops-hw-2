"""Async worker that consumes sampled (input, response) pairs and runs the
deep judge on each. Emits Prometheus metrics; the judge result is not
written back to the user-facing request.
"""

from __future__ import annotations

import asyncio
import logging
import time

from src.judge import Verdict, judge as run_judge
from src.monitoring.metrics import (
    deep_judge_queue_depth,
    judge_evaluations_total,
    judge_latency_seconds,
)

log = logging.getLogger(__name__)


class JudgeWorker:
    """Single-consumer async worker over a bounded queue."""

    def __init__(self, queue: asyncio.Queue):
        self._queue = queue

    async def run(self) -> None:
        log.info("JudgeWorker started")
        try:
            while True:
                config_id, user_message, assistant_response = await self._queue.get()
                deep_judge_queue_depth.set(self._queue.qsize())
                start = time.perf_counter()
                try:
                    result = await asyncio.to_thread(run_judge, user_message, assistant_response)
                    judge_evaluations_total.labels(
                        config_id=config_id, verdict=result.verdict.value
                    ).inc()
                    judge_latency_seconds.labels(config_id=config_id).observe(
                        result.latency_seconds
                    )
                except Exception:  # noqa: BLE001
                    judge_evaluations_total.labels(
                        config_id=config_id, verdict=Verdict.JUDGE_ERROR.value
                    ).inc()
                    judge_latency_seconds.labels(config_id=config_id).observe(
                        time.perf_counter() - start
                    )
                    log.exception("JudgeWorker iteration failed")
                finally:
                    self._queue.task_done()
        except asyncio.CancelledError:
            log.info("JudgeWorker cancelled")
            raise
