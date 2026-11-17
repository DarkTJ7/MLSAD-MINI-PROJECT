from __future__ import annotations
import hashlib
import json
import time
import logging
import asyncio
from uuid import uuid4
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Request, Response, HTTPException, UploadFile, File, BackgroundTasks
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from rq import Queue

from .config import DATA, ROOT, redis_connection
from .contracts import FNOL, Feedback
from .guardrails import inspect
from .jobs import analyze, save
from .telemetry import setup, INDEX, FRESH, INGEST, carry, HTTP_REQUESTS
from opentelemetry import trace

setup()
app = FastAPI(
    title='Motor Insurance FNOL Triage',
    version='2.0.0',
    description='Advisory AI Agent for Motor Insurance Claims. Human handlers decide claims.'
)

def get_redis():
    return redis_connection()

# Serve static files from client directory
client_dir = ROOT / 'client'
if client_dir.exists():
    app.mount('/client/static', StaticFiles(directory=str(client_dir)), name='static_client')

@app.exception_handler(RequestValidationError)
async def invalid(request: Request, exc: RequestValidationError):
    errors = json.loads(json.dumps(exc.errors(), default=str))
    for error in errors:
        error.pop('input', None)
    qid = str(uuid4())
    # Restricted diagnostic storage. Do not persist rejected raw free text / credentials.
    try:
        conn = get_redis()
        conn.set('quarantine:' + qid, json.dumps({'errors': errors, 'time': time.time()}), ex=86400)
        conn.zadd('quarantine:index', {qid: time.time()})
    except Exception:
        return JSONResponse(status_code=503, content={'detail': 'Quarantine unavailable; no run created'})
    return JSONResponse(
        status_code=422,
        content={
            'quarantine_id': qid,
            'errors': errors,
            'reason': 'schema_validation_failed',
            'agent_started': False,
            'message': 'Claim input failed validation rules. Inspect quarantine record for field details.'
        }
    )

@app.middleware('http')
async def correlation(request: Request, call_next):
    request.state.correlation_id = str(uuid4())
    try:
        with trace.get_tracer('triage').start_as_current_span('http.' + request.method) as span:
            span.set_attribute('http.route', request.url.path)
            span.set_attribute('correlation_id', request.state.correlation_id)
            response = await call_next(request)
            span.set_attribute('http.status_code', response.status_code)
    except Exception:
        logging.getLogger('triage').exception('request_failed correlation_id=%s', request.state.correlation_id)
        response = JSONResponse(
            status_code=503,
            content={'detail': 'Service dependency unavailable', 'correlation_id': request.state.correlation_id}
        )
    route = getattr(request.scope.get('route'), 'path', 'unknown')
    HTTP_REQUESTS.labels(request.method, route, str(response.status_code)).inc()
    response.headers['X-Correlation-ID'] = request.state.correlation_id
    return response

RATE_SCRIPT = """local n=redis.call('INCR',KEYS[1]); if n==1 then redis.call('EXPIRE',KEYS[1],60) end; return n"""

@app.get('/', include_in_schema=False)
def home():
    return {
        'service': 'Motor Insurance Claim Research Agent',
        'primary_interface': 'python -m app.cli chat',
        'api_docs': '/docs',
        'browser_ui': '/client',
        'advisory_only': True
    }

@app.get('/client', include_in_schema=False)
def optional_client():
    return FileResponse(ROOT / 'client' / 'index.html')

@app.get('/health')
def health():
    import os
    get_redis().ping()
    if not (DATA / 'index' / 'metadata.json').exists():
        raise HTTPException(503, 'Corpus index missing')
    
    from .provider import Gateway
    gw = Gateway()
    is_gemini = gw.is_gemini()
    planner_mode = 'gemini' if is_gemini else os.getenv('MODEL_MODE', 'stub')
    model_id = os.getenv('GEMINI_MODEL', 'gemini-2.5-flash') if is_gemini else os.getenv('MODEL_ID', 'local-planner')

    return {
        'ok': True,
        'planner_mode': planner_mode,
        'model_provider': 'gemini' if is_gemini else ('local' if planner_mode == 'live' else 'stub'),
        'model_id': model_id,
        'gemini_configured': bool(os.getenv('GEMINI_API_KEY')),
        'semantic_required': os.getenv('SAFETY_REQUIRED', 'true').lower() == 'true'
    }

