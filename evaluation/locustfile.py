"""Locust custom event measures the entire run, not just POST latency."""
import json
import time
import os
from pathlib import Path
import gevent
from locust import HttpUser, task, between

BASE=json.loads((Path(__file__).parent/'scenarios.jsonl').read_text().splitlines()[0])['fnol']
class ClaimUser(HttpUser):
    wait_time=between(.2,.5)
    @task
    def triage(self):
        started=time.perf_counter();error=None;status='unknown'
        rid=None
        try:
            response=self.client.post('/runs',json=BASE,name='submit')
            if response.status_code!=202: raise RuntimeError('submission '+str(response.status_code))
            rid=response.json()['run_id']
            while time.perf_counter()-started<50:
                response=self.client.get('/runs/'+rid,name='poll')
                response.raise_for_status()
                item=response.json();status=item['status']
                if status=='completed' and not (item.get('result') or {}).get('verified'):
                    raise RuntimeError('unverified terminal recommendation')
                if status in ('completed','escalated'): break
                gevent.sleep(.25)
            if status!='completed': raise RuntimeError('terminal '+status)
        except Exception as exc:
            error=exc
        self.environment.events.request.fire(request_type='RUN',name='submission_to_terminal',
            response_time=(time.perf_counter()-started)*1000,response_length=0,exception=error,context={'status':status})
        if os.getenv('LOAD_EVENTS'):
            with open(os.environ['LOAD_EVENTS'],'a',encoding='utf-8') as log:
                log.write(json.dumps({'run_id':rid,'status':status,'seconds':time.perf_counter()-started,
                                      'error':str(error) if error else None,'terminal_time':time.time()})+'\n')
