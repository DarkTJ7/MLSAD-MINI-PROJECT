# Native demonstration and measurement reproduction

Docker remains the assessed deployment. This optional path reproduces the
explicitly labelled native-process measurements when Docker is unavailable.

Use Python 3.12 or 3.13. Create a virtual environment, activate it and install
requirements.txt. Copy .env.native.example to .env.native. Use synthetic data.
Set REDIS_URL to a running local Redis-compatible server. If using a previously
installed native Redis executable, set REDIS_EXECUTABLE to its absolute path.
The authoring measurement used the community Windows Redis 5.0.14.1 port from
https://github.com/tporadowski/redis/releases/tag/v5.0.14.1 and RESP2; the assessed
Docker setup instead specifies Redis 7.4. They are separate environments.

Load the .env.native entries into your shell, then download verified model data:

```powershell
$env:MODEL_ASSET_DIR = '.native_runtime/models'
$env:MODEL_MANIFEST_PATH = 'corpus/model_manifest.json'
python -m app.model_assets
python -m app.retrieval
python tools/native_runtime.py start --workers 1 --cache on
```

The helper reads .env.native, launches localhost-only API/stub/safety and distinct
analysis/verification processes, and records process IDs and JSON span files in
.native_runtime/. Wait for both worker metrics endpoints and /health before a
request: worker readiness includes warming the corpus. Use the API_PORT from
.env.native in your browser. Run the HTTP demo with DEMO_BASE_URL configured:

```powershell
$env:DEMO_BASE_URL = 'http://127.0.0.1:18766'
python -m evaluation.live_demo
python tools/measure_native.py
```

The measurement harness restarts its own stack when worker count/cache changes,
checks worker readiness, warms the corpus, and runs the predeclared Locust matrix.
Reproduction results use results/native_load_reproduction/ to preserve the original
evidence. Stop with `python tools/native_runtime.py stop`. Do not use the helper
to stop a separately managed Redis/model server; it only owns recorded child PIDs.

## Optional real local planner

The validated authoring runtime uses a CPU llama.cpp server and a small GGUF
instruction model, with artifact provenance recorded in results/REAL_MODEL.md.
Weights and runtime executables are downloaded data/tools, not committed source.
Start your model's OpenAI-compatible server separately on localhost. Set MODEL_MODE
to live, MODEL_URL to its chat-completions URL, MODEL_ID as required by that server,
and input/output API prices to zero for local inference. Set MODEL_TIMEOUT_SECONDS
and RUN_TIMEOUT_SECONDS for a separate live-model quality experiment; do not
silently change the stub SLO target. Compare both prompt versions on the same set:

```powershell
python -m evaluation.evaluate --version v1 --output results/real_model_v1.json
python -m evaluation.evaluate --version v4 --output results/real_model_v4.json
```

The native helper leaves a live model server under its existing owner's control.
Read the real-model results and semantic abstentions, not just JSON-format success.