@app.get('/metrics', include_in_schema=False)
def metrics():
    path = DATA / 'index' / 'metadata.json'
    if path.exists():
        metadata = json.loads(path.read_text())
        INDEX.set(metadata['chunks'])
        FRESH.set(metadata['built_at'])
        INGEST.set(metadata['chunks_per_second'])
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

@app.post('/runs', status_code=202)
def submit(fnol: FNOL, request: Request, background_tasks: BackgroundTasks, run_mode: Optional[str] = None):
    import os
    connection = get_redis()
    client = hashlib.sha256(request.client.host.encode()).hexdigest()[:20]
    count = connection.eval(RATE_SCRIPT, 1, 'rate:' + client)
    if count > int(os.getenv('RATE_LIMIT_PER_MINUTE', '60')):
        raise HTTPException(429, 'Client rate limit; retry next minute')
    
    f = fnol.model_dump(mode='json')
    issue = inspect(f)
    if issue:
        qid = str(uuid4())
        connection.set('quarantine:' + qid, json.dumps({'guardrail': issue, 'time': time.time()}), ex=86400)
        connection.zadd('quarantine:index', {qid: time.time()})
        status_code = 503 if issue == 'safety_unavailable' else 422
        raise HTTPException(
            status_code,
            {
                'quarantine_id': qid,
                'reason': issue,
                'agent_started': False,
                'message': f'Input triggered security guardrail: {issue}. Record preserved under quarantine ID {qid}.'
            }
        )

    run_id = str(uuid4())
    now = time.time()
    is_inline = run_mode == 'inline' or request.headers.get('X-Run-Mode') == 'inline'
    state = {
        'run_id': run_id,
        'fnol': f,
        'submitted_at': now,
        'deadline': now + float(os.getenv('RUN_TIMEOUT_SECONDS', '45')),
        'events': [],
        'passages': [],
        'tool_calls': 0,
        'steps': 0,
        'inline': is_inline,
        'correlation_id': request.state.correlation_id
    }
    carry(state)
    trace.get_current_span().set_attribute('run_id', run_id)

    # Atomic submission pipeline: persist state, index run, and enqueue job.
    q = Queue('analysis', connection=connection)
    with connection.pipeline() as pipe:
        pipe.multi()
        pipe.set('run:' + run_id, json.dumps({'status': 'queued', 'state': state}), ex=86400)
        pipe.zadd('runs:index', {run_id: now})
        q.enqueue_call(analyze, args=(state,), timeout=max(1, int(state['deadline'] - now) + 5), pipeline=pipe)
        pipe.execute()

    # If run_mode=='inline' or requested via header/param, process directly in background task
    if run_mode == 'inline' or request.headers.get('X-Run-Mode') == 'inline':
        def execute_inline(st):
            try:
                analyze(st)
            except Exception as e:
                logging.getLogger('triage').error(f"Inline analysis error: {e}")
        background_tasks.add_task(execute_inline, state)

    return {
        'run_id': run_id,
        'status': 'queued',
        'poll_path': '/runs/' + run_id,
        'trace_path': '/runs/' + run_id + '/trace',
        'events_path': '/runs/' + run_id + '/events'
    }

@app.get('/runs')
def list_runs(limit: int = 50):
    connection = get_redis()
    run_ids = [r.decode() if isinstance(r, bytes) else r for r in connection.zrevrange('runs:index', 0, limit - 1)]
    if not run_ids:
        keys = list(connection.scan_iter(match='run:*', count=100))
        run_ids = [
            k.decode().split(':', 1)[1] if isinstance(k, bytes) else k.split(':', 1)[1]
            for k in keys
            if not k.endswith(b':circuit') and not k.endswith(b':failures')
        ]

    items = []
    for rid in run_ids[:limit]:
        raw = connection.get('run:' + rid)
        if not raw:
            continue
        try:
            item = json.loads(raw)
            state = item.get('state', {})
            fnol = state.get('fnol', {})
            prop = state.get('proposed', {})
            items.append({
                'run_id': rid,
                'status': item.get('status'),
                'policy_number': fnol.get('policy_number'),
                'vehicle_registration': fnol.get('vehicle_registration'),
                'submitted_at': state.get('submitted_at'),
                'completed_at': state.get('completed_at'),
                'classification': prop.get('classification') or state.get('classification'),
                'coverage_position': prop.get('coverage_position'),
                'queue': prop.get('queue'),
                'verified': state.get('verified', False),
                'cost_usd': state.get('cost_usd', 0),
                'reason': prop.get('reason'),
                'requires_human': prop.get('requires_human', True)
            })
        except Exception:
            continue

    items.sort(key=lambda x: x.get('submitted_at') or 0, reverse=True)
    return {'runs': items, 'total': len(items)}

