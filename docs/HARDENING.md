# Verification, guardrails, tracing and live scoring

## Independent semantic verification

The verification service now combines four checks before a recommendation can be
marked verified: canonical source/hash/page/quote resolution, immutable advisory
flags and allowlisted draft templates, risk/route consistency, and a separate CPU
natural-language-inference model. The model scores explicit propositions against
the actual cited policy passages. Neutral, contradictory, unavailable or low-score
evidence fails verification. One bounded modifier-search retry is allowed, then
the run escalates. The handler still decides the claim.

The use-restriction proposition is deliberately limited to what the public
wording establishes: it contains restrictions on vehicle use. The system does not
turn a missing customer schedule into a definitive exclusion of all deliveries.
It cites both the use clause and FAQ hire/reward passage, flags the narrative's
delivery use, and recommends investigation/human schedule review.

New failure checks include a real source quote attached to invented reasoning,
forged retrieved text, a false requires_human flag, missing semantic service and
encoded attack variants. Exact matching alone would not catch all these cases.

## Injection and toxicity defence

All free-text fields and every retrieved passage that can reach the planner are
screened. Normalisation covers NFKC, zero-width format characters, HTML entities,
URL escapes and printable base64 payloads. Lexical policy checks and an independent
prompt-injection classifier both apply. Overlapping windows inspect the full text,
including its tail. The planner has only three allowlisted read-only tools; its
JSON action schema cannot add arbitrary tools, commands, URLs or tool arguments.

Input and output also pass a separate multilabel toxicity classifier. Output has
immutable human-review/advisory flags, bounded templates and determination filters.
The input injection classifier is not used to reject an allowed human-review
instruction in the final output: a real test exposed that false positive. Such
output cannot invoke any further tool. Toxicity and determination checks still
apply. Missing required safety infrastructure fails closed.

These controls are implemented and testable, not a guarantee of universal attack
coverage. English-trained classifiers have language/domain limits and possible
false positives/negatives. Thresholds are runtime configuration and require domain
calibration. Do not equate a finite passing attack suite with complete security.

## Model assets

Four CPU ONNX models provide entailment, prompt-injection detection, toxicity and
sentence embeddings. corpus/model_manifest.json pins immutable source revisions,
file hashes and sizes. app.model_assets downloads and verifies only data files;
no remote model Python code is executed. Compose's one-shot model-assets service
fills a named volume before the safety container becomes healthy. Large model
weights are not committed to GitHub. The first startup needs network access and
roughly 1 GB of safety-model downloads, plus Python/container dependencies.
The policy-preflight service then screens the immutable policy chunks before
the API accepts claim work. In the recorded native preflight, 83 chunks took
188.82 seconds and five were flagged for review. These flags are preserved in
results/policy_preflight.json; they are not automatically overridden as benign.
This warms public-policy safety checks, never customer FNOL answers. Native
readiness also includes graph/contract imports, not just a running Python process.

## Connected trace

Submission creates a root OpenTelemetry span. W3C traceparent is serialised into
the queued state; analysis and verification extract it and create CONSUMER spans.
Every gateway/safety HTTP call creates a CLIENT span and injects its context. The
safety service extracts that header into SERVER spans. Quality scoring continues
the same trace after completion. All steps carry the run/correlation identifiers.

OTLP export feeds Jaeger in Compose; TRACE_FILE provides JSON span evidence in the
native demonstration. Tests verify shared trace IDs and exact parent relationships
after serialisation. The durable run trace also retains prompts, passages, tool
queries, cost, semantic scores and verification decisions. Secrets are excluded.

## Live scoring and dashboards

After first-writer-wins terminal persistence, a separate queued scoring job selects
a reproducible sample using a hash of run_id. It does not delay final intake
results. Groundedness is mean entailment probability over the checked propositions;
faithfulness is the supported fraction; unsupported-claim rate is the complement;
context relevance is mean sentence-embedding cosine between FNOL and retrieved
passages. Abstentions without propositions have null scores, not perfect scores.
These are reference-free quality indicators, not insurer-labelled claim accuracy.

Scores are persisted, returned by /quality and /runs/{id}/trace, charted over time
in the web client, and exported to Prometheus. Feedback remains separately labelled.
Grafana now has 28 panels, including all four scores, per-agent task success,
steps/tools/retries per task, step p95, Redis health and cAdvisor CPU, working set,
uptime, filesystem and network metrics by Compose service. Prometheus targets all
long-running application/monitoring services. Docker dashboards remain unexecuted
until Docker is available; native measurements must not be relabelled as container
measurements. cAdvisor requires Docker's Linux host paths and compatible cgroups.
The pinned cAdvisor 0.55.1 configuration follows the official host-monitoring
mount/device setup, including privileged access and /dev/kmsg. It is an
infrastructure monitor, not an application agent. Validate those host paths on
Docker Desktop before rehearsal; container validation remains pending.
Reference: https://github.com/google/cadvisor#quick-start-running-cadvisor-in-a-docker-container
