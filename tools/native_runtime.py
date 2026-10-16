"""Optional localhost native-process demo. Docker remains the assessed deployment."""
import argparse,json,os,subprocess,sys,socket,time
from pathlib import Path
from urllib.parse import urlsplit
import psutil,httpx
from dotenv import load_dotenv

ROOT=Path(__file__).resolve().parents[1]
load_dotenv(ROOT/'.env.native')
RUNTIME=Path(os.getenv('NATIVE_RUNTIME_DIRECTORY',str(ROOT/'.native_runtime'))).resolve()
RUNTIME.mkdir(parents=True,exist_ok=True)
PIDFILE=RUNTIME/'processes.json'

def stop(workers_only=False):
    if not PIDFILE.exists():return
    keep=[]
    for row in json.loads(PIDFILE.read_text()):
        if workers_only and row['name'] in ('safety','redis'):
            keep.append(row);continue
        try:
            process=psutil.Process(row['pid'])
            if abs(process.create_time()-row['created'])>.01:continue
            for child in process.children(recursive=True):child.terminate()
            process.terminate()
        except psutil.NoSuchProcess:pass
    PIDFILE.write_text(json.dumps(keep,indent=2))
    print('Stopped this native demonstration stack')

def start(workers,cache):
    required=['REDIS_URL','MODEL_URL','SAFETY_URL']
    for name in required:
        if not os.getenv(name):raise SystemExit('Copy .env.native.example to .env.native and configure '+name)
    for name in required:
        if urlsplit(os.environ[name]).hostname not in ('localhost','127.0.0.1'):
            raise SystemExit('Native helper accepts localhost endpoints only: '+name)
    procs=json.loads(PIDFILE.read_text()) if PIDFILE.exists() else []
    base=dict(os.environ,PYTHONPATH=str(ROOT),RETRIEVAL_CACHE=str(cache).lower())
    def listening(url):
        endpoint=urlsplit(url)
        try:
            with socket.create_connection((endpoint.hostname,endpoint.port or 80),timeout=1):return True
        except OSError:return False
    def launch(name,args,extra=None,executable=None):
        env=dict(base,SERVICE_NAME=name,TRACE_FILE=str(RUNTIME/'traces'/f'{name}.jsonl'),**(extra or {}))
        log=(RUNTIME/f'{name}-{int(time.time())}.log').open('w')
        proc=subprocess.Popen([executable or sys.executable,*args],cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0,start_new_session=os.name!='nt')
        procs.append({'name':name,'pid':proc.pid,'created':psutil.Process(proc.pid).create_time()})
        PIDFILE.write_text(json.dumps(procs,indent=2))
    if os.getenv('REDIS_EXECUTABLE') and not listening(os.environ['REDIS_URL']):
        endpoint=urlsplit(os.environ['REDIS_URL'])
        launch('redis',['--bind','127.0.0.1','--port',str(endpoint.port or 6379),'--dir',str(RUNTIME)],executable=os.environ['REDIS_EXECUTABLE'])
    if os.getenv('NATIVE_START_SAFETY','true').lower()=='true' and not listening(os.environ['SAFETY_URL']):
        assets=Path(os.environ['MODEL_ASSET_DIR']).resolve()
        env={('SAFETY_'+kind.upper()+'_PATH'):str(assets/kind) for kind in ('nli','injection','toxicity','embedding')}
        launch('safety',['-m','uvicorn','app.safety_service:app','--host','127.0.0.1','--port',str(urlsplit(os.environ['SAFETY_URL']).port)],env)
    with httpx.Client(timeout=30,trust_env=False) as client:
        for _ in range(90):
            try:
                if client.get(os.environ['SAFETY_URL'].rstrip('/')+'/health').status_code==200:break
            except httpx.HTTPError:pass
            time.sleep(1)
        else:raise SystemExit('Safety service did not become healthy')
    subprocess.run([sys.executable,'-m','app.preflight'],cwd=ROOT,env=base,check=True)
    if os.getenv('MODEL_MODE','stub')=='stub':
        launch('stub',['-m','uvicorn','app.stub:app','--host','127.0.0.1','--port',str(urlsplit(os.environ['MODEL_URL']).port)])
    launch('api',['-m','uvicorn','app.api:app','--host','127.0.0.1','--port',os.environ['API_PORT']])
    for i in range(workers):
        launch('analysis-'+str(i+1),['-m','app.worker'],{'AGENT_QUEUE':'analysis','METRICS_PORT':str(19101+i)})
    launch('verification',['-m','app.worker'],{'AGENT_QUEUE':'verification','METRICS_PORT':'19202'})
    PIDFILE.write_text(json.dumps(procs,indent=2));print(json.dumps(procs))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['start','stop'])
    parser.add_argument('--workers',type=int,default=1);parser.add_argument('--cache',choices=['on','off'],default='on')
    parser.add_argument('--workers-only',action='store_true')
    args=parser.parse_args()
    if args.action=='stop':stop(args.workers_only)
    else:start(args.workers,args.cache=='on')
