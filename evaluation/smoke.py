"""CLI smoke run using the configured HTTP planner (requires running stub/provider)."""
import argparse,json
from pathlib import Path
from app.agents import run_local
from app.retrieval import index_corpus

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('fnol',type=Path);args=parser.parse_args()
    index_corpus()
    state=run_local(json.loads(args.fnol.read_text()))
    print(json.dumps(state['proposed'],indent=2))
    raise SystemExit(0 if state['proposed']['verified'] else 2)
