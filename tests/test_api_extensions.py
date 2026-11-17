import io
import json
import fakeredis
import pytest
from fastapi.testclient import TestClient
from app import api, jobs
from app.config import ROOT
from app.retrieval import index_corpus
from app.agents import analysis_graph as real_graph
from tests.test_system import Planner

@pytest.fixture
def extended_client(monkeypatch):
    index_corpus()
    connection = fakeredis.FakeRedis()
    monkeypatch.setattr(api, 'get_redis', lambda: connection)
    monkeypatch.setattr(jobs, 'redis_connection', lambda: connection)
    monkeypatch.setattr(jobs, 'analysis_graph', lambda gateway=None: real_graph(gateway=Planner()))
    return TestClient(api.app), connection

def valid_payload():
    return json.loads((ROOT / 'examples/valid.json').read_text())

def test_dashboard_stats_empty(extended_client):
    web, _ = extended_client
    res = web.get('/dashboard/stats')
    assert res.status_code == 200
    data = res.json()
    assert 'total_claims' in data
    assert 'agent_status' in data
    assert data['agent_status']['redis_connected'] is True

def test_list_runs_and_quarantine(extended_client):
    web, redis = extended_client
    
    # 1. Submit valid run
    sub = web.post('/runs', json=valid_payload())
    assert sub.status_code == 202
    run_id = sub.json()['run_id']

    # 2. Query /runs
    runs_res = web.get('/runs')
    assert runs_res.status_code == 200
    runs = runs_res.json()['runs']
    assert any(r['run_id'] == run_id for r in runs)

    # 3. Trigger validation error -> quarantine
    bad_payload = valid_payload()
    bad_payload['estimated_repair'] = -500
    bad_res = web.post('/runs', json=bad_payload)
    assert bad_res.status_code == 422
    qid = bad_res.json()['quarantine_id']

    # 4. Check /quarantine and /quarantine/{qid}
    q_list = web.get('/quarantine')
    assert q_list.status_code == 200
    assert any(q['quarantine_id'] == qid for q in q_list.json()['quarantined'])

    q_item = web.get(f'/quarantine/{qid}')
    assert q_item.status_code == 200
    assert q_item.json()['quarantine_id'] == qid

def test_document_extraction_text(extended_client):
    web, _ = extended_client
    sample_text = "ESTIMATE FOR REPAIR: Rs 14,500. Policy No: POL-2026-99. Reg: MH02CD5678. Loss Date: 2026-05-10."
    file_bytes = io.BytesIO(sample_text.encode('utf-8'))
    res = web.post('/documents/extract', files={'file': ('estimate.txt', file_bytes, 'text/plain')})
    assert res.status_code == 200
    data = res.json()
    assert data['filename'] == 'estimate.txt'
    assert data['suggestions']['estimated_repair'] == 14500.0
    assert data['suggestions']['policy_number'] == 'POL-2026-99'
    assert data['suggestions']['vehicle_registration'] == 'MH02CD5678'
    assert data['suggestions']['loss_date'] == '2026-05-10'

def test_document_extraction_unsupported_type(extended_client):
    web, _ = extended_client
    res = web.post('/documents/extract', files={'file': ('malicious.exe', io.BytesIO(b'binary'), 'application/octet-stream')})
    assert res.status_code == 422
    assert 'Unsupported file type' in res.json()['detail']['error']
