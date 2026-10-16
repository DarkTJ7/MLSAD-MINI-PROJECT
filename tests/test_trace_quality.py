import json,time
import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from app.telemetry import carry,run_span
from app.quality import sample_score

def test_trace_parent_context_crosses_serialized_handoffs():
    exporter=InMemorySpanExporter();provider=trace.get_tracer_provider()
    if not hasattr(provider,'add_span_processor'):
        provider=TracerProvider();trace.set_tracer_provider(provider)
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    tracer=trace.get_tracer('integration')
    with tracer.start_as_current_span('submission'):
        state={'run_id':'trace-test','correlation_id':'cid'};carry(state)
    state=json.loads(json.dumps(state))
    with run_span(state,'analysis'):carry(state)
    state=json.loads(json.dumps(state))
    with run_span(state,'verification'):pass
    spans=exporter.get_finished_spans();by_name={s.name:s for s in spans}
    assert len({s.context.trace_id for s in spans})==1
    assert by_name['agent.analysis'].parent.span_id==by_name['submission'].context.span_id
    assert by_name['agent.verification'].parent.span_id==by_name['agent.analysis'].context.span_id

def test_sampled_quality_uses_semantic_results(monkeypatch):
    monkeypatch.setenv('QUALITY_SAMPLE_RATE','1');monkeypatch.delenv('SAFETY_URL',raising=False)
    state={'run_id':'quality-test','semantic_report':{'claims':[{'supported':True,'scores':{'entailment':.95}},
        {'supported':False,'scores':{'entailment':.1}}]},'passages':[],'proposed':{'verified':True}}
    score=sample_score(state)
    assert score['groundedness']==pytest.approx(.525)
    assert score['faithfulness']==.5 and score['hallucination_rate']==.5
