# Evaluation definitions and limits

Fixed set: 24 synthetic scenarios, with structured expected classification,
position and queue; supporting source chunks frozen in scenarios.jsonl. Labels
were prepared from the public corpus and operational demo rules. They require
faculty/domain review, particularly the food-delivery reference answer. They are
not an independently annotated insurer benchmark.

For each run:

| Metric | Exact implementation |
|---|---|
| Groundedness proxy | Exact quoted citations resolving to retrieved chunks / all returned citations |
| Context relevance proxy | Retrieved chunk IDs overlapping frozen reference chunk IDs / all retrieved chunk IDs |
| Faithfulness proxy | 1 when all three expected classification/position/queue fields match; else 0 |
| Hallucination rate proxy | Non-resolving or fabricated citations / all returned citations |
| Reference recall | Frozen reference chunks retrieved / frozen reference chunks |
| Verified rate | Fraction whose final recommendation passed the independent verifier |

Citation-based metrics are undefined on abstentions without citations; JSON uses
null and reports denominators explicitly. Never turn these into a perfect score.
All 24 runs enter outcome/faithfulness accuracy. Guarded and out-of-scope cases
count as correct only if the expected safe abstention matches.

"Faithfulness" here is a coarse structured-outcome proxy, not semantic entailment.
Groundedness/hallucination inspect citations, not every narrative claim. Reference
overlap may penalise an alternative valid chunk. These metrics are an equivalent
small explicit harness, not TruLens or an independent LLM judge. Add expert
annotation for stronger quality evidence. Independent semantic-claim scoring is
also supplied separately, with per-metric denominators.

Deliberate change: v1 searches apparent cover and finishes; v4 adds modifier
search, source lookup, explicit tool descriptions and stage-specific objectives.
Historical v2/v3 regressions and the first NLI input strategy are preserved.
The current v1/v4 comparison holds the corrected
clause-preserving verifier constant. Both still face independent verification.
Report before/after for all four required metrics, citation denominators and
structured accuracy. The stub has zero tokens/cost; it cannot predict live cost.
Provider call events record actual usage and runtime prices in live mode.

The original evaluation_v1/v2 JSON files preserve historical stub proxy results.
Current real_model_v1/v4 files use an actual local generative model and required
independent safety/NLI. Native load and Docker load are separate environments;
Docker remains unmeasured here. /quality now charts independently computed,
sampled reference-free quality metrics, not ground-truth claim accuracy.
See HARDENING.md for live metric definitions and the asynchronous scoring handoff.
