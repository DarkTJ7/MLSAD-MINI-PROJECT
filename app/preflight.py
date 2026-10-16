"""Warm immutable policy safety checks before the service accepts claim work."""
import json,time
from .retrieval import get_corpus
from .semantic import scan_text
from .config import DATA

def run():
    started=time.monotonic();rows=get_corpus().rows;flagged=[]
    for i,row in enumerate(rows):
        report=scan_text(row['text'])
        if report['blocked']:flagged.append(row['clause_id'])
        print(json.dumps({'screened':i+1,'total':len(rows)}),flush=True)
    result={'policy_chunks_screened':len(rows),'flagged_for_review':flagged,'seconds':time.monotonic()-started,
            'note':'Warm policy safety cache only; no customer FNOL or coverage answer is cached.'}
    (DATA/'safety_preflight.json').write_text(json.dumps(result,indent=2))
    return result
if __name__=='__main__':print(json.dumps(run(),indent=2))
