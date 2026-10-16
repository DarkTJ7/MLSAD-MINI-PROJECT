# Runbook

## 1. Model provider timeout or outage

Symptom: provider retries, provider_unavailable/circuit_open escalation, completed
recommendation rate drops. API can remain healthy while reasoning is degraded.

Confirm: inspect `docker compose logs agent-worker model-stub`, run trace provider
events, retry metric and Redis `provider:circuit` timestamp. Verify MODEL_URL,
MODEL_MODE, network reachability and (for live) account quota without printing keys.
An absolute deadline should prevent a stuck run being presented as confident.

Recover: restore reachable model service/configuration. For stub set STUB_FAIL=false
and `docker compose up -d --force-recreate model-stub`; wait cooldown (default 20s)
then submit a new synthetic smoke case. Restore worker config if changed and recreate
workers. Inspect failure cause before clearing a circuit key manually. Never
silently convert failed runs to success. Existing explicit escalations remain
auditable; a handler can request a new run.

Demonstrate: set STUB_FAIL=true, recreate stub, submit two ordinary cases; watch
three call attempts per failing gateway call, circuit opening, and safe escalation.

## 2. Queue/worker or corpus readiness failure

Symptom: 503 during intake, queued run stays pending, health fails, or indexer exits.

Confirm: `docker compose ps`; `docker compose logs redis indexer agent-worker
verification-worker`. Inspect Redis queue lengths and failed/started job registries.
Check corpus metadata/source hash and index file presence. An expired queued run
polled through the API must escalate as worker_or_queue_timeout.

Recover: restore Redis volume/network, restart worker service, then run smoke case.
For a broken/missing index stop both worker services, run the indexer, then restart
workers. Do not modify index files concurrently with readers. Do not delete Redis
volumes to clear a queue: that also destroys feedback and incident evidence.
RQ worker crash recovery may require reviewing/requeueing an abandoned job in its
registry; verify its deadline first and submit a fresh run if expired. Duplicate
execution/finalisation remains a known production hardening gap.

## Evidence and configuration

Local-only deployment. Run traces contain synthetic claim facts/passages, not
secrets. Retain report, test output and load CSV separately from transient logs.
All run IDs are UUIDs and correlation IDs are server generated. Feedback is
persisted but unbounded in this prototype; implement explicit retention before
real customer use. Record each real development/rehearsal failure in incident_log.md.
