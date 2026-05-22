"""Async worker that consumes sampled (input, response) pairs and runs the
deep judge on each. Emits Prometheus metrics; the judge result is not
written back to the user-facing request.
"""

from __future__ import annotations

import asyncio
import logging

from src.judge import judge as run_judge
from src.monitoring.metrics import deep_judge_queue_depth
# TODO (Task 4): import judge_evaluations_total and judge_latency_seconds
# once you've defined them in src/monitoring/metrics.py. Then emit them
# in run() below where indicated.

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
                try:
                    result = await asyncio.to_thread(
                        run_judge, user_message, assistant_response
                    )
                    # TODO (Task 4): emit the two sampled metrics here.
                    #   judge_evaluations_total.labels(
                    #       config_id=config_id, verdict=result.verdict.value
                    #   ).inc()
                    #   judge_latency_seconds.labels(config_id=config_id).observe(
                    #       result.latency_seconds
                    #   )
                    # The DIVERGENCE Grafana panel needs verdict="leaked" series from
                    # the first; the Judge-verdicts panel slices by verdict.
                    _ = result  # silence unused-variable lint until you wire it up
                except Exception:  # noqa: BLE001
                    log.exception("JudgeWorker iteration failed")
                finally:
                    self._queue.task_done()
        except asyncio.CancelledError:
            log.info("JudgeWorker cancelled")
            raise
