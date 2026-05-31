# Task 4 Runtime Observations

Date: 2026-05-31

## Observation 1: Prometheus is scraping the assistant

Proof command:

```bash
curl -sS --get http://localhost:9090/api/v1/query --data-urlencode 'query=up'
```

Observed result:

```json
{
  "status": "success",
  "data": {
    "result": [
      {
        "metric": {
          "__name__": "up",
          "instance": "localhost:9090",
          "job": "prometheus"
        },
        "value": [1780216224.667, "1"]
      },
      {
        "metric": {
          "__name__": "up",
          "instance": "host.docker.internal:8000",
          "job": "travel_assistant",
          "service": "travel_assistant"
        },
        "value": [1780216224.667, "1"]
      }
    ]
  }
}
```

Conclusion: Grafana emptiness is not caused by Prometheus being down or failing to scrape the assistant.

## Observation 2: The current deployment gauge is present

Proof command:

```bash
curl -sS --get http://localhost:9090/api/v1/query --data-urlencode 'query=assistant_info'
```

Observed result:

```json
{
  "status": "success",
  "data": {
    "result": [
      {
        "metric": {
          "__name__": "assistant_info",
          "config_id": "v6",
          "guardrail_type": "sandwich",
          "instance": "host.docker.internal:8000",
          "job": "travel_assistant",
          "model": "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B",
          "model_alias": "production",
          "model_name": "travel-assistant",
          "model_version": "5",
          "service": "travel_assistant"
        },
        "value": [1780216241.211, "1"]
      }
    ]
  }
}
```

Conclusion: the service started successfully and exported state metrics with deployment identity labels.

## Observation 3: The judge sample rate is 5 percent

Proof command:

```bash
curl -sS --get http://localhost:9090/api/v1/query --data-urlencode 'query=judge_sample_rate'
```

Observed result:

```json
{
  "status": "success",
  "data": {
    "result": [
      {
        "metric": {
          "__name__": "judge_sample_rate",
          "instance": "host.docker.internal:8000",
          "job": "travel_assistant",
          "service": "travel_assistant"
        },
        "value": [1780216241.212, "0.05"]
      }
    ]
  }
}
```

Conclusion: judge panels can remain empty during small manual tests because only about 5 percent of requests are sampled into the judge queue.

## Observation 4: The current process has no post-restart request samples yet

Proof command:

```bash
curl -sS --get http://localhost:9090/api/v1/query --data-urlencode 'query=chat_request_duration_seconds_count'
```

Observed result:

```json
{"status":"success","data":{"resultType":"vector","result":[]}}
```

Conclusion: latency panels need live `/chat` traffic after the current uvicorn process starts. A restart resets in-process Prometheus client counters and histograms.

## Observation 5: The LLM API error metric is registered but has no events

Proof command:

```bash
curl -sS http://localhost:8000/metrics/
```

Relevant observed output:

```text
# HELP llm_api_errors_total Errors raised by the LLM client during a /chat invocation.
# TYPE llm_api_errors_total counter
```

Proof command:

```bash
curl -sS --get http://localhost:9090/api/v1/query --data-urlencode 'query=llm_api_errors_total'
```

Observed result:

```json
{"status":"success","data":{"resultType":"vector","result":[]}}
```

Conclusion: `LLM API error rate by type` is empty because no LLM exception has occurred. This is expected and healthy. A labeled counter series appears only after the first failure for a specific `error_type`.

## Observation 6: The judge metrics are registered but have no events in the current process

Proof command:

```bash
curl -sS http://localhost:8000/metrics/
```

Relevant observed output:

```text
# HELP judge_evaluations_total Completed sampled judge evaluations by verdict.
# TYPE judge_evaluations_total counter
# HELP judge_latency_seconds Latency of sampled deep judge calls in seconds.
# TYPE judge_latency_seconds histogram
```

Proof command:

```bash
curl -sS --get http://localhost:9090/api/v1/query --data-urlencode 'query=judge_evaluations_total'
```

Observed result:

```json
{"status":"success","data":{"resultType":"vector","result":[]}}
```

Conclusion: `Judge verdicts (1h rolling)` is empty because no sampled judge evaluation has completed since the current process started. For quick testing, temporarily set `JUDGE_SAMPLE_RATE=1.0`, restart uvicorn, and send mixed `/chat` traffic.

## Observation 7: How to intentionally populate the LLM API error panel

The LLM API error panel should not populate during healthy traffic. To simulate a real error without changing code, run the service with an unreachable Nebius base URL:

```bash
NEBIUS_BASE_URL=http://127.0.0.1:9/v1/ .venv/bin/uvicorn src.assistant.service:app --reload
```

Then send one request:

```bash
python scripts/chat.py "Find flights from Paris to Rome"
```

Expected metric after the failure:

```text
llm_api_errors_total{config_id="v6",error_type="APIConnectionError"} 1
```

Conclusion: this panel is an operational failure panel. It should be demonstrated with an induced API failure, then the service should be restarted with the normal `.env` settings.
