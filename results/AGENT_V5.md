# Agent-first redesign: evidence and current limits

Updated 3 November 2026. The terminal command is the main demonstration:

```powershell
python -m app.cli --api-url http://127.0.0.1:18766 chat
```

The analysis worker invokes a real local Qwen2.5-1.5B-Instruct Q4_K_M model. The
model generates a validated tool action, its search query or clause identifier,
and a short public purpose. Read-only tools return policy passages; the next
action receives those observations and the evidence still needed. The independent
verification worker checks canonical quotes, allowed recommendation wording and
learned entailment. A refusal asks for a different search or a human review.

Safety and operational limits: maximum 14 research decisions and 10 tool calls,
run/model deadlines, provider retry and circuit breaker, screened free text,
quarantined flagged source passages, exact clause-ID lookup, immutable policy
citations and advisory-only output. The policy schedule and activated endorsements
are unavailable, so a human must decide coverage.

The v5 model is pinned in corpus/agent_planner_manifest.json. Its API charge is
USD 0 per call. CPU and electricity are not priced. The model weights and local
runtime binaries are deliberately excluded from the repository and archive.

The first 0.5B agent loop repeated field reads and searches. A first 1.5B trial
repeated an overbroad query; a later trial encountered a flagged policy passage.
These real failures are preserved in agent_v5_*_failure.json and incident_log.md.
The final prompt and tool policy focus each search on the current evidence gap and
quarantine flagged passages before the model sees them. These development trials
cannot be counted as successful agent runs.

The historical 24-scenario v1-v4 evaluations, native scaling trials and cache
comparisons test earlier code. They are not v5 quality or capacity results.
Docker deployment, container dashboards and Docker load measurements remain
pending as separately disclosed in the original report.

Final local checks: 50 regression tests passed. A parking-damage case completed
with a verified, cited fast-track recommendation in agent_v5_parking.json. The
required food-delivery case completed with a verified coverage-concern position,
investigation routing and citations to both the accidental-damage cover and the
private-car vehicle-use restriction in agent_v5_delivery.json. Full model
decisions, tool observations and verifier reports are in those JSON files.

Live v5 results and regression checks are in agent_v5_parking.json,
agent_v5_delivery.json and tests_agent_v5.txt. A single or small set of successful
cases does not establish general accuracy; the frozen 24-scenario set still needs
to be rerun with v5 before a new quality percentage is reported.
