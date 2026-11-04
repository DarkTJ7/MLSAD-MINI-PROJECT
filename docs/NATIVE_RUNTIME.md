# Optional native terminal-agent runtime

Docker Compose is the assessed deployment. This path is useful on Windows
before Docker Desktop is available. It needs Python 3.12 or 3.13, a local
Redis-compatible server, and a separately installed llama.cpp server. The
model is local and needs no hosted API key.

1. Create a virtual environment and install `requirements.txt`.
2. Copy `.env.native.example` to `.env.native`. Set `MODEL_MODE=live`,
   `MODEL_URL` to the local llama.cpp chat-completions URL,
   `MODEL_ID` to the local alias, `MODEL_TIMEOUT_SECONDS=90`,
   `RUN_TIMEOUT_SECONDS=360`, and token prices to `0`.
3. Download checksum-verified safety and planner assets:

   ```powershell
   $env:MODEL_ASSET_DIR = '.native_runtime/models'
   $env:MODEL_MANIFEST_PATH = 'corpus/model_manifest.json'
   python -m app.model_assets
   $env:MODEL_MANIFEST_PATH = 'corpus/agent_planner_manifest.json'
   python -m app.model_assets
   python -m app.retrieval
   ```

4. Start llama.cpp on the configured localhost port with
   `.native_runtime/models/planner.gguf`. Start Redis, or set
   `REDIS_EXECUTABLE` in `.env.native` to an existing local executable.
5. Start the managed API, safety, research and verification processes:

   ```powershell
   python tools/native_runtime.py start --workers 1 --cache on
   python -m app.cli --api-url http://127.0.0.1:18766 chat
   ```

The helper owns only the processes it records in `.native_runtime/`. Stop
them with `python tools/native_runtime.py stop`. It does not install or
stop a separately managed llama.cpp server. Use synthetic FNOLs only.
See [the agent guide](AGENT_GUIDE.md) for behavior and
[the report](../Motor_Insurance_Agent_Report.pdf) for evidence limits.
