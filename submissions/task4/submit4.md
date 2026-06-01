# Task 4 Submission and Implementation Audit

Date: 2026-05-31

## Scope

Task 4 asked for five Prometheus metrics and three Grafana panel query fixes:

- `chat_request_duration_seconds`
- `chat_input_tokens`
- `chat_output_tokens`
- `judge_evaluations_total`
- `judge_latency_seconds`
- DIVERGENCE panel PromQL
- Request latency p50/p95/p99 panel PromQL
- Judge verdicts panel PromQL

## Code Proofs

### Metric definitions

File: `src/monitoring/metrics.py`

The required metrics are defined with the requested types, labels, and buckets:

```python
chat_request_duration_seconds = Histogram(
    "chat_request_duration_seconds",
    "End-to-end /chat request latency in seconds.",
    ["config_id"],
    buckets=(0.1, 0.25, 0.5, 1.0, 2.0, 4.0, 8.0, 16.0, 32.0),
)

chat_input_tokens = Histogram(
    "chat_input_tokens",
    "Prompt/input tokens used by each model call in a /chat request.",
    ["config_id", "model"],
    buckets=(16, 64, 256, 1024, 4096, 16384),
)

chat_output_tokens = Histogram(
    "chat_output_tokens",
    "Completion/output tokens produced by each model call in a /chat request.",
    ["config_id", "model"],
    buckets=(8, 32, 128, 512, 2048),
)

judge_evaluations_total = Counter(
    "judge_evaluations_total",
    "Completed sampled judge evaluations by verdict.",
    ["config_id", "verdict"],
)

judge_latency_seconds = Histogram(
    "judge_latency_seconds",
    "Latency of sampled deep judge calls in seconds.",
    ["config_id"],
    buckets=(0.5, 1.0, 2.0, 4.0, 8.0, 16.0, 32.0),
)
```

Conclusion: all metrics listed in "Which metrics you'll add" are defined.

### `/chat` instrumentation

File: `src/assistant/service.py`

Each model call now records cost plus token distributions:

```python
for call in response.model_calls:
    chat_cost_usd_total.labels(
        config_id=config_id, model=call.model
    ).inc(cost_usd(call.model, call.input_tokens, call.output_tokens))
    chat_input_tokens.labels(config_id=config_id, model=call.model).observe(
        call.input_tokens
    )
    chat_output_tokens.labels(config_id=config_id, model=call.model).observe(
        call.output_tokens
    )
```

The request duration histogram is observed in the `finally` block:

```python
chat_request_duration_seconds.labels(config_id=config_id).observe(
    time.perf_counter() - start
)
```

Conclusion: token and latency metrics are emitted by live `/chat` traffic.

### Judge worker instrumentation

File: `src/monitoring/judge_worker.py`

The sampled judge worker increments verdict counters and observes judge latency:

```python
judge_evaluations_total.labels(
    config_id=config_id, verdict=result.verdict.value
).inc()
judge_latency_seconds.labels(config_id=config_id).observe(
    result.latency_seconds
)
```

Unexpected worker failures are also surfaced as `judge_error`:

```python
judge_evaluations_total.labels(
    config_id=config_id, verdict=Verdict.JUDGE_ERROR.value
).inc()
judge_latency_seconds.labels(config_id=config_id).observe(
    time.perf_counter() - start
)
```

Conclusion: sampled judge outcomes and judge latency are emitted when a queued sample is processed.

## Grafana Proofs

File: `observability/grafana/dashboards/live_monitoring.json`

### DIVERGENCE

```promql
sum(rate(chat_requests_total{refused="true"}[5m])) / sum(rate(chat_requests_total[5m]))
```

```promql
sum(rate(judge_evaluations_total{verdict="leaked"}[1h])) / sum(rate(judge_evaluations_total[1h]))
```

Conclusion: the panel compares cheap refusal rate with sampled judge leakage rate.

### Request latency

```promql
histogram_quantile(0.5, sum by (le, config_id) (rate(chat_request_duration_seconds_bucket[5m])))
histogram_quantile(0.95, sum by (le, config_id) (rate(chat_request_duration_seconds_bucket[5m])))
histogram_quantile(0.99, sum by (le, config_id) (rate(chat_request_duration_seconds_bucket[5m])))
```

Conclusion: p50, p95, and p99 are computed correctly from histogram buckets, preserving `le`.

### Judge verdicts

```promql
sum by (verdict) (rate(judge_evaluations_total[1h]))
```

Conclusion: the panel shows one rolling-rate series per verdict after judge samples exist.

## Validation Proofs

Commands run:

```bash
.venv/bin/python -m compileall src
.venv/bin/python -c 'import json; json.load(open("observability/grafana/dashboards/live_monitoring.json")); import src.monitoring.metrics; import src.assistant.service; import src.monitoring.judge_worker; print("ok")'
git diff --check -- src/monitoring/metrics.py src/assistant/service.py src/monitoring/judge_worker.py observability/grafana/dashboards/live_monitoring.json
```

Observed results:

- `compileall` completed successfully.
- JSON parse and module imports printed `ok`.
- `git diff --check` produced no whitespace errors.

Conclusion: the implementation is syntactically valid, imports cleanly, and the dashboard JSON is parseable.
