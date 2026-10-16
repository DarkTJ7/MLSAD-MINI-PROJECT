# Native validation after clause-preserving verification

These are native Windows processes, not Docker. Same 30-second target,350ms stub,required learned safety/NLI; policy-preflight completed before claim work. No generative-model evaluation ran concurrently.

| Workers | Clients | Verified/terminal | Successful RUN/s | p50 s | p95 s | SLO met |
|---:|---:|---:|---:|---:|---:|:---:|
| 1 | 5 | 26/26 | 0.356 | 12.58 | 19.00 | yes |
| 1 | 20 | 26/42 | 0.260 | 43.94 | 46.31 | no |
| 3 | 5 | 67/67 | 1.072 | 3.85 | 6.49 | yes |
| 3 | 20 | 80/80 | 0.933 | 17.71 | 26.17 | yes |

Source commit: be78857129b2f1151a8f3c19628653d8b9c18698. The baseline nine-trial matrix and cache comparisons remain in native_load/ and NATIVE_MEASUREMENTS.md. These four matched validations use focused, complete policy clauses for NLI. At three workers the tested20-client case now meets the target; this does not locate the next failure point. One worker still has its observed latency limit. No zero-charge local API result prices CPU/electricity. Single trials, no confidence intervals.
