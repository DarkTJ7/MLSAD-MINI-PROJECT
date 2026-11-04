# Service level objective and measurement plan

The original target was declared on 17 October 2026 before load tests:
**complete-run p95 at most 30 seconds at five concurrent clients** with a
350 ms delayed model stub and a warm policy index. A run starts when the API
accepts the FNOL and ends at a verified recommendation or explicit escalation.
The POST response time alone is not the run latency. The 45-second stub run
deadline and verified-success fraction must be reported alongside p95.

This target measures queueing, workers, retrieval, verification and API
polling with a controlled model delay. A live CPU model has a separate
360-second run budget for quality demonstrations; its latency is not
comparable to the stub SLO. The target was not changed after seeing results.

## Required experiment

Run Locust against a clean Compose deployment at 1, 5, 10, 20 and 40
concurrent clients for 60 seconds per condition, with repeat trials.
Compare one and three analysis workers using
`docker compose up -d --scale agent-worker=3`. Repeat matched cache
on/off conditions. Preserve raw terminal-run events, CSV, container metrics,
model-stub delay/configuration and source revision. Report completed-run RPS,
p50, p95, errors, verified rate and escalations. Identify the first tested
concurrency missing the target and the component causing it.

Docker Desktop has not been available in the authoring environment. These
current-agent Docker measurements, scaling results and cache comparisons
are **unmeasured**. One real local-model run and 57 regression tests
demonstrate behavior, not this SLO.
