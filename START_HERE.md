# Start here

1. Read docs/AGENT_GUIDE.md for the redesigned v5 AI agents and terminal commands.
2. Start the support services, then use `python -m app.cli --api-url YOUR_API_URL chat`.
   On this machine, `..\Start-Motor-Agent.ps1` starts local services and opens
   terminal chat; add `-Demo` to run the food-delivery example.
3. Use docs/PROJECT_PLAN.md for Evaluation 1 and docs/DEMO_AND_VIVA.md for Evaluation 2.
4. Review docs/REQUIREMENTS.md and docs/SUBMISSION_CHECKLIST.md before submission.

Included: source, official corpus with provenance, versioned prompts, 24 reference
scenarios, test evidence, before/after evaluation, API contracts, Compose and
monitoring configuration, runbook and genuine incident log.

Historical v1-v4 evidence: 39 passing regression tests, 12/12 learned safety/NLI checks, native
HTTP/browser demonstrations, connected traces and automatic sampled quality.
Real local-model outcome agreement: v1 19/24, v4 17/24; failures are retained.
Thirteen native load trials include process scaling and cache comparisons.
The three-worker, twenty-client post-fix trial verified 80/80 runs at p95 26.17 s.
Docker startup, container dashboards and Docker measurements remain pending.
Repository: https://github.com/DarkTJ7/MLSAD-MINI-PROJECT (private).
Add actual team names and confirm corpus/reference with faculty before submitting.

The printable report describes the earlier v1-v4 implementation. The agent guide
and results/AGENT_V5.md describe the redesign; historical metrics do not measure v5.
