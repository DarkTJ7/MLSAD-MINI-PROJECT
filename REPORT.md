# Motor Insurance Claim Intake and Triage AI Agent

**MLSAD MINI PROJECT · UE24AM342AA5 · 4 November 2026**

## Problem and scope

Motor insurers receive free-text First Notices of Loss (FNOLs). A handler
must validate facts, classify the incident, read applicable cover and
modifying restrictions, and route the work. A single search for “accident”
can find own-damage cover while missing a distant private-car use
restriction. This project builds a multi-agent advisory service that
searches for that modifier and verifies citations. It does not approve,
reject, settle or promise payment. A human handler makes the decision.

The selected corpus is a historical HDFC ERGO private-car package PDF.
Its first page includes FAQ/claim procedure text; this is one publication,
not two independent documents. Faculty confirmation is needed. The
customer's actual schedule and active endorsements are absent.

## Agent design

The terminal is the primary interaction. FastAPI validates the FNOL and
returns a run ID; Redis queues a research worker. A local Qwen2.5 1.5B
model first audits narrative vehicle use using an exact claimant quote.
The research loop then chooses `request_fields`, `corpus_search` or
`clause_lookup` and supplies the argument. Delivery or hire/reward risk
requires an explicit use-limitation search. A separate verification worker
checks the draft against canonical PDF passages, source identity, advisory
rules and learned semantic entailment. It can ask for one different search
or escalate. Research is bounded by 14 decisions, 10 tool calls and a
runtime deadline.

The API, research worker, verification worker, safety service, local model,
Redis and indexer have separate deployment boundaries. Prometheus,
Grafana, Jaeger and container exporters are configured in Compose.
The [architecture diagram](docs/ARCHITECTURE.md) explains the handoff and
failure path. The optional minimal browser client exists to satisfy brief A8.

## Decisions and alternatives

The model controls the investigation tools and queries; constrained rules
control final wording and operational routing. This balances agentic
research with the risk of an unsupported claim determination. Exact
canonical citations and an independent semantic check are required before
release. Weak retrieval, missing schedule facts, a failed verifier or
provider outage leads to human review. A single retrieval pass,
unrestricted tools, synchronous POST reasoning and model-only
self-verification were rejected.

FAISS indexes 1000-character page-local chunks with 180-character overlap.
The zero-charge local word/bigram hashing embedding is a **lexical
baseline**, not a semantic embedding model. The index job records source
hashes and freshness and can re-embed. A richer semantic retriever is a
future improvement.

## Recorded evidence

| Check | Result and limit |
| --- | --- |
| Regression suite | 57 tests passed on the cleaned v5-only source; one library deprecation warning. |
| Paraphrased paid-meal case | Fresh clean-tree live run: the model quoted the paid meal trip despite structured personal use, made a distinct use-limitation search, and the independent verifier accepted an investigation recommendation with four original-PDF citations. End-to-end time was 341.33 seconds on this local CPU runtime. |
| Failed development attempts | A model-purpose safety flag and premature voluntary escalation both produced human review. Corrections and traces are in the incident log. |

This is one synthetic smoke case, not a representative accuracy estimate.
The [trace](results/clean_agent_live.json) was captured after the clean-tree
source change. Its slow CPU latency is separate from the stub-mode SLO.

The fixed 24-scenario evaluation set is runnable from the command line.
The current v5 full-set run, same-set comparison of two v5 prompt variants,
and before/after groundedness, context relevance, faithfulness and
hallucination rate are **pending**. Metric definitions and denominators
are in [evaluation/METRICS.md](evaluation/METRICS.md). No historical
v1–v4 scores are used as results for this agent.

## Performance and cost

The predeclared stub-mode service target is complete-run p95 ≤ 30 seconds
at five concurrent clients with a 350 ms stub delay. RPS, p50/p95,
one-versus-three-worker scaling, first failing concurrency and cache
effect for the current cleaned agent are **unmeasured in Docker**. Docker
Desktop was unavailable here. The planned matrix and measurement
definition are in [docs/SLO.md](docs/SLO.md). No bottleneck or SLO pass
is claimed without those runs.

The free local model incurred USD 0 in hosted API charges in the selected
traces. CPU, electricity and setup time are not priced. Per-step token
usage is captured, but current-agent cost per 100 runs and the largest
cost driver require the full batch. The stub's zero token charge is not a
live-model cost measurement.

## What did not work and what remains

The small model sometimes repeated a tool call, chose a field-read tool
with a search phrase, or escalated before trying a modifier search. The
loop rejects duplicates, requires the modifier search when relevant, and
never turns such failures into confident coverage advice. The policy PDF
is old and lacks the actual schedule. The browser client and dashboards
are supporting requirements; the product is the terminal AI agent.

Before final assessment: confirm corpus sufficiency and the food-delivery
reference with faculty; run the 24-case live v5 batch and prompt comparison;
start Compose from a clean clone; verify Jaeger and Grafana container panels;
run Locust scaling/cache tests; update this report with actual numbers.
The [requirement map](docs/REQUIREMENTS.md) lists each outstanding item.
