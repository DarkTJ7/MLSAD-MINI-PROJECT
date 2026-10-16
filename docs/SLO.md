# SLO declared before measurements

Declaration: 17 October 2026, before evaluation and load measurements in this package.

Target: p95 <= 30 seconds from accepted FNOL submission to terminal verified
recommendation or explicit escalation, under 5 concurrent clients, a 350 ms stub
per planner call and an initially warm corpus. Also report terminal escalation rate;
fast failures do not count as successful recommendations. At least 95% of valid,
in-scope test claims should produce a verified recommendation.

Why: handlers need interactive intake rather than immediate final settlement;
30 seconds gives queueing/retry headroom above 4-5 model calls while remaining
short enough for assisted intake. Hard run deadline: 45 seconds including queueing.
This is a design target, not a measured claim.

Load plan: 1, 5, 10, 20, 40 clients for 60 seconds each, repeat three times;
compare 1 versus 3 analysis workers. Preserve CSV files and terminal-run events.
Repeat cache off/on on identical scenarios. Raise demo rate limit for the isolated
load experiment, then restore it. Measure completed-run RPS, p50, p95, errors and
escalations separately. Identify the first tested concurrency missing either SLO;
inspect queue wait and step spans before attributing a bottleneck.

Docker is unavailable in the authoring environment. Docker SLO, scaling,
concurrency failure point and Docker cache comparisons remain UNMEASURED.
The user authorised separately labelled native-process measurements; their plan,
raw RUN records and CSVs are under results/native_load/. The native plan uses
60-second exploratory trials, one and three analysis processes, and preserves
the same 30-second target. It does not replace the required Docker experiment.
