# Genuine development incidents

## INC-001 - Valid FNOL returned 503 during API integration test

Date: 17 October 2026. Environment: local Python 3.13, FastAPI TestClient,
fakeredis, RQ 2.12.0. This was an actual test failure, not an invented production event.

Symptom: tests/test_api.py::test_full_api_durable_handoff_feedback_trace expected
202 for a valid FNOL but received 503. Three API tests failed while fourteen passed.

Confirmation: added server-side exception logging keyed by correlation ID. The
trace showed `TypeError: Queue.enqueue_call() got an unexpected keyword argument
'job_timeout'` at the submission boundary. enqueue_call uses `timeout`; the
convenience enqueue API uses job_timeout. A generic dependency response had hidden
the programming error from the initial test output.

Recovery: corrected enqueue_call to timeout=60 and reran the API tests and full
suite. Final test evidence is in results/tests.txt. No external customer or remote
repository was affected. The rejected transaction did not start an agent run.

Prevention: retain actual API + queue handoff test, quarantine/no-start tests and
correlation-linked server diagnostics. Pin tested dependencies separately from the
portable dependency ranges, and rerun integration checks after dependency changes.

## INC-002 - Stub evaluation escalated every in-scope request

Date: 17 October 2026. Local HTTP stub, same development environment.
Symptom: first batch reports had 0% verified rate and 25% outcome match (only safe
abstentions matched); stub access log showed no planner requests despite health
being reachable. Gateway events recorded HTTP protocol failures.

Cause: empty MODEL_API_KEY still generated an Authorization header with a trailing
space (`Bearer `). The HTTP client rejected the malformed header before sending.
Recovery: omit Authorization entirely if no key is configured. Added regression
test test_no_empty_bearer_header and reran both evaluation variants. Reports
supersede the failed batch; raw final traces remain in results/evaluation_v*.json.
This is evidence that health alone is insufficient; always smoke-test a full run.

## INC-003 - Native Redis protocol mismatch

17 October 2026. The first actual native worker startup failed with Redis
`unknown command HELLO 3`: the new Python client defaulted to RESP3 while the
community Windows test Redis supports RESP2. Explicitly selected RESP2 in the
connection adapter, which also works with the assessed Docker Redis 7.4. Reran
the live HTTP demonstration successfully. Native and container environments are
kept distinct in the measurement report.

## INC-004 - Benign output blocked by input-injection classifier

17 October 2026. The independent input classifier marked the template's
"Review required ..." handler instruction as injection. This caused the delivery
case to escalate without its useful verified evidence. Kept injection screening
on all untrusted model inputs/corpus, and constrained output to approved templates,
advisory flags, determination filters and toxicity screening. The final output
does not control another tool. Both benign-output and unauthorized-determination
tests are recorded by evaluation.safety_evaluate. This demonstrates why classifier
scores alone are not sufficient policy decisions.

## INC-005 - Cold corpus loaded after accepting a native warmup job

17 October 2026. After a worker restart, the next warmup exceeded the 45-second
deadline while importing/building its in-process corpus. The first attempted
measurement's raw evidence is retained under results/native_load_attempt1/; it is
not silently combined with the final matrix. Changed worker readiness to warm
the corpus before exposing its metrics endpoint/consuming jobs, and configured
Compose API dependencies on both warmed worker roles. The native harness waits
for those endpoints before its unmeasured warmup. Repeated concurrency tests reuse
the same warmed group; worker/cache changes create a fresh group. SLO target
remained unchanged. Docker startup still needs execution on a working engine.

## INC-006 - NLI exposed an overstrong delivery proposition

17 October 2026. A learned entailment check did not support a blanket hire/reward
exclusion proposition from concatenated short snippets. The public wording lacks
the customer's schedule. The correct output is a coverage concern, not a definitive
exclusion decision. Added the actual General Exception/use-clause passage, preserved
the FAQ hire/reward citation, and verify the narrower supported proposition that
the policy restricts use. Added full source chunks to preserve clause context.
The live delivery demonstration subsequently passed with human review required.

## INC-007 - Terminal-state confidence audit found four inconsistent baseline runs

17 October 2026. A final Redis-versus-client audit found four records from the
original one-worker/20-client overload trial whose final proposal was unverified
despite a client-recorded completed status. Deadline escalation had not cleared a
previous verified state flag, and a late worker could reopen an already terminal
status. No real customer was involved; the proposal itself requested human review.

Fixed escalation to clear both flags, made terminal writes first-writer-wins,
prevented late intermediate saves from reopening terminal records, and added
regressions. Locust now also requires result.verified before counting success.
The baseline verified-success count is corrected to32/44; original CSV/JSONL and
as-recorded summary fields remain available. The four post-fix native trials have
zero canonical-confidence discrepancies (terminal_confidence_audit.json).

## Incident 008 — v5 research repetition

1–3 November 2026. While replacing name-only tool selection with model-authored
queries and clause IDs, the 0.5B local model repeatedly requested fields or repeated
the same search. A 1.5B model also repeated an overbroad concatenated query when
shown all evidence topics together. Runs exhausted their bounded research budget
or escalated; no unsupported coverage recommendation was returned.

Preserved evidence: agent_v5_initial_failure.json, agent_v5_small_model_failure.json,
agent_v5_broad_query_failure.json. Changes: restrict field reads to one call, reject
duplicate calls, supply only current missing evidence and a focused research
objective, constrain argument length, and retain independent verification. The
larger model uses a single processing slot to limit memory. See results/AGENT_V5.md
for the subsequent measured smoke checks, not a claim of universal model accuracy.
