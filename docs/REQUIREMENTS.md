# Requirement traceability and evidence

Status meanings: implemented = code plus relevant local test; partial = useful
implementation but important gaps; prepared = supplied configuration/experiment,
not executed in Docker. None implies insurer/production certification.

| ID | Status | Implementation / evidence / gap |
|---|---|---|
| F1 | implemented | POST /runs; docs/openapi.json; data_contracts.json; API test |
| F2 | implemented | Pydantic validation, cross-field chronology, quarantine; no-enqueue tests |
| F3 | partial | Four-category rules and structured entities; no robust natural-language extraction |
| F4 | partial | Agent-selected FAISS searches plus modifier queries; lexical/scope limits |
| F5 | implemented for bounded outputs | Canonical source/page/quote checks, controlled narrative and independent learned NLI; human legal interpretation still required |
| F6 | implemented | Three operational queues with reasons; threshold is documented demo assumption |
| F7 | implemented | Missing clauses, scope, guardrails, deadlines or failed verification escalate |
| F8 | partial | Health/metrics/JSON step logs and connected native traces; full container exporters configured but unexecuted |
| A1 | partial | LangGraph, three allowlisted tools, step/tool/deadline limits; actual local Qwen planner tested on frozen scenarios; measured failures disclosed |
| A2 | implemented natively; Docker pending | Actual separate worker processes, queues and handoff; distinct Compose containers configured |
| A3 | implemented for bounded outputs | Canonical quote checks, risk/template constraints, independent NLI and retry/escalation; classifier uncertainty remains |
| A4 | implemented locally | FastAPI 202 plus RQ, polling; atomic enqueue integration test; Linux workers untested |
| A5 | partial | HTTP timeouts, 3 attempts/backoff, shared Redis breaker, fail-safe escalation; local tools lack isolated timeouts |
| A6 | implemented; dashboard execution pending | Agent task success, steps/tools/retries/task, latency, uptime and cAdvisor container panels configured |
| A7 | native measured; Docker pending | One versus three native workers measured; Compose scale command supplied; container comparison still pending |
| A8 | implemented locally | Plain web client, polling, citations, escalation and feedback; browser and native HTTP rehearsal passed; Docker rehearsal pending |
| L1 | partial | LangChain + FAISS, content-hash embedding cache, --reembed; local word-hash baseline, no semantic embeddings |
| L2 | measured locally | Versioned prompts; historical stub and current same-set real-model comparison recorded separately |
| L3 | implemented with stated metric limits | 24 frozen references, CLI evaluation, learned semantic evidence plus explicit structured/citation metrics; no expert certification |
| L4 | implemented defence in depth | Normalisation, full-window independent injection/toxicity classifiers, all-field/source screening, allowlisted tools/templates; no universal security guarantee |
| L5 | implemented for local model | Actual generation token counts and per-call/run costs; local API charge zero, CPU/electricity not priced |
| L6 | implemented locally | Feedback, deterministic sampling, asynchronous learned quality scoring, persistence and four-metric time chart |
| D1 | implemented locally | Exported input/output/feedback/OpenAPI contracts; rejects before queue; docs explain status codes |
| D2 | implemented locally | Idempotent CLI, digest/chunks/freshness/throughput metadata and metrics; safe concurrent index swap absent |
| D3 | prepared | Indexer, model assets, policy preflight and core/observability services; dependencies/health for core services; full clean-clone rehearsal pending |
| D4 | partial | Runtime .env for model/config; no provider secrets/model IDs committed; local health endpoints and provenance URLs necessarily documented |
| D5 | code complete; Docker verification pending | W3C context across queues/HTTP, connected span tests, JSON evidence, all-service scrapes and 28-panel cAdvisor/agent/quality dashboard |
| D6 | native measured; Docker pending | Predeclared SLO, whole-run Locust records and native failure point; container results remain separate/unmeasured |
| D7 | native measured; Docker pending | Embedding/query caches, rate-limit tests, same-condition native cache comparisons; zero local API cost explicitly scoped |
| D8 | implemented locally | Two-mode runbook and genuine test failures/fixes in incident_log.md |

The brief says completing every requirement is not expected. Prioritisation here
favours working contracts, explicit abstention, modifier retrieval and verifiable
citations. Missing Docker evidence must be completed or disclosed at assessment.
