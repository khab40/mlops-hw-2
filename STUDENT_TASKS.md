# Hometask 2 — student tasks

This repo is a deliberately-incomplete version of a working travel-assistant MLOps pipeline. **Four core tasks** are required (Tasks 0, 1, 2, 3) plus **one optional task** (Task 4) for those who want to go deeper into production-grade observability.

The required tasks teach the canonical MLOps loop: *write the judge → instrument the eval → build the promotion CLI → use it to ship a real change.* Together they take you from "I can classify a response" to "I've promoted a config I designed and defended the decision."

Recommended order: **0 → 1 → 2 → 3** (required), then **4** if you have the time.

| # | Task | Required? | Type | Time | Details |
|---|---|---|---|---|---|
| 0 | Write the LLM judge (`prompts/judge.txt`) | **required** | replace placeholder | 2–3 h | [tasks/task0.md](tasks/task0.md) |
| 1 | More metrics for eval runs (`src/eval.py`) | **required** | fill in | 1–2 h | [tasks/task1.md](tasks/task1.md) |
| 2 | Promotion CLI (`scripts/promote.py`) | **required** | add | 3–5 h | [tasks/task2.md](tasks/task2.md) |
| 3 | Add a new config, score it, promote it | **required** | use the pipeline | 4–6 h + eval time | [tasks/task3.md](tasks/task3.md) |
| 4 | Restore Prometheus metrics and Grafana panels | optional | restore | 6–9 h | [tasks/task4.md](tasks/task4.md) |

## Submission

Each task's individual page documents what to submit for it. Final delivery is a single `submissions/` directory at the repo root, with one subdirectory per task you completed (`submissions/task0/`, `submissions/task1/`, etc.) containing screenshots, diffs, and short writeups as specified.

## Getting started

The orientation, setup, and "how to run things" sections are in the main [README.md](README.md). Once the stack is up, jump into [tasks/task0.md](tasks/task0.md).