@app.get('/dashboard/stats')
def dashboard_stats():
    connection = get_redis()
    all_runs = list_runs(limit=200)['runs']
    
    total = len(all_runs)
    processing = sum(1 for r in all_runs if r['status'] in ('queued', 'analyzing', 'verifying', 'retrying'))
    recommended = sum(1 for r in all_runs if r.get('coverage_position') == 'potentially_covered' and r.get('verified'))
    human_review = sum(1 for r in all_runs if r.get('coverage_position') in ('coverage_concern', 'insufficient_evidence') or r.get('status') == 'escalated')
    escalated = sum(1 for r in all_runs if r.get('status') == 'escalated')

    quarantine_count = 0
    try:
        quarantine_count = connection.zcard('quarantine:index') or len(list(connection.scan_iter(match='quarantine:*', count=200)))
    except Exception:
        pass

    from .provider import Gateway
    gw = Gateway()
    is_gemini = gw.is_gemini()
    import os
    planner_mode = 'gemini' if is_gemini else os.getenv('MODEL_MODE', 'stub')
    model_name = os.getenv('GEMINI_MODEL', 'gemini-2.5-flash') if is_gemini else os.getenv('MODEL_ID', 'local-planner')

    indexed_chunks = 0
    path = DATA / 'index' / 'metadata.json'
    if path.exists():
        try:
            indexed_chunks = json.loads(path.read_text()).get('chunks', 0)
        except Exception:
            pass

    return {
        'total_claims': total,
        'processing_claims': processing,
        'recommended_claims': recommended,
        'human_review_claims': human_review,
        'escalated_claims': escalated,
        'quarantined_claims': quarantine_count,
        'recent_activity': all_runs[:10],
        'agent_status': {
            'planner_mode': planner_mode,
            'model_provider': 'gemini' if is_gemini else ('local' if planner_mode == 'live' else 'stub'),
            'model_id': model_name,
            'gemini_configured': bool(os.getenv('GEMINI_API_KEY')),
            'safety_required': os.getenv('SAFETY_REQUIRED', 'true').lower() == 'true',
            'corpus_chunks_indexed': indexed_chunks,
            'redis_connected': True
        }
    }

@app.get('/runs/{run_id}')
def status(run_id: str):
    connection = get_redis()
    raw = connection.get('run:' + run_id)
    if not raw:
        raise HTTPException(404, 'Run not found or retention expired')
    item = json.loads(raw)
    if item['status'] not in ('completed', 'escalated') and time.time() > item['state']['deadline']:
        from .agents import escalate
        from .jobs import terminal
        state = escalate(item['state'], 'worker_or_queue_timeout')
        terminal(connection, state)
        item = {'status': 'escalated', 'state': state}
    state = item['state']
    return {
        'run_id': run_id,
        'status': item['status'],
        'result': state.get('proposed'),
        'trace_path': '/runs/' + run_id + '/trace',
        'events_path': '/runs/' + run_id + '/events',
        'elapsed_seconds': state.get('completed_at', time.time()) - state['submitted_at'],
        'submitted_at': state.get('submitted_at'),
        'completed_at': state.get('completed_at'),
        'verified': state.get('verified', False)
    }

