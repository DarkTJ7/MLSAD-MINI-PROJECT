"""Compare matched scenario runs without mixing live and stub measurements."""
import argparse
import json
import statistics
from pathlib import Path

def compare(a,b):
    if a['mode'] != b['mode']:
        raise ValueError('Both evaluations must use the same model mode')
    if a.get('model_id') != b.get('model_id'):
        raise ValueError('Both evaluations must use the same model ID')
    left={row['id']:row for row in a['runs']}
    right={row['id']:row for row in b['runs']}
    if set(left)!=set(right):
        raise ValueError('Both evaluations must contain identical scenario IDs')
    if a.get('prompt_variant')==b.get('prompt_variant'):
        raise ValueError('Prompt variants must differ')
    rows=[]
    for case_id in sorted(left):
        x,y=left[case_id],right[case_id]
        rows.append({'id':case_id,
                     'faithfulness':{a['prompt_variant']:x['metrics']['faithfulness'],b['prompt_variant']:y['metrics']['faithfulness']},
                     'verified':{a['prompt_variant']:x['metrics']['verified'],b['prompt_variant']:y['metrics']['verified']},
                     'seconds':{a['prompt_variant']:x['seconds'],b['prompt_variant']:y['seconds']},
                     'provider_calls':{a['prompt_variant']:sum(e.get('step')=='provider' for e in x['events']),
                                       b['prompt_variant']:sum(e.get('step')=='provider' for e in y['events'])}})
    return {'mode':a['mode'],'case_count':len(rows),'variants':[a['prompt_variant'],b['prompt_variant']],
            'summary':{v:{'faithfulness':sum(r['faithfulness'][v] for r in rows)/len(rows),
                          'verified':sum(r['verified'][v] for r in rows)/len(rows),
                          'median_seconds':statistics.median(r['seconds'][v] for r in rows)}
                       for v in (a['prompt_variant'],b['prompt_variant'])},'cases':rows}

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('first',type=Path);parser.add_argument('second',type=Path)
    parser.add_argument('--output',type=Path,default=Path('results/prompt_comparison.json'))
    args=parser.parse_args()
    report=compare(json.loads(args.first.read_text()),json.loads(args.second.read_text()))
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report['summary'],indent=2))

if __name__=='__main__':main()
