"""Single-command runner for the complete ClaimTriage AI application stack."""
import os
import sys
import threading
import time
import uvicorn
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / '.env')

os.environ['USE_FAKEREDIS'] = os.getenv('USE_FAKEREDIS', 'true')
os.environ['SAFETY_REQUIRED'] = os.getenv('SAFETY_REQUIRED', 'false')
os.environ['MODEL_MODE'] = os.getenv('MODEL_MODE', 'stub')
os.environ['MODEL_URL'] = os.getenv('MODEL_URL', 'http://127.0.0.1:8001/v1/chat/completions')

from app.retrieval import index_corpus
index_corpus()

# Launch model stub if in stub mode and local endpoint specified
if os.getenv('MODEL_MODE') == 'stub' and '8001' in os.getenv('MODEL_URL', ''):
    from app.stub import app as stub_app
    stub_server = uvicorn.Server(uvicorn.Config(stub_app, host='127.0.0.1', port=8001, log_level='warning'))
    threading.Thread(target=stub_server.run, daemon=True).start()
    print("Started deterministic model stub on http://127.0.0.1:8001")

port = int(os.getenv('API_PORT', '8000'))
print(f"Starting ClaimTriage AI server on http://127.0.0.1:{port}")
print(f"Open browser client at: http://127.0.0.1:{port}/client")

from app.api import app as api_app
api_server = uvicorn.Server(uvicorn.Config(api_app, host='127.0.0.1', port=port, log_level='info'))
api_server.run()
