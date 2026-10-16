# Where the measurements come from

The primary timing event is Locust's RUN/submission_to_terminal, emitted only after
polling reaches a terminal result or times out. POST submission and GET polling
have separate rows. Never use their aggregate row or POST p95 as end-to-end latency.

results/native_load/ contains a plan written before measurements, per-trial raw
JSONL terminal-run observations, Locust stats/history/failure CSVs and a summary.
Rows identify analysis-worker count, concurrency and whether retrieval caching
was enabled. Stub latency is 350 ms per planner call. Safety inference, Redis,
queueing, retrieval, verification and HTTP polling remain real.

Environment: native Windows Python processes and a localhost Redis community
Windows port, not containers. Analysis and verification are separate OS processes.
The real generative model is idle during load tests, to avoid CPU contention.
Safety/embedding models remain active because they are part of the service.
Conclusions apply only to this host/configuration. Docker measurements remain
pending by agreement with the user.

RPS in summary is completed verified runs divided by full observed experiment wall
time, including client startup/drain; terminal RPS is also reported. p50/p95 use
linear interpolation over individual submission-to-terminal durations. Locust
CSV percentiles use Locust's response-time buckets, so small differences are
expected. Error/escalation fraction is reported separately; fast abstentions do
not count as successful recommendations. 60-second tests provide exploratory
evidence, not a production capacity certification or confidence intervals.

Scaling compares one versus three analysis processes at matched concurrency.
The first tested concurrency that misses p95 <=30 seconds or >=95% successful
recommendations is the observed failure point; it is not an exact mathematical
maximum. If none fails, report 'not reached' instead of inventing a limit.

Cache comparison switches the actual retrieval-query cache off/on on the same
scenario, worker count and client count. Other warm-cache conditions are held as
consistently as possible. Local model/stub usage has zero API charge, so USD 0
per run means API cost only; electricity, CPU and memory are not free. A tiny
FAISS query cache may show little improvement when model delay/queueing dominate.
Always report the observed effect, including negligible or negative differences.

Docker follow-up: run the same Locust scenario under Compose, repeat with
`docker compose up -d --scale agent-worker=3`, and record cAdvisor/Grafana metrics.
Use three repetitions and longer runs for a stronger capacity claim. Keep those
results in a separate docker_load/ directory; do not overwrite native evidence.
