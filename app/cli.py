"""Direct terminal client for the two independently running agent workers."""
import argparse
import json
import os
import sys
import time
from pathlib import Path
import httpx
from dotenv import load_dotenv

def ask(label,default=None,convert=str):
    while True:
        answer=input(label+(f' [{default}]' if default is not None else '')+': ').strip()
        answer=answer or (str(default) if default is not None else '')
        if not answer:print('Please provide this detail.');continue
        try:return convert(answer)
        except (ValueError,TypeError):print('That value was not understood. Please try again.')

def yes_no(value):
    if value.lower() in ('yes','y'):return True
    if value.lower() in ('no','n'):return False
    if value.lower() in ('unknown','?'):return None
    raise ValueError()

def intake():
    print('\nMotor claim research agent\nDescribe the incident; I will collect the facts the research and verification agents need.')
    print('This produces advice only. You can type unknown for driver eligibility facts. Ctrl+C exits.\n')
    fnol={'description':ask('What happened?'),
          'policy_number':ask('Policy number'),'vehicle_registration':ask('Vehicle registration').upper(),
          'insurer':ask('Insurer','HDFC ERGO'),'country':ask('Country','India'),
          'location':ask('Incident location'),'loss_date':ask('Incident date (YYYY-MM-DD)'),
          'reported_date':ask('Reported date (YYYY-MM-DD)'),
          'policy_start':ask('Policy start (YYYY-MM-DD)'), 'policy_end':ask('Policy end (YYYY-MM-DD)'),
          'vehicle_use':ask('Vehicle use: personal / commute / business / delivery / hire_reward / unknown','unknown'),
          'estimated_repair':ask('Estimated repair in INR',convert=float),
          'idv':ask('Insured declared value in INR',convert=float),
          'network_garage':ask('Network garage? yes/no','no',yes_no),
          'driver_licensed':ask('Valid licence? yes/no/unknown','unknown',yes_no),
          'intoxicated':ask('Alcohol or drugs involved? yes/no/unknown','unknown',yes_no),
          'third_party_involved':ask('Third party involved? yes/no','no',yes_no),'retrieval_version':'v5'}
    print('\nYour incident:',fnol['description'])
    return fnol

def checked(response):
    if response.is_error:
        try:detail=response.json()
        except ValueError:detail=response.text[:500]
        raise RuntimeError(f'HTTP {response.status_code}: {json.dumps(detail,ensure_ascii=False)}')
    return response.json()

def event_line(event):
    agent=event.get('agent','system');kind=event.get('step');d=event.get('details',{})
    if kind=='narrative_audit':
        signal=d.get('narrative_use','unknown')
        conflict='; conflicts with structured vehicle use' if d.get('field_conflict') else ''
        quoted='; claimant phrase: '+d['evidence_phrase'] if d.get('evidence_phrase') else ''
        return f'[intake] narrative vehicle use: {signal}{conflict}{quoted}'
    if kind=='decision':return f"[{agent}] {d.get('action')}: {d.get('argument','')} | {d.get('purpose','')}"
    if kind=='tool':
        if d.get('observation',{}).get('error'):
            return f"[{agent}] tool refused: {d['observation']['error']}"
        return f"[{agent}] tool returned: {d.get('tool')} | {len(d.get('passages',[]))} passages" if d.get('tool')=='corpus_search' else f"[{agent}] tool returned: {d.get('tool')}"
    if kind=='verify':return '[verification] '+('Evidence accepted.' if d.get('verified') else 'Evidence refused; retry or human escalation required.')
    if kind=='provider':return f"[{agent}] model usage: {event.get('prompt_tokens',0)} input / {event.get('completion_tokens',0)} output tokens"
    return None

