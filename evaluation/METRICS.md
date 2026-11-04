# Current-agent evaluation definitions

The fixed set has 24 synthetic FNOL scenarios, expected classification,
coverage position and operational queue, and frozen policy-support chunks.
It includes the required food-delivery case. These labels need faculty
or claims-domain review and are not an insurer benchmark.

Run the batch from a configured live local-model environment:

```powershell
python -m evaluation.evaluate --output results/evaluation_v5.json
```

The runner reports:

| Metric | Computation |
| --- | --- |
| Groundedness proxy | Returned citations whose exact quotes resolve to retrieved chunks / all returned citations |
| Context relevance proxy | Retrieved chunk IDs matching frozen supporting IDs / all retrieved IDs |
| Faithfulness proxy | Share of scenarios whose classification, position and queue all match expected fields |
| Hallucination rate proxy | Returned citations that do not resolve / all returned citations |
| Reference recall | Frozen supporting chunks retrieved / all frozen supporting chunks |
| Verified rate | Share of runs accepted by the independent verifier |

Citation-based rates are undefined for abstentions without citations and
are reported as `null` with denominators. The faithfulness metric is a
structured outcome comparison, not unrestricted semantic truth. Matching
a frozen source ID can miss another valid supporting passage. Independent
reference-free semantic quality is scored separately on sampled live runs.

Run the same 24 scenarios with two **current v5** prompt variants before
claiming prompt-comparison or before/after quality results. This clean
repository contains only the current deployed prompt; that comparison
remains pending. Stub runs may test orchestration but cannot validate
real-model reasoning. Historic v1–v4 scores have been removed from this
repository tree.