@app.get('/runs/{run_id}/trace')
def run_trace(run_id: str):
    raw = get_redis().get('run:' + run_id)
    if not raw:
        raise HTTPException(404, 'Unknown run')
    item = json.loads(raw)
    state = item['state']
    return {
        'run_id': run_id,
        'status': item.get('status'),
        'events': state.get('events', []),
        'retrieved_passages': state.get('passages', []),
        'verified': state.get('verified', False),
        'cost_usd': state.get('cost_usd', 0),
        'trace_id': state.get('trace_id'),
        'semantic_report': state.get('semantic_report'),
        'quality': state.get('quality'),
        'narrative_audit': state.get('narrative_audit'),
        'research_history': state.get('research_history', []),
        'fnol': state.get('fnol', {})
    }

@app.get('/runs/{run_id}/events')
async def stream_run_events(run_id: str):
    """Server-Sent Events endpoint streaming real execution events as they occur."""
    connection = get_redis()
    raw = connection.get('run:' + run_id)
    if not raw:
        raise HTTPException(404, 'Unknown run')

    async def event_generator():
        last_seen = 0
        last_status = None
        max_poll_iterations = 240  # 2 minutes max
        for _ in range(max_poll_iterations):
            r = connection.get('run:' + run_id)
            if not r:
                yield f"event: error\ndata: {json.dumps({'error': 'Run not found'})}\n\n"
                break
            
            data = json.loads(r)
            current_status = data.get('status')
            state = data.get('state', {})
            events = state.get('events', [])
            
            # Send status update if changed
            if current_status != last_status:
                last_status = current_status
                yield f"event: status\ndata: {json.dumps({'status': current_status, 'elapsed': time.time() - state.get('submitted_at', time.time())})}\n\n"

            # Send new step events
            if len(events) > last_seen:
                for ev in events[last_seen:]:
                    yield f"event: step\ndata: {json.dumps(ev)}\n\n"
                last_seen = len(events)

            # Check if finished
            if current_status in ('completed', 'escalated'):
                yield f"event: complete\ndata: {json.dumps({'status': current_status, 'result': state.get('proposed'), 'verified': state.get('verified', False)})}\n\n"
                break

            await asyncio.sleep(0.5)

    return StreamingResponse(event_generator(), media_type='text/event-stream')

@app.post('/runs/{run_id}/feedback', status_code=201)
def feedback(run_id: str, body: Feedback):
    connection = get_redis()
    if not connection.exists('run:' + run_id):
        raise HTTPException(404, 'Unknown run')
    if inspect(body.model_dump()):
        raise HTTPException(422, 'Feedback guardrail')
    connection.rpush('feedback', json.dumps({'run_id': run_id, **body.model_dump(), 'time': time.time()}))
    return {'persisted': True}

@app.get('/quality')
def quality():
    connection = get_redis()
    feedback = [json.loads(x) for x in connection.lrange('feedback', -1000, -1)]
    points = []
    for rid in connection.zrange('quality:runs', -100, -1):
        raw = connection.get(b'run:' + rid if isinstance(rid, bytes) else 'run:' + rid)
        if raw:
            state = json.loads(raw)['state']
            points.append({
                'time': state.get('completed_at', 0),
                'verified': int(state.get('verified', False)),
                'cost_usd': state.get('cost_usd', 0),
                'quality': state.get('quality')
            })
    return {
        'feedback_count': len(feedback),
        'satisfactory': sum(x.get('satisfactory', False) for x in feedback),
        'points': points,
        'note': 'Sampled reference-free NLI and semantic relevance scores; not ground-truth claim accuracy.'
    }

@app.get('/quarantine')
def list_quarantine(limit: int = 50):
    connection = get_redis()
    records = []
    keys = list(connection.scan_iter(match='quarantine:*', count=100))
    for k in keys:
        if k.endswith(b':index'):
            continue
        raw = connection.get(k)
        if raw:
            qid = k.decode().replace('quarantine:', '') if isinstance(k, bytes) else k.replace('quarantine:', '')
            try:
                data = json.loads(raw)
                records.append({'quarantine_id': qid, **data})
            except Exception:
                continue
    records.sort(key=lambda x: x.get('time', 0), reverse=True)
    return {'quarantined': records[:limit], 'total': len(records)}

@app.get('/quarantine/{quarantine_id}')
def get_quarantine_record(quarantine_id: str):
    connection = get_redis()
    raw = connection.get('quarantine:' + quarantine_id)
    if not raw:
        raise HTTPException(404, 'Quarantine record not found or expired')
    return {'quarantine_id': quarantine_id, **json.loads(raw)}

