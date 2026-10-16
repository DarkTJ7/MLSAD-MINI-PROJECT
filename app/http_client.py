"""Thread-safe connection pool shared by gateway and safety calls."""
from functools import lru_cache
import os
import httpx
from opentelemetry import trace
from opentelemetry.propagate import inject

@lru_cache(maxsize=1)
def client():
    return httpx.Client(trust_env=os.getenv('HTTP_TRUST_ENV','false').lower()=='true',
                        limits=httpx.Limits(max_connections=30,max_keepalive_connections=15))

def post(*args,**kwargs):
    with trace.get_tracer('triage').start_as_current_span('http.client',kind=trace.SpanKind.CLIENT) as span:
        headers=dict(kwargs.pop('headers',{}) or {});inject(headers)
        response=client().post(*args,headers=headers,**kwargs)
        span.set_attribute('http.status_code',response.status_code)
        return response
