"""All deployment-specific values come from runtime configuration."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = Path(os.getenv('DATA_DIR', str(ROOT / 'data')))
DATA.mkdir(parents=True, exist_ok=True)

def required(name):
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f'Set {name}; see .env.example')
    return value

def redis_connection():
    from redis import Redis
    return Redis.from_url(required('REDIS_URL'),protocol=2)
