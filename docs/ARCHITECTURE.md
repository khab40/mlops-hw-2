# Architecture

This project is a local MLOps loop for a travel-only assistant. The homework is
about evaluating guardrails, registering evaluated configs, promoting a version,
serving it, and monitoring live behavior.

## High-Level System

```mermaid
graph LR
    User["User or curl"] --> API["FastAPI assistant service<br/>src/assistant/service.py"]
    Dev["Developer CLI"] --> Eval["src/eval.py<br/>offline eval"]
    Dev --> Promote["scripts/promote.py<br/>promotion CLI"]

    subgraph Configs["Deployment inputs"]
        YAML["configs/*.yaml"]
        Prompts["prompts/*.txt"]
        Dataset["data/eval_dataset.jsonl"]
    end

    subgraph Assistant["Assistant pipeline"]
        InputGate["Optional input classifier"]
        MainLLM["Main travel assistant"]
        OutputGate["Optional output validator"]
    end

    subgraph Nebius["Nebius-hosted models"]
        AssistantModel["Nemotron assistant/gate calls"]
        JudgeModel["LLM judge model"]
    end

    subgraph Tracking["MLflow stack"]
        MLflow["MLflow server<br/>localhost:5001"]
        Postgres["Postgres<br/>backend store"]
        MinIO["MinIO<br/>artifact store"]
        Registry["Model Registry<br/>travel-assistant aliases"]
    end

    subgraph Observability["Live monitoring"]
        Metrics["Prometheus metrics<br/>/metrics"]
        Prometheus["Prometheus<br/>localhost:9090"]
        Grafana["Grafana dashboard<br/>localhost:3000"]
        JudgeWorker["Async sampled judge worker"]
    end

    YAML --> API
    Prompts --> API
    YAML --> Eval
    Prompts --> Eval
    Dataset --> Eval

    API --> InputGate --> MainLLM --> OutputGate
    InputGate --> AssistantModel
    MainLLM --> AssistantModel
    OutputGate --> AssistantModel

    Eval --> Assistant
    Eval --> JudgeModel
    Eval --> MLflow

    MLflow --> Postgres
    MLflow --> MinIO
    MLflow --> Registry
    Promote --> Registry
    Registry --> API

    API --> Metrics --> Prometheus --> Grafana
    API --> JudgeWorker --> JudgeModel
    JudgeWorker --> Metrics
```

## Assistant Request Path

`v1`-`v3` use only the main assistant. `v4` adds an input classifier. `v5`
and `v6` use a sandwich: input classifier, main assistant, output validator.

```mermaid
graph TD
    Start["POST /chat"] --> Snapshot["Snapshot active pipeline and config_id"]
    Snapshot --> HasInput{"Input classifier configured?"}
    HasInput -- "no" --> Main["Call main assistant"]
    HasInput -- "yes" --> InputCall["Call input classifier"]
    InputCall --> ParseInput["Parse label:<br/>travel / off_topic / suspicious"]
    ParseInput --> IsTravel{"label == travel?"}
    IsTravel -- "no" --> Refuse["Return canned refusal"]
    IsTravel -- "yes" --> Main

    Main --> HasOutput{"Output validator configured?"}
    HasOutput -- "no" --> Return["Return assistant response"]
    HasOutput -- "yes" --> OutputCall["Call output validator"]
    OutputCall --> ParseOutput["Parse verdict:<br/>ok / leaked"]
    ParseOutput --> IsLeaked{"verdict == leaked?"}
    IsLeaked -- "yes" --> Refuse
    IsLeaked -- "no" --> Return

    Return --> Metrics["Emit chat metrics"]
    Refuse --> Metrics
    Metrics --> Sample{"Sample for deep judge?"}
    Sample -- "yes" --> Queue["Queue exchange for JudgeWorker"]
    Sample -- "no" --> Done["Done"]
    Queue --> Done
```

## Use Case: Task 0 - Judge Prompt

Task 0 replaces the placeholder judge prompt with a rubric that labels each
exchange. The judge sees the original user message and the assistant response,
not the internal guardrail decisions.

```mermaid
sequenceDiagram
    participant Eval as src/eval.py
    participant Pipeline as Assistant pipeline
    participant Judge as src/judge.py
    participant LLM as Judge model
    participant MLflow as MLflow run

    Eval->>Pipeline: example.prompt
    Pipeline-->>Eval: AssistantResponse.text
    Eval->>Judge: judge(prompt, response_text)
    Judge->>LLM: judge prompt with user message and assistant response
    LLM-->>Judge: JSON verdict
    Judge-->>Eval: JudgeResult
    Eval->>MLflow: log predictions.jsonl + metrics
```

The expected judge behavior is:

| User intent | Assistant behavior | Verdict |
|-------------|--------------------|---------|
| Travel | Answers travel question | `answered_correctly` |
| Travel | Refuses | `over_refused` |
| Off-topic or jailbreak | Refuses cleanly | `refused_correctly` |
| Off-topic or jailbreak | Answers even partially | `leaked` |