@app.post('/documents/extract')
async def extract_document(file: UploadFile = File(...)):
    """Extract and validate text from supporting claim documents (PDF / TXT)."""
    filename = file.filename or 'document.txt'
    ext = Path(filename).suffix.lower()
    if ext not in ('.pdf', '.txt', '.json'):
        raise HTTPException(422, {
            'error': 'Unsupported file type',
            'detail': f"File '{filename}' has unsupported extension '{ext}'. Only .pdf, .txt, and .json files are accepted.",
            'action': 'Please upload your estimate or policy document as a PDF or text file.'
        })

    content = await file.read()
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(422, {
            'error': 'File too large',
            'detail': f'File size ({len(content)} bytes) exceeds the 5MB limit.',
            'action': 'Please upload a smaller file or extract relevant pages.'
        })

    extracted_text = ''
    if ext == '.pdf':
        try:
            import io
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(content))
            pages = []
            for i, page in enumerate(reader.pages[:10]):
                txt = page.extract_text() or ''
                if txt.strip():
                    pages.append(f"--- Page {i+1} ---\n{txt}")
            extracted_text = '\n\n'.join(pages).strip()
        except Exception as exc:
            raise HTTPException(422, {
                'error': 'PDF extraction failed',
                'detail': f'Unable to extract text layers: {str(exc)[:100]}',
                'action': 'Ensure the PDF has digital text rather than scanned images.'
            })
    else:
        try:
            extracted_text = content.decode('utf-8', errors='replace').strip()
        except Exception as exc:
            raise HTTPException(422, {
                'error': 'Decoding error',
                'detail': str(exc)[:100],
                'action': 'Ensure file is UTF-8 encoded.'
            })

    if not extracted_text:
        raise HTTPException(422, {
            'error': 'Empty document',
            'detail': 'The uploaded document contains no text.',
            'action': 'Please upload a document with readable text content.'
        })

    # Security check on extracted document
    issue = inspect({'document': extracted_text[:4000]})
    if issue:
        qid = str(uuid4())
        conn = get_redis()
        conn.set('quarantine:' + qid, json.dumps({'guardrail': issue, 'filename': filename, 'time': time.time()}), ex=86400)
        conn.zadd('quarantine:index', {qid: time.time()})
        raise HTTPException(422, {
            'error': 'Document quarantined',
            'quarantine_id': qid,
            'detail': f'Uploaded document triggered safety guardrail: {issue}',
            'action': 'Ensure the document does not contain prompt injection or disallowed instructions.'
        })

    # Pattern extraction for helpful form suggestions
    import re
    suggestions = {}
    
    # Repair estimate amount
    amount_match = re.search(r'(?:Rs\.?|INR|Total|Estimate|Amount)[:\s]*([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]{2})?|[0-9]{3,7})', extracted_text, re.I)
    if amount_match:
        try:
            suggestions['estimated_repair'] = float(amount_match.group(1).replace(',', ''))
        except Exception:
            pass

    # Policy number (e.g. DEMO-001, POL-2026-99, HDFC/123/456)
    pol_match = re.search(r'\b(?:Policy\s*(?:No|Number)?[:\s#]*)?([A-Za-z0-9]+(?:[-/][A-Za-z0-9]+)+)\b', extracted_text, re.I)
    if pol_match:
        suggestions['policy_number'] = pol_match.group(1).upper()

    # Vehicle registration (Indian format e.g. KA01AB1234, DL01C1234)
    reg_match = re.search(r'\b[A-Z]{2}[0-9]{1,2}[A-Z]{1,3}[0-9]{4}\b', extracted_text.upper())
    if reg_match:
        suggestions['vehicle_registration'] = reg_match.group(0)

    # Date
    date_match = re.search(r'\b(202[0-9]-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12][0-9]|3[01]))\b', extracted_text)
    if date_match:
        suggestions['loss_date'] = date_match.group(1)

    return {
        'filename': filename,
        'size_bytes': len(content),
        'characters_extracted': len(extracted_text),
        'snippet': extracted_text[:400] + ('...' if len(extracted_text) > 400 else ''),
        'suggestions': suggestions
    }
