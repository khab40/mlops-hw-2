# Task 3 Session

Annotation: Verify that the new config exists and is a meaningful variation.

```bash
$ sed -n '1,220p' configs/v6.yaml
# ANSWER Task 3 - defines a hardened sandwich config for eval, registration, and promotion.
display_name: "Hardened sandwich"
description: "Combines the anti-jailbreak main prompt with input classification and output validation."
model:
  name: nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B
  temperature: 0.0
system_prompt: prompts/v3_prompt_hardening.txt
guardrail:
  type: sandwich
  input_classifier:
    model:
      name: nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B
      temperature: 0.0
    prompt: prompts/classifier_input.txt
  output_validator:
    model:
      name: nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B
      temperature: 0.0
    prompt: prompts/classifier_output.txt
```

Annotation: Try the model-catalog command requested by the task.

```bash
$ .venv/bin/python scripts/list_models.py --verbose
No API key found. Set NEBIUS_API_KEY env var or create a `nebius_api_key` file.
```

Note: this script reads `NEBIUS_API_KEY` from the shell environment or `mlops-hw-tf-api-key`; it does not load `.env` through `src.config`.

Annotation: Confirm that full `v6` evals were registered in MLflow.

```bash
$ .venv/bin/python -c 'import mlflow; from mlflow.tracking import MlflowClient; from src.config import get_settings; s=get_settings(); mlflow.set_tracking_uri(s.mlflow_tracking_uri); c=MlflowClient(); versions=list(c.search_model_versions("name = '\''travel-assistant'\'' AND tags.config_id = '\''v6'\''")); [print("version", mv.version, "run", mv.run_id, "tags", dict(mv.tags), "metrics", c.get_run(mv.run_id).data.metrics) for mv in sorted(versions, key=lambda m:int(m.version))]'
version 4 run d4b53588d2cd40949ebb2dd3e633b19e tags {'config_id': 'v6', 'model': 'nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B', 'guardrail_type': 'sandwich', 'judge_model': 'meta-llama/Llama-3.3-70B-Instruct', 'dataset_size': '100'} metrics {'accuracy_overall': 0.98, 'accuracy_travel': 1.0, 'refusal_rate_travel': 0.0, 'accuracy_off_topic': 0.96, 'refusal_rate_off_topic': 0.96, 'accuracy_jailbreak': 0.96, 'refusal_rate_jailbreak': 1.0, 'accuracy_social_engineering': 1.0, 'refusal_rate_social_engineering': 1.0, 'verdict_rate_answered_correctly': 0.26, 'judge_evaluations_total_answered_correctly': 26.0, 'verdict_rate_refused_correctly': 0.73, 'judge_evaluations_total_refused_correctly': 73.0, 'verdict_rate_over_refused': 0.01, 'judge_evaluations_total_over_refused': 1.0, 'judge_evaluations_total_leaked': 0.0, 'judge_evaluations_total_judge_error': 0.0, 'total_cost_usd': 0.02123518, 'avg_cost_per_request_usd': 0.0002123518, 'avg_calls_per_request': 1.66, 'avg_latency_seconds': 0.8322359633760061, 'request_latency_p50_seconds': 0.24586122948676348, 'request_latency_p95_seconds': 2.7979020728846073, 'total_input_tokens': 45994.0, 'mean_input_tokens': 459.94, 'total_output_tokens': 14521.0, 'mean_output_tokens': 145.21, 'eval_duration_seconds': 200.0935015840223}
version 5 run 3926272dbffc48b095adc61aea40ef27 tags {'config_id': 'v6', 'model': 'nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B', 'guardrail_type': 'sandwich', 'judge_model': 'meta-llama/Llama-3.3-70B-Instruct', 'dataset_size': '100'} metrics {'accuracy_overall': 0.99, 'accuracy_travel': 1.0, 'refusal_rate_travel': 0.0, 'accuracy_off_topic': 1.0, 'refusal_rate_off_topic': 1.0, 'accuracy_jailbreak': 0.96, 'refusal_rate_jailbreak': 1.0, 'accuracy_social_engineering': 1.0, 'refusal_rate_social_engineering': 1.0, 'verdict_rate_answered_correctly': 0.25, 'judge_evaluations_total_answered_correctly': 25.0, 'verdict_rate_refused_correctly': 0.74, 'judge_evaluations_total_refused_correctly': 74.0, 'verdict_rate_over_refused': 0.01, 'judge_evaluations_total_over_refused': 1.0, 'judge_evaluations_total_leaked': 0.0, 'judge_evaluations_total_judge_error': 0.0, 'total_cost_usd': 0.02137672, 'avg_cost_per_request_usd': 0.00021376719999999997, 'avg_calls_per_request': 1.66, 'avg_latency_seconds': 0.8495809949946124, 'request_latency_p50_seconds': 0.2469658125191927, 'request_latency_p95_seconds': 3.148229087417711, 'total_input_tokens': 46345.0, 'mean_input_tokens': 463.45, 'total_output_tokens': 14848.0, 'mean_output_tokens': 148.48, 'eval_duration_seconds': 143.26377166702878}
```

Annotation: Confirm the promoted production alias.

```bash
$ .venv/bin/python scripts/promote.py show production
travel-assistant @ production
  mlflow_version: 5
  config_id: v6
  dataset_size: 100
  guardrail_type: sandwich
  judge_model: meta-llama/Llama-3.3-70B-Instruct
  model: nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B
  accuracy_overall: 0.9900
  total_cost_usd: $0.0214
```

Annotation: Compare the latest `v5` and promoted `v6` eval results. `v6` is not a different base model; it is a hardened prompt plus sandwich guardrail configuration around the same model.

```text
latest v5:
  MLflow version: 6
  accuracy_overall: 0.970
  accuracy_jailbreak: 0.920
  verdict_rate_leaked: 0.020
  avg_latency_seconds: 1.164
  request_latency_p95_seconds: 4.385
  total_cost_usd: $0.0245

promoted v6:
  MLflow version: 5
  accuracy_overall: 0.990
  accuracy_jailbreak: 0.960
  verdict_rate_leaked: 0.000
  avg_latency_seconds: 0.850
  request_latency_p95_seconds: 3.148
  total_cost_usd: $0.0214
```

Conclusion: on the full eval, `v6` improved overall accuracy, jailbreak accuracy, leakage rate, latency, and total cost compared with latest `v5`.

Annotation: Part D hot reload command for deployment. `ADMIN_TOKEN` was set, so the request included `X-Admin-Token`; the token value is redacted here.

```bash
$ curl -X POST http://localhost:8000/admin/reload \
  -H "X-Admin-Token: <redacted>"
{"status":"ok","previous":{"config_id":"v6","model":"nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B","guardrail_type":"sandwich","model_name":"travel-assistant","model_alias":"production","model_version":"5"},"current":{"config_id":"v6","model":"nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B","guardrail_type":"sandwich","model_name":"travel-assistant","model_alias":"production","model_version":"5"}}
```

Verification after reload:

```bash
$ curl -sS http://localhost:8000/metrics/ | grep assistant_info
# HELP assistant_info Info metric carrying deployment identity in labels. Always 1.
# TYPE assistant_info gauge
assistant_info{config_id="v6",guardrail_type="sandwich",model="nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B",model_alias="production",model_name="travel-assistant",model_version="5"} 1.0
```

Conclusion: Part D is complete. The live service is in production-alias mode and is serving `config_id=v6` from MLflow model version `5`.
