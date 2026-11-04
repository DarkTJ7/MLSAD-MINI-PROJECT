# Motor Insurance Claim Intake and Triage — Project Plan

**Mini Project 01 · UE24AM342AA5 · ML System Design and AgentOps**
**Project:** MLSAD MINI PROJECT
**Team:** [@DarkTJ7](https://github.com/DarkTJ7), [@vishalh06](https://github.com/vishalh06), [@trishagshetty05-art](https://github.com/trishagshetty05-art)
**Plan updated:** 4 November 2026

## 1. Problem, objective and boundary

A motor insurer receives a First Notice of Loss (FNOL) with structured policy and incident fields plus a free-text description. A claims handler must check completeness, identify the claim type, read the relevant policy cover **and** any modifying restriction, and choose a work queue. The AI agent recommends a likely coverage position and an operational route, with citations a handler can inspect. It never approves or rejects a claim, calculates a settlement, or changes a policy. A human handler decides.

The core difficulty is that an accident description naturally retrieves the own-damage cover, while the applicable private-car use restriction may be elsewhere in the wording. The agent must decide to search for a modifier, use what it learns to search again, and verify its answer. Weak, conflicting, out-of-scope or missing evidence leads to escalation.

## 2. Worked demonstration case and reference answer

> “I was making a food delivery run in my own car when the accident happened.”

| One-pass lookup can miss | Agent investigation must do |
| --- | --- |
| It finds accidental external means under own-damage cover and may imply ordinary coverage. | Retrieve that cover; ask whether vehicle use modifies it; search the private-car use restriction and hire/reward wording; check procedure and exact citations; refer the concern to a handler. |

**Reference outcome for the selected corpus:** own-damage classification; `coverage_concern`; `investigation` queue. The answer cites the accidental-damage cover and vehicle-use restriction, explains that delivery use needs investigation, and requests the actual schedule and endorsements. It does **not** assert that every delivery trip is excluded, because the insured schedule is absent. A personal-use field in the synthetic FNOL is intentionally paired with the delivery narrative to test inconsistency. Exact page/chunk IDs are in [the reference answer](../corpus/reference_answer.json).

**Fixed demo inputs:** IDV ₹500,000; repair estimate ₹12,000; network garage yes; valid licence yes; intoxication no; incident in India and during the policy period. The control case uses an ordinary parking collision and expects a cited fast-track recommendation. The ₹20,000 fast-track threshold is our configurable demonstration rule, not an insurer policy term.

## 3. Corpus and evidence preparation

The corpus is the HDFC ERGO Standard Form for Private Car Package Policy PDF. Its first PDF page contains insurer FAQ and claims-intimation procedure; later pages contain policy wording and endorsements. The claims-procedure text file is extracted from that same PDF and is **not** a second independent insurer publication. This is a historical teaching snapshot. Confirm with faculty whether the corpus satisfies the two-document expectation; if not, add a separately published official procedure and re-run indexing/evaluation. The actual policy schedule is unavailable. See [corpus provenance](../corpus/SOURCES.md).

The indexer reads the PDF text layer, creates page-linked chunks with document/page/clause IDs, builds a FAISS index and caches embeddings by content hash. It records source hash, build time, chunk count and throughput. Re-embedding has a separate command. Retrieval must surface apparent cover and modifying exclusions/restrictions; similarity alone cannot settle coverage.

## 4. Agent design and execution

```text
Terminal client or simple web client
          │ submit FNOL / poll run ID
          ▼
FastAPI validation ── invalid records → quarantine (no worker starts)
          │
          ▼
Redis queue → Research agent worker → verification queue → Verifier worker
                 │ model-selected tools             │ source/citation/NLI checks
                 │ request fields                   └─ accept, request new search,
                 │ corpus search                       or escalate
                 └ clause lookup
          │
          ▼
Cited recommendation + fast-track / surveyor / investigation or human escalation
          │
          └→ trace, metrics, feedback and sampled quality score
```

The research agent uses LangGraph and a free local Qwen2.5 1.5B model. A narrow intake audit first looks for an exact claimant phrase supporting delivery or hire/reward use and flags conflicts with structured vehicle use. The model then selects a read-only tool **and its argument**. It can inspect request fields, search policy text with a query it writes, and look up an exact retrieved clause ID. It seeks cover, modifiers and procedure before completing; restricted-use cases require an explicit modifier search. The verifier runs in a separate worker process. It checks every citation against canonical retrieved text, checks recommendation support, and blocks a final claim determination. A refusal asks for a different search once; otherwise the run escalates. Live research is bounded to 14 decisions, 10 tool calls and a 360-second local-model deadline; stub load testing uses a separate 45-second deadline. Model timeouts, retry/backoff and a circuit breaker protect the run. The terminal is the main interaction; the brief also requires a simple web client.

## 5. Architecture and operations

FastAPI validates an FNOL, returns HTTP 202 plus a run ID, and exposes polling, trace and feedback endpoints. Redis holds queues, bounded cache, rate limits and demo run state. Separate research and verification workers isolate failures and permit scaling. The indexer is an independent job; safety/NLI and model services have distinct resource profiles. Docker Compose declares services and health checks. Prometheus, Grafana, Jaeger and OpenTelemetry are configured for p50/p95 latency, throughput, errors, retries, task success, token/cost use, uptime, resources and complete traces. See the [architecture](ARCHITECTURE.md) and [requirement map](REQUIREMENTS.md).

The published contract enforces schema, categories, ranges and cross-field dates before enqueueing; rejects are quarantined with field errors. Free text and retrieved content are screened for injection and toxicity. Tools are allowlisted and read-only; output constraints plus verification prevent claim approval/rejection. Per-client rate limiting controls repeated multi-step use. Runtime configuration comes from `.env`. The free local model needs no hosted API key.

## 6. Evaluation and acceptance criteria

| Evidence | Planned check and acceptance rule |
| --- | --- |
| Correctness | Run the frozen 24-scenario set, including food delivery, ordinary damage, theft, third-party, malformed and out-of-scope cases. Record expected outcomes and supporting passages. Count verified recommendations separately from escalations. |
| Agent behavior | Show model-authored search/lookup arguments, independent verifier handoff, a changed search after refusal, and escalation when evidence remains weak. |
| Quality | Compare two versioned prompts on the same cases. Report groundedness, context relevance, faithfulness and hallucination rate with the stated scoring method, before/after one deliberate change. Keep stub and real-model results separate. |
| Safety | Test quarantine/no enqueue, injection, toxicity, forged citations, outage/circuit breaker, retries and fallback. Never return an unverified or unauthorised determination. |
| Performance | Predeclared stub-mode SLO: complete-run p95 ≤ 30 seconds at five concurrent clients with 350 ms model-stub delay. Measure terminal-run RPS, p50/p95, failures and escalations at 1, 5, 10, 20 and 40 clients; compare one/three research workers and cache on/off. Identify first failing tested concurrency and bottleneck. |
| Operations | Reconstruct one run across API, workers, tools, retrieval and verification. Verify Prometheus scrapes, Grafana container panels and Jaeger trace once Docker Desktop is available. |

Current evidence includes 57 regression tests and one verified live local-model example for a paid-meal paraphrase from the cleaned checkout. These few traces are not a full accuracy estimate. The old native-process and v1–v4 measurement files have been removed from this clean repository tree because they do not measure the current agent. Docker startup, container dashboard rehearsal, full v5 evaluation and Docker scaling measurements remain pending. See the [current report](../REPORT.md), [live paraphrase trace](../results/clean_agent_live.json) and [predeclared SLO](SLO.md).

## 7. Delivery sequence and team work

| Stage | Work and reviewable output |
| --- | --- |
| 1. Corpus and contract | Confirm insurer/product and procedure with faculty; locate food-delivery cover/restriction; freeze FNOL contract and reference answer. |
| 2. Working agent path | Run validation → queue → model-chosen retrieval → independent verification → cited route in terminal; retain simple web client for brief A8. |
| 3. Quality and safety | Re-run frozen set with live v5; compare two prompts; investigate failures; test injection, toxicity, citation faults and outage fallback. |
| 4. Container measurement | Start clean-clone Compose with Docker Desktop; check health, traces and dashboards; execute planned Locust, scaling and cache matrix and save raw results. |
| 5. Submission and viva | Update report with measured results and limits, rehearse all ten demo items from a clean clone, and submit report plus GitHub repository by course deadline. |

**Suggested ownership for three contributors:** one leads corpus/retrieval and reference labels; one leads API, agent and verifier; one leads deployment, telemetry and evaluation. All three review the difficult case, inspect failures and rehearse the demo. The team should assign ownership; usernames alone do not establish who did which work.

## 8. Risks and decisions to confirm

- **Corpus sufficiency:** procedure and wording are currently one published PDF. Confirm whether a second independent document is required; replace the extract if necessary.
- **Policy ambiguity:** delivery use needs the schedule and endorsements. Escalate when these are missing.
- **Local model quality:** small CPU models can repeat searches or miss modifiers. Keep loop limits, independent verification and recorded failure cases.
- **Deployment evidence:** Docker Desktop has not been available here. Complete container measurements and the dashboard demo before claiming those requirements met.
- **Personal data:** use synthetic FNOLs in evaluation and shared traces; this local prototype has no production authentication.

## 9. Deliverables and demonstration

Evaluation 1: this plan, corpus provenance, food-delivery reference passages and proposed test values. Final submission: report, documented GitHub repository, contracts, versioned prompts, frozen evaluation set/results, runbook, incident log, `.env.example`, working agent, API, Compose and dashboard configuration. Evaluation 2: live run through the ten items in the [demo guide](DEMO_AND_VIVA.md), including malformed input, escalation, verification retry, injection response, circuit breaker, scaling evidence and the food-delivery case. The course brief says the system must start and serve a valid request at the demonstration.

**Planning references:** [example plan 1](https://github.com/dhanushs1912-svg/tariff-dispute-triage/blob/main/docs/project_plan.pdf), [example plan 2](https://github.com/tanishkgowda/MLSDA_Electricity-Tariff-Dispute/blob/main/Mini_Project_11_Plan.pdf), and the local course brief `MiniProject_01_Motor_Insurance_Claim_Triage.pdf`. The examples informed structure only; the insurance case, corpus, limits and status come from this project and its brief.
