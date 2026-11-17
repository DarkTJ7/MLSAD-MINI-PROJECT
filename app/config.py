"""All deployment-specific values come from runtime configuration."""
from __future__ import annotations
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = Path(os.getenv('DATA_DIR', str(ROOT / 'data')))
DATA.mkdir(parents=True, exist_ok=True)

_FAKEREDIS_INSTANCE = None

def required(name):
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f'Set {name}; see .env.example')
    return value

def redis_connection():
    global _FAKEREDIS_INSTANCE
    redis_url = os.getenv('REDIS_URL', '')
    if os.getenv('USE_FAKEREDIS', 'false').lower() == 'true' or redis_url.startswith('fakeredis'):
        if _FAKEREDIS_INSTANCE is None:
            import fakeredis
            _FAKEREDIS_INSTANCE = fakeredis.FakeRedis()
        return _FAKEREDIS_INSTANCE
    from redis import Redis
    return Redis.from_url(required('REDIS_URL'), protocol=2)