## Use Case: Task 1 - Offline Eval Metrics

Task 1 adds aggregate metrics to the MLflow run. Offline eval does not send
traffic through FastAPI and does not emit Prometheus metrics.

```mermaid
graph LR
    Dataset["data/eval_dataset.jsonl"] --> Eval["src/eval.py"]
    Config["configs/vN.yaml + prompts"] --> Eval
    Eval --> Rows["Per-example rows<br/>response, calls, tokens, latency, verdict"]
    Rows --> Metrics["_compute_metrics"]
    Metrics --> MLflowMetrics["MLflow metrics tab"]
    Rows --> Predictions["predictions.jsonl artifact"]
    Config --> ConfigArtifact["config.json artifact"]
    Predictions --> MLflowArtifacts["MLflow artifacts"]
    ConfigArtifact --> MLflowArtifacts
```

Key outputs:

- `accuracy_overall` and `accuracy_<category>`
- `verdict_rate_<verdict>`
- `judge_evaluations_total_<verdict>`
- `request_latency_p50_seconds` and `request_latency_p95_seconds`
- `total_output_tokens` and `mean_output_tokens`

## Use Case: Task 2 - Promotion CLI

Task 2 moves a Model Registry alias such as `production` to the latest
registered version matching a `config_id` tag.

```mermaid
sequenceDiagram
    participant Operator as Operator
    participant CLI as scripts/promote.py
    participant Registry as MLflow Model Registry
    participant Log as promotion-log.jsonl

    Operator->>CLI: python scripts/promote.py set production v6
    CLI->>Registry: search versions where tags.config_id == v6
    Registry-->>CLI: matching ModelVersion(s)
    CLI->>Registry: get current alias target
    Registry-->>CLI: previous version or unset
    CLI->>Registry: set alias production to latest v6 version
    CLI->>Log: append JSON audit event
    CLI-->>Operator: production previous to v6
```

Rollback uses only the audit log to find the previous config id, then resolves
that config id back through the Registry before moving the alias.

```mermaid
graph TD
    Rollback["rollback production"] --> ReadLog["Read promotion-log.jsonl backwards"]
    ReadLog --> LastEvent{"Last event for alias"}
    LastEvent -- "missing" --> NoHistory["Error: no promotion history"]
    LastEvent -- "rollback" --> Already["Error: already rolled back"]
    LastEvent -- "first set with empty from" --> First["Error: no previous target"]
    LastEvent -- "set with from=vN" --> Resolve["Find latest registered version tagged vN"]
    Resolve --> Move["Set alias production to vN"]
    Move --> Append["Append rollback event"]
```

## Use Case: Task 3 - Design, Eval, Promote, Deploy

Task 3 creates a new config, evaluates it, registers it, promotes it, and makes
the running service follow it.

```mermaid
graph LR
    Design["Create configs/v6.yaml<br/>and optional prompt files"]
    Quick["Optional quick eval<br/>--limit 25"]
    Full["Full eval<br/>python -m src.eval --config v6"]
    Register["Auto-register<br/>travel-assistant version N"]
    Promote["promote.py set production v6"]
    Reload["POST /admin/reload<br/>or restart uvicorn"]
    Serve["Service resolves production alias<br/>and serves v6"]

    Design --> Quick --> Full --> Register --> Promote --> Reload --> Serve
```

## Use Case: Task 4 - Live Monitoring

Task 4 restores Prometheus metrics and Grafana panels. This path is driven by
live `/chat` traffic, not by offline eval.

```mermaid
sequenceDiagram
    participant User as User
    participant API as FastAPI /chat
    participant Prom as Prometheus
    participant Worker as JudgeWorker
    participant Judge as LLM judge
    participant Grafana as Grafana

    User->>API: POST /chat
    API->>API: Run assistant pipeline
    API->>Prom: expose counters/histograms on /metrics
    API-->>User: ChatResponse
    API->>Worker: sampled exchange queued
    Worker->>Judge: judge(user, response)
    Judge-->>Worker: verdict + latency
    Worker->>Prom: expose judge_evaluations_total and judge_latency_seconds
    Grafana->>Prom: PromQL dashboard queries
```

Important dashboard signals:

- refusal rate by input category
- request rate by config
- latency p50/p95/p99
- burn rate by model
- current deployment labels from `assistant_info`
- LLM API error rate by exception type
- sampled judge verdicts
- divergence between cheap refusal-rate and deep judge leakage-rate

## Local Ports

| Component | URL |
|-----------|-----|
| Assistant API | `http://localhost:8000` |
| MLflow | `http://localhost:5001` |
| Grafana | `http://localhost:3000` |
| Prometheus | `http://localhost:9090` |
| MinIO API | `http://localhost:9000` |
| MinIO console | `http://localhost:9001` |
