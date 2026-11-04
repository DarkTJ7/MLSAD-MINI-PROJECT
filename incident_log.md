# Genuine AI-agent development incidents

All cases below used synthetic FNOLs. The recorded result was human review,
not an unsupported claim determination.

## 4 November 2026 — model text triggered a tool guard

**Symptom:** the paid-meal paraphrase was correctly identified as delivery
use, but a subsequent model decision was stopped by
`tool_argument_guardrail`. The run escalated. The
[trace](results/narrative_audit_guardrail_failure.json) preserves the
run ID, intake signal and terminal response.

**Diagnosis and correction:** the safety check screened the model's entire
action object, including its display-only purpose. Tool arguments remain
screened and an unsafe argument still fails closed. A flagged purpose is
replaced with a neutral display note; an unavailable safety service
continues to fail closed. A regression checks that replacement.

## 4 November 2026 — voluntary escalation before modifier research

**Symptom:** the small model recognised the narrative conflict and
retrieved cover/procedure evidence, then chose escalation before making
a separate use-limitation search. The
[trace](results/narrative_audit_early_escalation_failure.json) records
the premature stop.

**Diagnosis and correction:** the available-action gate now requires a
targeted modifier attempt while research budget remains. The subsequent
[live run](results/clean_agent_live.json) searched private-car use
limitations and passed independent verification. The model also made an
irrelevant request-fields call; this is visible in the trace and did not
affect the verified recommendation.

These runs demonstrate failure handling on individual examples. They do
not establish an overall model failure rate.
