"""Real native process measurements; explicitly not container performance."""
import os,subprocess,time,json,statistics,sys
from dotenv import load_dotenv
from pathlib import Path
import httpx
root=Path(__file__).resolve().parents[1];load_dotenv(root/'.env.native');python=Path(sys.executable);base_url=os.environ['DEMO_BASE_URL'].rstrip('/')
results=root/'results/native_load_reproduction';results.mkdir(exist_ok=True)
plan={'environment':'Windows native processes; Redis 5.0.14.1 community port; NOT DOCKER',
      'declared_before_run':time.time(),'stub_delay_seconds':.35,'slo_p95_seconds':30,
      'target_valid_completed_fraction':.95,'duration_seconds':60,'stop_timeout_seconds':50,
      'matrix':[(1,True,1),(1,True,5),(1,True,10),(1,True,20),(3,True,5),(3,True,10),(3,True,20),(1,False,5),(3,False,5)]}
(results/'plan.json').write_text(json.dumps(plan,indent=2))
summaries=[]
base=json.loads((root/'examples/valid.json').read_text())
def warm():
    with httpx.Client(timeout=30,trust_env=False) as client:
        for _ in range(90):
            try:
                if client.get(base_url+'/health').status_code==200:break
            except httpx.HTTPError:pass
            time.sleep(1)
        # Warm corpus/model caches, but do not count warmup in measurements.
        response=client.post(base_url+'/runs',json=base);response.raise_for_status()
        rid=response.json()['run_id']
        for _ in range(250):
            item=client.get(base_url+'/runs/'+rid).json()
            if item['status'] in ('completed','escalated'):
                if item['status']!='completed':raise RuntimeError('Warmup did not produce verified recommendation: '+json.dumps(item))
                return
            time.sleep(.2)
        raise RuntimeError('Warmup timeout')

previous=None
for workers,cache,users in plan['matrix']:
    label=f'w{workers}_cache{int(cache)}_u{users}'
    env=dict(os.environ,NATIVE_ANALYSIS_WORKERS=str(workers),RETRIEVAL_CACHE=str(cache).lower(),QUALITY_SAMPLE_RATE='.25')
    if previous!=(workers,cache):
        subprocess.run([str(python),str(root/'tools/native_runtime.py'),'stop','--workers-only'],check=True)
        subprocess.run([str(python),str(root/'tools/native_runtime.py'),'start','--workers',str(workers),'--cache','on' if cache else 'off'],check=True,env=env)
        with httpx.Client(timeout=2,trust_env=False) as client:
            for _ in range(180):
                try:
                    ports=[19101+i for i in range(workers)]+[19202]
                    if all(client.get(f'http://127.0.0.1:{port}/metrics').status_code==200 for port in ports):break
                except httpx.HTTPError:pass
                time.sleep(1)
            else:raise RuntimeError('Workers not ready after corpus warmup')
        previous=(workers,cache)
    warm()
    events=results/(label+'.jsonl');events.write_text('')
    runenv=dict(env,LOAD_EVENTS=str(events))
    started=time.monotonic()
    with (results/(label+'.log')).open('w') as log:
        process=subprocess.run([str(python),'-m','locust','-f','evaluation/locustfile.py','--host',base_url,
            '--headless','-u',str(users),'-r',str(users),'-t','60s','--stop-timeout','50','--csv',str(results/label)],
            cwd=root,env=runenv,stdout=log,stderr=subprocess.STDOUT,timeout=150)
    elapsed=time.monotonic()-started
    rows=[json.loads(line) for line in events.read_text().splitlines()]
    seconds=sorted(x['seconds'] for x in rows)
    def percentile(q):
        if not seconds:return None
        index=(len(seconds)-1)*q;low=int(index);high=min(len(seconds)-1,low+1)
        return seconds[low]+(seconds[high]-seconds[low])*(index-low)
    completed=sum(x['status']=='completed' and not x['error'] for x in rows)
    p95=percentile(.95)
    report={'label':label,'workers':workers,'retrieval_cache':cache,'clients':users,'terminal_runs':len(rows),
        'completed':completed,'errors':len(rows)-completed,'measurement_wall_seconds':elapsed,
        'completed_rps':completed/elapsed,'terminal_rps':len(rows)/elapsed,'p50_seconds':percentile(.5),'p95_seconds':p95,
        'success_fraction':completed/len(rows) if rows else 0,'slo_met':bool(p95 is not None and p95<=30 and rows and completed/len(rows)>=.95),
        'locust_exit_code':process.returncode}
    summaries.append(report)
    (results/'summary.json').write_text(json.dumps({'plan':plan,'measurements':summaries},indent=2))
    print(json.dumps(report),flush=True)
print('Native benchmark finished; Docker remains unmeasured',flush=True)
