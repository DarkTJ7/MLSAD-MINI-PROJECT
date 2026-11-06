# MLSAD MINI PROJECT

**Motor Insurance Claim Intake and Triage AI Agent · Mini Project 01 · UE24AM342AA5**

This repository contains a terminal-first AI agent for a synthetic motor
insurance First Notice of Loss (FNOL). It checks the request, investigates
the HDFC ERGO private-car policy wording with model-chosen read-only tools,
verifies every cited recommendation in a separate worker, and routes work
to fast-track, surveyor assignment or investigation. A human claims handler
makes every coverage decision. The agent cannot approve, reject or settle a
claim.

## Team

- [Tarun J](https://github.com/DarkTJ7) (`@DarkTJ7`)
- [Vishal H](https://github.com/vishalh06) (`@vishalh06`)
- [Trisha Shetty](https://github.com/trishagshetty05-art) (`@trishagshetty05-art`)

See [CONTRIBUTORS.md](CONTRIBUTORS.md) for the team list.

## Try the AI agent

The real-model demonstration uses a free local Qwen2.5 1.5B GGUF served through
an OpenAI-compatible llama.cpp endpoint. It needs **no hosted API key**. The
model weights are downloaded at runtime and are not stored in Git.

1. Install Docker Desktop with its Linux engine and Docker Compose v2.
2. Copy `.env.example` to `.env`. Set `MODEL_MODE=live`,
   `MODEL_URL=http://local-model:8003/v1/chat/completions`,
   `MODEL_ID` to your local model alias, `MODEL_TIMEOUT_SECONDS=90`,
   `RUN_TIMEOUT_SECONDS=360`, and both token prices to `0`.
3. Start the stack from this directory:

   ```powershell
   docker compose --profile local-model up --build
   ```

4. In another terminal, use the agent client inside the API container:

   ```powershell
   docker compose exec api python -m app.cli --api-url http://api:8000 chat
   docker compose exec api python -m app.cli --api-url http://api:8000 run examples/paraphrased_delivery.json
   ```

The first build downloads dependencies and local model assets. If the machine
cannot run the local model, `MODEL_MODE=stub` with the default `.env.example`
configuration allows deterministic system tests; the CLI requires
`--allow-stub` in that mode and the result is **not** real AI reasoning.
An [optional native runtime guide](docs/NATIVE_RUNTIME.md) covers Windows
when Docker Desktop is unavailable.
The API is at `http://127.0.0.1:8000` by default, with OpenAPI at `/docs`.
A small optional browser client is at `/client` solely for brief requirement A8.
The root URL describes the agent service rather than opening a website.

## What the agent does

1. FastAPI validates the FNOL contract and quarantines rejects before queueing.
2. The analysis worker checks the claimant narrative for quoted delivery or
   hire/reward use that conflicts with a structured field.
3. Its local model chooses `request_fields`, `corpus_search` or
   `clause_lookup` and writes search queries and clause IDs. A restricted-use
   case must include a modifier search. Set `RESEARCH_PROMPT_VARIANT=v5a` or
   `v5b` to compare the two current research instructions.
4. A separate verification worker checks canonical PDF citations, route
   constraints and semantic support. It can request one different search or
   escalate.
5. The API exposes status, trace, metrics and feedback by run ID.

The required food-delivery case should produce an **own-damage,
coverage-concern, investigation** recommendation citing both accident cover
and private-car use restriction. The actual policy schedule and endorsements
are absent, so the agent cannot determine final coverage.

## Repository map

| Path | Purpose |
| --- | --- |
| `app/` | API, terminal client, LangGraph research and verification, safety, queue and tracing |
| `prompts/` | Current versioned research, intake-audit and verification prompts |
| `corpus/` | Official historical policy PDF, provenance, hashes and reference case |
| `examples/` | Synthetic FNOLs, including the food-delivery paraphrase |
| `evaluation/` | Frozen 24-scenario set, metric definitions and batch runner |
| `tests/` | Contract, API, agent, safety and trace regressions |
| `docs/` | [Project plan](docs/PROJECT_PLAN.pdf), [agent guide](docs/AGENT_GUIDE.md), [architecture](docs/ARCHITECTURE.md), [requirement status](docs/REQUIREMENTS.md) and [peer comparison](docs/REFERENCE_AGENT_COMPARISON.md) |
| `results/` | Selected synthetic live traces and development failure evidence |
| `client/` | Minimal optional web client required by the course brief |

See [the report](Motor_Insurance_Agent_Report.pdf) for tested evidence and honest gaps,
[runbook.md](runbook.md) for failures, and [incident_log.md](incident_log.md)
for genuine development incidents.

## Verification and limits

Run `python -m pytest -q` after installing `requirements.txt`. The latest
local suite passed 63 tests. The fresh real local-model trace in
`results/clean_agent_live.json` shows the paraphrased paid-meal case,
an explicit use-limitation search, a cited investigation route and independent
verification. These few cases do not establish an accuracy rate.

The [matched live prompt comparison](results/prompt_comparison_live.json) for
the synthetic food-delivery claim found both variants verified and faithful;
v5b used 6 provider calls and 115 seconds versus 7 calls and 186 seconds for
v5a. This is a one-case observation, not an accuracy or throughput estimate.

A later [live retrieval check](results/procedure_retrieval_live.json) on the
same claim retrieved and cited the PDF's actual claim-filing instructions
(`p1:c2`) after a documented procedure-query vocabulary expansion. The run
was verified and matched the expected route. Its 150-second duration is a
separate local run and does not establish a latency improvement.

The full v5 24-scenario real-model comparison and Docker load, scaling, cache
and dashboard measurements remain unmeasured. Docker Desktop was unavailable
in the authoring environment. Do not cite earlier native measurements as
results for this cleaned agent.

Use synthetic data only. This localhost course prototype has no customer
authentication, insurer policy lookup or production PII controls.