def show_result(item,trace):
    result=item.get('result') or {}
    print('\n--- VERIFIED ADVICE ---' if result.get('verified') else '\n--- HUMAN REVIEW REQUIRED ---')
    for key in ('classification','coverage_position','queue','reason','escalation'):
        print(key.replace('_',' ').capitalize()+': '+str(result.get(key,'')))
    print('\nEvidence:')
    for c in result.get('citations',[]):
        print(f"  {c['clause_id']} | {c['document']} page {c['page']}\n  {c['quote']}\n")
    if not result.get('citations'):print('  No verified citations; no coverage conclusion should be inferred.')
    print(f"Run: {item['run_id']} | Prompt: {result.get('prompt_version')} | API cost: ${trace.get('cost_usd',0):.6f}")
    print('A human claims handler makes the final decision. No approval, rejection or settlement is issued.')

def watch(client,run_id,timeout=420,output=None):
    seen=0;previous=None;deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        item=checked(client.get('/runs/'+run_id))
        trace=checked(client.get('/runs/'+run_id+'/trace'))
        if item['status']!=previous:
            print('[workflow] '+item['status'],flush=True);previous=item['status']
        events=trace.get('events',[])
        for e in events[seen:]:
            line=event_line(e)
            if line:print(line,flush=True)
        seen=len(events)
        if item['status'] in ('completed','escalated'):
            show_result(item,trace)
            if output:
                path=Path(output);path.parent.mkdir(parents=True,exist_ok=True)
                path.write_text(json.dumps({'run':item,'trace':trace},indent=2),encoding='utf-8')
                print('Saved result and agent actions to '+str(path))
            return item
        time.sleep(1)
    raise TimeoutError('Client wait ended; the run continues. Resume with: python -m app.cli watch '+run_id)

def main(argv=None):
    load_dotenv(Path(__file__).resolve().parents[1]/'.env.native')
    parser=argparse.ArgumentParser(description='Motor claim AI agents: intake, tool-driven research and independent verification.')
    parser.add_argument('--api-url',default=os.getenv('AGENT_API_URL') or os.getenv('DEMO_BASE_URL'))
    parser.add_argument('--allow-stub',action='store_true',help='Explicitly allow deterministic system tests instead of a real AI model')
    sub=parser.add_subparsers(dest='command',required=True)
    chat=sub.add_parser('chat');chat.add_argument('--output')
    run=sub.add_parser('run');run.add_argument('file');run.add_argument('--output')
    observe=sub.add_parser('watch');observe.add_argument('run_id');observe.add_argument('--output')
    feedback=sub.add_parser('feedback');feedback.add_argument('run_id');feedback.add_argument('--satisfactory',choices=['yes','no'],required=True);feedback.add_argument('--reason',required=True)
    args=parser.parse_args(argv)
    if not args.api_url:parser.error('Set AGENT_API_URL or pass --api-url for the running agent service.')
    try:
        with httpx.Client(base_url=args.api_url.rstrip('/'),timeout=60,trust_env=False) as client:
            health=checked(client.get('/health'))
            if args.command in ('chat','run') and health.get('planner_mode')!='live' and not args.allow_stub:
                raise RuntimeError('The service is in stub mode. Start a real local model, or use --allow-stub explicitly for system testing.')
            if args.command=='feedback':
                checked(client.post('/runs/'+args.run_id+'/feedback',json={'satisfactory':args.satisfactory=='yes','reason':args.reason}))
                print('Feedback saved.');return 0
            if args.command=='watch':watch(client,args.run_id,output=args.output);return 0
            body=intake() if args.command=='chat' else json.loads(Path(args.file).read_text(encoding='utf-8-sig'))
            body['retrieval_version']='v5'
            submission=checked(client.post('/runs',json=body))
            print('Run accepted: '+submission['run_id'],flush=True)
            print('Independent workers: research -> verification -> verified advice or human review.',flush=True)
            watch(client,submission['run_id'],output=args.output)
            return 0
    except KeyboardInterrupt:print('\nClient stopped. An accepted run may still be processing.');return 130
    except (httpx.HTTPError,RuntimeError,ValueError,OSError,TimeoutError) as exc:
        print('Agent client: '+str(exc),file=sys.stderr);return 1

if __name__=='__main__':raise SystemExit(main())
