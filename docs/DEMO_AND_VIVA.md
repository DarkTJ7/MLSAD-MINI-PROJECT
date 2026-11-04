# Live demonstration checklist

Use synthetic FNOLs and the **live local model** for reasoning demonstrations.
State explicitly when switching to the delayed stub for load or outage tests.
The course brief asks for these ten items:

1. From a clean clone, copy `.env.example` to `.env`, set the local-model
   values in [README.md](../README.md), and start
   `docker compose --profile local-model up --build`. Check service health.
2. Submit `examples/valid.json` through the terminal client. Show the run
   ID, verified route, exact PDF page and quote.
3. Open `/runs/{id}/trace` and the matching Jaeger trace. Explain every
   model call, tool query, passage, verifier decision, latency and API cost.
4. Submit `examples/malformed.json`. Show 422, quarantine ID and no
   analysis queue job.
5. Change the insurer/product to one outside the corpus. Show escalation.
6. Use the controlled verifier test to insert a fabricated citation. Show
   rejection and a different search or escalation.
7. Submit `examples/injection.json`. Show the input guard and no agent run.
8. With the stub only, set `STUB_FAIL=true`, recreate the stub, and show
   bounded retries, shared circuit opening and safe human-review fallback.
9. Run the [Locust matrix](SLO.md) with one and three research workers;
   report terminal-run p50/p95/RPS, first failing concurrency and cache effect.
10. Run `examples/food_delivery.json` and
    `examples/paraphrased_delivery.json`. Show apparent cover, separate
    use-limitation search, quoted narrative conflict, original citations,
    investigation route and schedule caveat.

Items 1, 3 dashboard, 8 and 9 still need a live Docker rehearsal on a machine
with Docker Desktop. Do not present configuration or earlier native numbers as
those measurements. The selected local-model traces in [results](../results)
prove only the recorded synthetic cases.

## Viva points

The terminal is primary because this is an agent project; `/client` exists
only for the required simple web-client demonstration. Research and
verification are separate workers so the verifier can refuse the researcher
and scale or fail independently. A second search is needed because a vehicle
use restriction may be far from the accident cover in the policy. The agent
never decides the claim; absent schedule/endorsements and unverified evidence
lead to human review. A stub isolates system capacity from live-model speed
and quality. The course target is full-run p95, including queue wait.
