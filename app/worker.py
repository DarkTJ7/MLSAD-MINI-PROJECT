import os
from rq import SimpleWorker
from prometheus_client import start_http_server
from .config import redis_connection
from .telemetry import setup

if __name__=='__main__':
    setup()
    # Readiness means corpus imports/index are warm, not merely a live process.
    from .retrieval import get_corpus
    get_corpus()
    from . import jobs  # Warm graph/contract imports before consuming the first job.
    start_http_server(int(os.environ['METRICS_PORT']))
    # Single process per container keeps Prometheus observations in the exporter process.
    # Scale containers for concurrency; Unix RQ job timeout still bounds each job.
    if os.name=='nt':
        from rq.timeouts import TimerDeathPenalty
        SimpleWorker.death_penalty_class=TimerDeathPenalty
    SimpleWorker([os.environ['AGENT_QUEUE']],connection=redis_connection()).work(with_scheduler=os.name!='nt')
