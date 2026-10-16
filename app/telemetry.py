import json
import logging
import os
import time
from contextlib import contextmanager
from prometheus_client import Counter, Histogram, Gauge
from opentelemetry import trace
from opentelemetry.propagate import inject,extract

logging.basicConfig(level=logging.INFO, format='%(message)s')
LOG = logging.getLogger('triage')
STEPS = Counter('triage_steps_total', 'Agent steps', ['agent', 'outcome'])
LATENCY = Histogram('triage_step_seconds', 'Step latency', ['agent', 'step'])
RUN_LATENCY = Histogram('triage_run_seconds', 'Submission to terminal result', buckets=(1,2,5,10,20,30,45,60,90,120))
TOOLS = Counter('triage_tool_calls_total', 'Tool calls', ['agent','tool'])
RETRIES = Counter('triage_retries_total', 'Provider retry count', ['agent'])
COST = Counter('triage_cost_usd_total', 'Recorded provider cost', ['agent'])
START = Gauge('triage_process_started_seconds', 'Process start epoch')
START.set(time.time())
INDEX = Gauge('triage_index_chunks', 'Indexed chunks')
FRESH = Gauge('triage_index_built_seconds', 'Corpus build epoch')
INGEST = Gauge('triage_ingest_chunks_per_second', 'Last indexing throughput')
TASKS=Counter('triage_agent_tasks_total','Agent task outcomes',['agent','outcome'])
QUALITY=Histogram('triage_live_quality','Sampled live quality metrics',['metric'],buckets=(0,.2,.4,.6,.8,1))
HTTP_REQUESTS=Counter('triage_http_requests_total','API responses',['method','route','status'])

def carry(state):
    carrier={};inject(carrier);state['trace_carrier']=carrier
    state['trace_id']=format(trace.get_current_span().get_span_context().trace_id,'032x')

@contextmanager
def run_span(state,agent):
    with trace.get_tracer('triage').start_as_current_span('agent.'+agent,context=extract(state.get('trace_carrier',{})),kind=trace.SpanKind.CONSUMER) as span:
        span.set_attribute('run_id',state['run_id'])
        span.set_attribute('correlation_id',state.get('correlation_id',state['run_id']))
        carry(state)
        yield

def setup():
    if os.getenv('OTEL_EXPORTER_OTLP_ENDPOINT') or os.getenv('TRACE_FILE'):
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        provider = TracerProvider(resource=Resource.create({'service.name':os.getenv('SERVICE_NAME','triage')}))
        if os.getenv('OTEL_EXPORTER_OTLP_ENDPOINT'):
            provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(timeout=5)))
        if os.getenv('TRACE_FILE'):
            from opentelemetry.sdk.trace.export import SpanExporter,SpanExportResult,SimpleSpanProcessor
            from pathlib import Path
            class FileExporter(SpanExporter):
                def export(self,spans):
                    path=Path(os.environ['TRACE_FILE']);path.parent.mkdir(parents=True,exist_ok=True)
                    with path.open('a',encoding='utf-8') as handle:
                        for span in spans:
                            handle.write(json.dumps({'name':span.name,'trace_id':format(span.context.trace_id,'032x'),
                                'span_id':format(span.context.span_id,'016x'),'parent_id':format(span.parent.span_id,'016x') if span.parent else None,
                                'attributes':dict(span.attributes),'start':span.start_time,'end':span.end_time})+'\n')
                    return SpanExportResult.SUCCESS
            provider.add_span_processor(SimpleSpanProcessor(FileExporter()))
        trace.set_tracer_provider(provider)

@contextmanager
def step(state, agent, name, details=None):
    started = time.monotonic()
    with trace.get_tracer('triage').start_as_current_span(name) as span:
        span.set_attribute('run_id', state['run_id'])
        span.set_attribute('agent', agent)
        span.set_attribute('correlation_id',state.get('correlation_id',state['run_id']))
        span.set_attribute('prompt_version',state['fnol']['retrieval_version'])
        outcome = 'success'
        try:
            yield
        except Exception:
            outcome = 'error'
            raise
        finally:
            elapsed = time.monotonic()-started
            event = {'run_id':state['run_id'], 'agent':agent, 'step':name,
                     'seconds':elapsed, 'outcome':outcome, 'details':details or {},
                     'time':time.time(), 'prompt_version':state['fnol']['retrieval_version']}
            state.setdefault('events', []).append(event)
            LOG.info(json.dumps(event))
            STEPS.labels(agent,outcome).inc()
            LATENCY.labels(agent,name).observe(elapsed)
