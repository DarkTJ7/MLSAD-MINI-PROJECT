# Measured native-process baseline

Native Windows processes, not Docker. Baseline runtime source is recorded in summary.json. A terminal-confidence audit excludes four inconsistent original one-worker/20-client records: verified completion is32/44, not the36/44 status-only count. Raw CSV/JSONL and as-recorded fields are preserved. The bug was fixed before the post-fix matrix, whose audit has zero discrepancies.

| Workers | Cache | Clients | Verified/terminal | Verified RUN/s | p50 s | p95 s | SLO met |
|---:|:---:|---:|---:|---:|---:|---:|:---:|
| 1 | on | 1 | 17/17 | 0.272 | 3.12 | 3.65 | yes |
| 1 | on | 5 | 25/25 | 0.349 | 12.77 | 16.44 | yes |
| 1 | on | 10 | 29/29 | 0.417 | 20.58 | 27.08 | yes |
| 1 | on | 20 | 32/44 | 0.310 | 43.58 | 46.10 | no |
| 3 | on | 5 | 31/31 | 0.433 | 9.34 | 12.75 | yes |
| 3 | on | 10 | 35/35 | 0.432 | 21.16 | 24.13 | yes |
| 3 | on | 20 | 29/44 | 0.296 | 40.99 | 47.30 | no |
| 1 | off | 5 | 31/31 | 0.458 | 10.04 | 12.84 | yes |
| 3 | off | 5 | 32/32 | 0.485 | 8.85 | 12.88 | yes |

1 worker(s), 5 clients: cache-on p95 16.44 s versus off 12.84 s; observed change +28.0%. API charge per run: USD 0 in both. Single exploratory trials; do not infer a statistically significant caching benefit.

3 worker(s), 5 clients: cache-on p95 12.75 s versus off 12.88 s; observed change -1.1%. API charge per run: USD 0 in both. Single exploratory trials; do not infer a statistically significant caching benefit.

Both worker counts first miss the target at the tested concurrency of 20; 10 passes. The actual boundary is only bracketed, not exactly located. Three analysis workers help at five/ten clients but do not remove the single verification queue and learned-inference bottleneck. Per-phase timings and their sample counts are in summary.json. Deadline escalations are counted as failures, not successful recommendations. Native startup issue and initial attempt are retained in incident_log.md and native_load_attempt1/. Docker measurements remain pending.
