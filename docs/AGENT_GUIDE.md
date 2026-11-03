# Run the AI agents directly

The primary interface is now a terminal agent client. No browser is needed.
The optional web client remains only because the brief requests one in A8.

## What changed in v5

Previously the model selected a tool name, but Python supplied the search query
and always chose the first clause for lookup. That limited the agent's autonomy.
In v5 the local model produces a validated action, its argument, and a short
public purpose. It writes each search query and selects exact clause identifiers
from retrieved evidence. Tool observations and prior calls become its next context.
The tool set is read-only: request_fields, corpus_search, clause_lookup. Completion
and escalation are explicit actions. Invalid identifiers and duplicate calls
produce observations instead of running arbitrary operations.

The analysis and verification agents are separate Redis/RQ worker processes.
The verifier checks canonical source text, citations, bounded recommendation
rules and independent learned NLI. Refusal is handed back with corrective evidence
requirements for one retry, or escalates to a human. Its validation is independent
of the research model; it does not blindly accept an LLM's self-assessment.

Classification, operational routing and final wording remain constrained rules.
This is a tool-using AI research agent with deterministic decision safeguards;
it is not unrestricted legal reasoning. Logged purposes are short action summaries,
not private chain-of-thought. The initial 0.5B model repeated tool calls and failed
the v5 smoke test; those failures are preserved. The current local runtime uses
Qwen2.5-1.5B-Instruct Q4_K_M with one processing slot. Models can fail, and failures must be
reported as abstentions rather than replaced with fabricated policy conclusions.

## Terminal usage

Install requirements.txt in your virtual environment. Start the support services
using the documented native runtime or Compose/local-model profile. Configure
AGENT_API_URL in the shell or pass --api-url. This endpoint connects to the agent
service; the CLI does not launch a browser.

```powershell
python -m app.cli --api-url http://127.0.0.1:18766 chat
python -m app.cli --api-url http://127.0.0.1:18766 run examples/food_delivery.json --output results/my_agent_run.json
python -m app.cli --api-url http://127.0.0.1:18766 watch RUN_ID
python -m app.cli --api-url http://127.0.0.1:18766 feedback RUN_ID --satisfactory yes --reason "Citations and routing were useful"
```

Chat asks for incident and policy facts. It does not invent dates, amounts or
driver eligibility. File submission validates the same external FNOL contract.
Both select prompt v5 and refuse a stub-mode service unless --allow-stub is
explicitly supplied for a system test.

The terminal displays model-authored calls and observations, the independent
verification result, citations, operational queue and recorded token/API cost.
The JSON export includes the complete run trace. Keep exports with synthetic data
when sharing the project; real customer requests may contain personal information.

## Local-model services and assessed deployment

See NATIVE_DEMO.md for native process setup and README for Compose. The CLI is a
client of the same API and queue used for assessed asynchronous execution; it does
not substitute a single Python process for two separate agents.
Use the live model configuration for AI demonstrations. The delayed stub is solely
for repeatable load tests. Earlier v1-v4 results and native performance trials are
historical evidence and must not be claimed as measurements of v5. Docker execution
and container measurements remain pending until separately run.

For live v5 research, use MODEL_TIMEOUT_SECONDS=90 and RUN_TIMEOUT_SECONDS=360.
The CLI waits up to 420 seconds and can resume an existing run. This live-model
budget is separate from the 45-second stub deadline used in historical load tests.

## Limits

- At most 14 research decisions and 10 tool calls per run, including retry.
- Existing model timeout/retry/circuit breaker, wall-clock deadline and safety service.
- Only retrieved clause IDs may be looked up; all citation text resolves canonically.
- The verifier can refuse a confident-looking model action.
- All recommendations require a human; there is no claim approval or settlement tool.
