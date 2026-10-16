# Measured real local-model validation

Actual CPU llama.cpp b11669, Qwen2.5-0.5B-Instruct Q4_K_M, context 8192,
four generation threads, localhost OpenAI-compatible API. No paid provider.
GGUF source revision, SHA256 and 491400032-byte length: corpus/planner_manifest.json.
Safety/NLI/embedding model revisions and hashes: corpus/model_manifest.json.
The binaries/weights are downloaded artifacts, excluded from Git.

| Prompt | Exact structured outcome agreement | Verified answers | Prompt tokens | Completion tokens |
|---|---:|---:|---:|---:|
| v1 | 19/24 | 15/24 | 11439 | 438 |
| v2 | 12/24 | 6/24 | 22584 | 673 |
| v3 | 9/24 | 4/24 | 19071 | 552 |
| v4 | 17/24 | 13/24 | 26621 | 783 |

All variants used the same 24 frozen scenarios. v2 is the preserved earlier
verifier experiment; v1/v3/v4 use clause-preserving NLI. This is a small,
synthetic, non-expert-certified evaluation, not a population accuracy estimate.
All generation calls have actual provider usage and zero local API charges.
CPU, RAM and electricity are not priced. Quality-experiment durations are not
the separately controlled stub-based load-test measurements.

v1 has the highest aggregate agreement (19/24); v4 has 17/24. The v4 default
retains explicit modifier research and tool/source context, including successful
food-delivery research, rather than selecting solely on aggregate agreement.
It is not claimed to outperform v1 overall. v2/v3 regressions and seven v4
failures remain in the raw results. Unsupported evidence causes abstention.
The 0.5B model and lexical retriever still miss valid scenarios; production
readiness and universal legal reasoning are not established.

v4 exact citation groundedness: 100% over 13 returned verified answers;
learned groundedness mean: 0.9699 (n=13). Learned supported fraction: 1.0
(n=13); unsupported fraction: 0.0. Abstentions have null proposition scores
and still count in all-24 structured agreement. These conditional scores must
not be presented as 100% overall claim accuracy. Sentence cosine relevance:
0.1127 (n=19), a separate signal, not a probability.

Live HTTP evidence verifies normal, delivery, surveyor and outside-corpus
routing, quarantine, persisted feedback and sampled quality. A controlled
internal forged citation was refused, researched again and recovered with
canonical evidence. Browser evidence: live_browser.png. Connected trace:
137 spans, all parents resolved, API/analysis/verification/safety services.
