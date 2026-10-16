# External interface contracts

Machine-readable: openapi.json (all paths), data_contracts.json (FNOL, feedback,
recommendation). Generated from the same Pydantic models enforced by the API.
The live server /openapi.json is authoritative if code changes after export.

| Interface | Request | Response / errors |
|---|---|---|
| POST /runs | FNOL JSON, extra fields forbidden | 202 run_id/status/poll_path; 422 field errors or guardrail quarantine id; 429 per-client budget; 503 dependency failure |
| GET /runs/{run_id} | UUID returned at intake | Status + optional result + elapsed seconds; 404 unknown/expired |
| GET /runs/{run_id}/trace | Same run id | Events, retrieved passages, verified flag, cost; 404 unknown |
| POST /runs/{run_id}/feedback | satisfactory boolean, reason 3-1000 chars | 201 persisted; 404 unknown; 422 invalid/guarded |
| GET /quality | None | Aggregate feedback and recent verifier outcomes |
| GET /health | None | 200 if Redis/index ready; 503 otherwise |
| GET /metrics | None | Prometheus exposition, process/agent/index counters and histograms |
| POST model gateway URL | Runtime endpoint; messages, model, stage/context/available | Stub action/usage; live OpenAI-style choices + usage; strict allowlisted action |

Dates use ISO 8601 calendar dates. Repair estimate is a nonnegative finite number;
IDV positive finite number, each capped at 100000000. Loss <= report <= current
date; policy end >= start. A loss outside the policy period is valid intake data
and becomes a coverage concern rather than schema rejection. Registration is
uppercase alphanumeric with spaces/hyphens; this is a broad demo contract and
not official registration verification. No real policy ownership lookup exists.

Coverage positions: potentially_covered, coverage_concern, insufficient_evidence.
Queues: fast-track, surveyor assignment, investigation. Every recommendation is
advisory, with human review required. verified=false terminal records are explicit
escalations, never confident coverage answers. Unknown run IDs are not authentication.

Internal queue payload is the serialised state: run_id, correlation_id, deadline,
FNOL, events, passages and proposed recommendation. RQ uses its internal serializer
on an isolated Redis network; do not allow untrusted users to write to Redis.

Status retention: 24 hours; feedback persists in the Redis volume. Correlation ID
is emitted in response header; run_id is the cross-service audit key. Polling is
chosen over callbacks because it avoids customer callback credential handling,
delivery retries and outbound networking in a local demonstration.
