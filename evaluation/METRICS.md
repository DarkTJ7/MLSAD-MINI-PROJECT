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

The two research prompts are `v5a` (baseline) and `v5b` (focused field and
policy search guidance). To compare them, run both with the same live model,
same scenarios, safety service and corpus:

```powershell
python -m evaluation.evaluate --prompt-variant v5a --output results/prompt_v5a_live.json
python -m evaluation.evaluate --prompt-variant v5b --output results/prompt_v5b_live.json
python -m evaluation.compare results/prompt_v5a_live.json results/prompt_v5b_live.json
```

Repeat `--case-id ID` on both evaluation commands for a small matched smoke
sample. The comparison refuses differing case sets or model modes. A small
sample cannot establish a population accuracy rate. Stub runs test
orchestration but cannot validate real-model reasoning. Historic v1–v4
scores have been removed from this repository tree.

On 5 November 2026, the live local Qwen model and safety service completed
one matched `food-delivery` run per prompt. Both were faithful to the frozen
label and independently verified. v5a took 185.93 seconds and 7 provider
calls; v5b took 115.01 seconds and 6 provider calls. The v5a trace shows an
unnecessary `request_fields` call; v5b searched the policy instead. See
[`prompt_comparison_live.json`](../results/prompt_comparison_live.json) and
the two underlying run files in `results/`. This is a single sequential
sample, so timing can vary with local CPU load and does not establish p95.
