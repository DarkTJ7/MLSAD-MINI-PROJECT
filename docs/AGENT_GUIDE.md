# Motor claim AI agent guide

The terminal client is the primary interface. The API and optional browser
client submit the same FNOL contract to the same queue.

## Agent roles

**Research worker.** A local model audits vehicle use in the claimant's words,
then chooses one read-only tool at a time. It writes the query for
`corpus_search`, selects an already retrieved ID for `clause_lookup`, and can
read structured fields through `request_fields`. Observations feed the next
decision. For delivery/hire-reward concerns, the loop requires a separate
search for a use limitation before it may finish. The intake audit is a stage
of this worker, not a third independently deployed agent.

**Verification worker.** A different RQ process checks the cited passage
against canonical indexed PDF text, the allowed advisory output, required
evidence and an independent semantic support service. It can reject the
research result and request one different search. Repeated or unsupported
work becomes human escalation. No model has a claim-approval or payment tool.

## Run it

Follow the live local-model Compose setup in [README.md](../README.md).
Then:

```powershell
docker compose exec api python -m app.cli --api-url http://api:8000 chat
docker compose exec api python -m app.cli --api-url http://api:8000 run examples/food_delivery.json
docker compose exec api python -m app.cli --api-url http://api:8000 run examples/paraphrased_delivery.json
```

The terminal shows model-authored actions and tool results, then the independent
verifier's outcome. It prints the operational route and original PDF
citations. A run can be resumed with `watch RUN_ID`; the caller can submit
feedback with `feedback RUN_ID --satisfactory yes|no --reason TEXT`.

The paid-meal paraphrase intentionally says `vehicle_use=personal` in a
structured field. The audit must quote the contrary narrative phrase. An
unquoted model signal is discarded; deterministic risk flags remain in force.

## Boundaries and fallback

- Research: at most 14 decisions and 10 tool calls, with a wall-clock deadline.
- The live local model uses a longer run budget than the delayed stub used for
  system load tests. The budget is set in the runtime environment.
- Every model call has a timeout, bounded retry and shared circuit breaker.
- Input, model tool arguments and retrieved text are screened; flagged source
  passages are quarantined from the model context.
- Only retrieved clause IDs may be looked up. The verifier resolves each
  citation to the original policy text.
- Weak evidence, conflict, missing scope, deadline, unsafe content or provider
  outage leads to explicit human review.

The chosen HDFC ERGO PDF is a historical teaching snapshot. Its first page has
FAQ/claims-procedure text, not an independently published second document.
Faculty confirmation is still needed. The insured schedule and active
endorsements are unavailable, so no definitive coverage determination is
possible.

## Evidence

The selected [live paraphrase trace](../results/clean_agent_live.json)
shows a quoted use conflict, a distinct use-limitation search, clause lookup,
and verified coverage-concern/investigation route. The two [development](../results/narrative_audit_guardrail_failure.json)
[failures](../results/narrative_audit_early_escalation_failure.json) are
preserved. These runs are examples, not a general accuracy estimate.
