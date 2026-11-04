# Course requirement status for the cleaned AI agent

Status is as of 4 November 2026. **Implemented** means code plus local
regression or selected live evidence; it does not mean production or insurer
approval. **Configured** means Compose/dashboard files exist but have not
been rehearsed with Docker Desktop. The course brief requires honest
disclosure of remaining gaps.

| ID | Status | Evidence or remaining gap |
| --- | --- | --- |
| F1 | Implemented | Documented `POST /runs` and FNOL schema |
| F2 | Implemented | Boundary validation, field errors, quarantine, no enqueue on reject |
| F3 | Partial | Four-category rules plus quoted model audit of vehicle use; broader entity extraction limited |
| F4 | Partial | Agent-chosen FAISS searches and modifier gate; lexical retrieval can miss paraphrases |
| F5 | Implemented for bounded output | Exact original-PDF citations, canonical and semantic verification |
| F6 | Implemented | Fast-track, surveyor and investigation routes with reasons |
| F7 | Implemented | Weak, conflicting, unsafe or out-of-scope evidence escalates |
| F8 | Partial | Local health, metrics and logs; full container evidence pending |
| A1 | Implemented locally | LangGraph, three model-chosen read-only tools, step/tool/run limits |
| A2 | Implemented locally | Separate research and verification worker processes and queue handoff |
| A3 | Implemented for bounded output | Canonical quote and semantic checks, one different-search retry |
| A4 | Implemented locally | FastAPI 202/run ID, Redis queue and polling |
| A5 | Partial | Model HTTP timeout, retries and circuit breaker; individual local tool calls lack isolated deadlines |
| A6 | Configured | Agent and container dashboard panels supplied; container rehearsal pending |
| A7 | Pending | `--scale agent-worker=3` is configured; Docker throughput/p95 comparison unmeasured |
| A8 | Implemented as minimal client | `/client` submits and polls; terminal remains primary |
| L1 | Partial | LangChain/FAISS, idempotent index and re-embedding; lexical word-hash embedding baseline |
| L2 | Pending for current agent | Current prompts versioned; same-set live v5 prompt-variant comparison still needed |
| L3 | Partial | Frozen 24 scenarios and CLI metric code; full v5 batch/before-after metrics still needed |
| L4 | Implemented with limits | Input/source screening, output controls, toxicity and injection classifiers; no universal guarantee |
| L5 | Partial | Per-step/run token and zero local API-cost records; current-agent cost per 100 runs pending batch |
| L6 | Implemented locally | Feedback, aggregation, asynchronous sampled quality; dashboard rehearsal pending |
| D1 | Implemented locally | Published JSON/OpenAPI contracts and quarantine at boundary |
| D2 | Implemented locally | Source digest, chunks, freshness, throughput and CLI index job |
| D3 | Configured | Compose services and health checks; clean-clone container start untested here |
| D4 | Partial | Runtime environment file; published artifact manifests necessarily identify pinned local models |
| D5 | Configured and locally traced | W3C context, structured events and all exporters; live container dashboards pending |
| D6 | Pending for this agent | Predeclared whole-run p95 target; Docker Locust RPS/p50/p95 and failure point unmeasured |
| D7 | Partial | Rate limit and caches implemented; current-agent cache p95/cost effect unmeasured |
| D8 | Implemented | Two-failure runbook and genuine [incident log](../incident_log.md) |

Priority for assessment: first prove a clean-clone live run; then test the
food-delivery restriction and independent verification; then complete the
24-case current-agent evaluation and Docker performance/dashboard rehearsal.
Do not reuse removed historical v1-v4 or native metrics as current results.
