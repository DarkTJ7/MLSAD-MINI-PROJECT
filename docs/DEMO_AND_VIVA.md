# Ten-item live demonstration

1. Copy .env.example to .env. Run `docker compose up --build`. Wait for API health.
   Show README setup on a fresh clone; inspect indexer logs and source hash.
2. Submit examples/valid.json from the web form or REST. Show 202/run id, poll,
   routed recommendation, source page and exact quote. Open original PDF.
3. Open /runs/{id}/trace. Show each tool query, passages, prompt version, timings,
   token/cost events and verification outcome. Locate run_id spans in Jaeger.
   Note the disconnected parent-context limitation honestly.
4. Submit examples/malformed.json. Show 422 and quarantine id. Inspect Redis key;
   prove analysis queue count does not increase. Use automated API test as evidence.
5. Change insurer to another company. Show insufficient_evidence and handler path.
6. Run the unsupported-citation test; show verifier refuses the fabricated quote.
   Optional live fault injection requires a test-only hook not exposed by default.
7. Submit examples/injection.json. Show rejection before queue creation. Repeat
   with instruction in location to demonstrate all string fields are checked.
8. Set STUB_FAIL=true in .env and recreate model-stub. Submit two runs; inspect
   retry events, Redis circuit key, escalation. Restore false and wait cooldown.
9. Follow SLO.md load matrix. Change RATE_LIMIT_PER_MINUTE to 10000 only during
   isolated load experiment. `docker compose --profile load run --rm load`.
   Repeat with `docker compose up -d --scale agent-worker=3`; preserve RUN rows.
   Do not present the POST row as end-to-end p95. Report first failing concurrency.
10. Submit examples/food_delivery.json. Show accident cover plus use restriction,
    investigation recommendation, and schedule/endorsement caveat.

## Viva preparation
Why two agents? Independently deployed verifier can refuse analysis outputs and
scale/fail separately. Why retry? Search omissions differ from provider outages;
one modifier-search retry is allowed, then safe escalation. Why not always answer?
Unverified coverage can harm a customer and insurer. Why stub? Isolates platform
capacity from provider limits; it cannot establish real-model quality. Why p95?
Tail latency captures queueing and retries that averages conceal. Why no settlement?
Explicitly outside assignment scope. What does grounding measure? Exact citation
support here; it does not prove full legal/semantic correctness.

Bring actual clean-clone output, results JSON/CSV, relevant source pages, report,
requirement status matrix and a real incident entry. Rehearse with the whole team.
