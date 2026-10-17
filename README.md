# MLSAD MINI PROJECT

Motor Insurance Claim Intake and Triage

Course UE24AM342AA5, Mini Project 01. A runnable advisory prototype for a single
HDFC ERGO private-car package corpus. Humans decide all claims. Start with the
stub configuration; no model account or credentials are needed.

## Team / Contributors

- [@DarkTJ7](https://github.com/DarkTJ7) — project team member and repository owner.
- [@vishalh06](https://github.com/vishalh06) — project team member.

## Deliverables

- `docs/PROJECT_PLAN.md`: Evaluation 1 plan and corpus/reference-case confirmation.
- `REPORT.md`: final report draft, measured evaluation and honest remaining gaps.
- `Motor_Insurance_Project_Report.pdf`: printable report with deployment diagram.
- `docs/ARCHITECTURE.md`: deployment diagram, tools, topology and tradeoffs.
- `docs/REQUIREMENTS.md`: every F/A/L/D requirement and its actual status.
- `docs/DEMO_AND_VIVA.md`: ten demonstration items and viva preparation.
- `runbook.md`, `incident_log.md`, `.env.example`, evaluation set and results.
- `app/`, `frontend/`, `prompts/`, `corpus/`: service source and policy evidence.

The repository is named MLSAD-MINI-PROJECT; this package contains its source.
See `docs/SUBMISSION_CHECKLIST.md` before calling it presentation-ready.

## Clean-clone setup (Docker Desktop / Docker Compose v2)

Install Docker Desktop and start its Linux-container engine. From this directory:

```powershell
Copy-Item .env.example .env
docker compose up --build
```

Linux/macOS: `cp .env.example .env`, then the same Docker command.
First build downloads Python dependencies and about 1 GB of pinned safety models.
Indexer reads the bundled PDF; API starts after indexing, Redis, safety and both
warmed worker roles are healthy. All application
processes run inside containers. No model or Redis installation on the host.

Open the browser on localhost at the API_PORT in .env (default 8000). The root
page is the web client. `/docs` documents REST; `/openapi.json` is its generated
machine-readable contract. Grafana uses GRAFANA_PORT (default 3000) and the local
credentials you set in .env. Jaeger uses JAEGER_PORT; Prometheus uses PROMETHEUS_PORT.

**Verification status:** local HTTP demonstration, API/queue handoff, independent
safety/NLI service and native process measurements have evidence under results/.
See docs/HARDENING.md and docs/MEASUREMENTS.md. Docker is absent and WSL networking
is blocked here, so container startup, Grafana/cAdvisor integration and container
scaling remain pending. Native measurements are not Docker measurements.

## First request and results

The form is prefilled with `examples/valid.json`. Submit, then observe the run id,
status, recommendation and exact citations. Use `examples/food_delivery.json`
to exercise the mandatory difficult case. Other examples show malformed and
injected inputs. Source PDF page numbering is one based (includes FAQ page).

PowerShell REST example (inject your configured API endpoint):

```powershell
$apiBase = Read-Host 'API base URL from your runtime configuration'
$body = Get-Content examples/valid.json -Raw
$run = Invoke-RestMethod "$apiBase/runs" -Method Post -ContentType application/json -Body $body
Invoke-RestMethod "$apiBase/runs/$($run.run_id)"
```

POST /runs returns 202 immediately. GET /runs/{run_id} polls until `completed` or
`escalated`. GET /runs/{run_id}/trace exposes tool calls/evidence. POST
/runs/{run_id}/feedback accepts `{ "satisfactory": true, "reason": "Checked citations" }`.
Unknown fields and invalid chronology/ranges return 422 without enqueueing.
All string fields are screened. Quarantine has a 24-hour TTL; runs also expire
after 24 hours. Feedback is retained until Redis data is explicitly removed.
Use synthetic data only; the localhost prototype has no authentication.

## Evaluation and tests

```powershell
docker compose exec api python -m pytest -q
docker compose exec api python -m evaluation.evaluate --version v1 --output results/evaluation_v1.json
docker compose exec api python -m evaluation.evaluate --version v4 --output results/evaluation_v4.json
docker compose cp api:/service/results/evaluation_v1.json results/evaluation_v1_docker.json
docker compose cp api:/service/results/evaluation_v4.json results/evaluation_v4_docker.json
```

Version comparison uses the same frozen 24 cases. Stub responses implement
different planner policies; these are system ablation results, not real-LLM prompt
quality scores. Metrics are explicit deterministic proxies in `evaluation/METRICS.md`.
The original evaluation_v1/v2 files are historical pre-hardening stub results.
Current real-model comparisons and native_load/ are separate experiments; see REPORT.md.

Index again (stop worker services first when changing the corpus):

```powershell
docker compose stop agent-worker verification-worker
docker compose run --rm indexer python -m app.retrieval --reembed
docker compose up -d agent-worker verification-worker
```

## Scaling and failure demonstrations

```powershell
docker compose up -d --scale agent-worker=3
docker compose --profile load run --rm load
```

Follow the predeclared target and experiment matrix in docs/SLO.md. Raise the
isolated test rate limit temporarily; restore afterwards. RUN events measure from
submission through terminal result. Never report POST latency as run latency.
Change STUB_FAIL in .env and recreate model-stub to demonstrate provider outage;
restore it for recovery. See runbook.md for exact recovery steps.

## Optional live planner

Set MODEL_MODE=live, MODEL_URL, MODEL_ID, MODEL_API_KEY and input/output token prices
in .env, then recreate API/workers. Endpoint must implement OpenAI-style chat JSON
and return `choices[0].message.content` containing `{"action":"allowed_tool"}`
plus token usage. Unknown actions or missing usage/prices cause escalation.
The adapter has been exercised with a real free local CPU model; see
results/REAL_MODEL.md and real_model_v1/v4.json for measured outcomes. Constrained
JSON ensures allowed actions; it does not guarantee good retrieval decisions.
Drafting remains template based; verification includes independent NLI.

For native reproduction, see docs/NATIVE_DEMO.md and .env.native.example.

For an entirely containerised local planner, the optional `local-model` profile
downloads the checksum-pinned GGUF into the models volume. Set MODEL_MODE=live,
MODEL_URL to the local-model service's chat-completions endpoint (port 8003),
MODEL_ID to LOCAL_MODEL_ALIAS, MODEL_TIMEOUT_SECONDS=45 and RUN_TIMEOUT_SECONDS=180,
then run `docker compose --profile local-model up --build`. Keep token prices at
zero for local inference. The longer timeout is for model quality evaluation;
it does not replace the 30-second stub SLO. This optional Docker profile is supplied
but unexecuted here, like the rest of the Docker rehearsal.

## Stop / preserve evidence

`docker compose down` stops services and retains named volumes. Copy results and
logs for submission. The report deliberately marks missing experiments; fill those
with actual measurements after rehearsal, never invented numbers.
