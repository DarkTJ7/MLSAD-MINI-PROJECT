"""Idempotent, content-addressed corpus pipeline and bounded retrieval tools."""
import hashlib
import json
import time
import os
from pathlib import Path
from functools import lru_cache
import numpy as np
import faiss
from pypdf import PdfReader
from sklearn.feature_extraction.text import HashingVectorizer
from langchain_core.embeddings import Embeddings
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from .config import DATA, ROOT

class LocalEmbeddings(Embeddings):
    """Stateless word-hash embedding; no model download or provider charges.

    Lexical baseline, deliberately NOT represented as semantic embeddings.
    """
    def __init__(self):
        self.vectorizer = HashingVectorizer(n_features=1024, alternate_sign=False, norm='l2', ngram_range=(1,2))
    def embed_documents(self, texts):
        return self.vectorizer.transform(texts).toarray().astype('float32').tolist()
    def embed_query(self, text):
        return self.embed_documents([text])[0]

def index_corpus(force=False):
    start = time.monotonic()
    target = DATA / 'index'
    target.mkdir(exist_ok=True)
    cache_file = DATA / 'embedding_cache.json'
    cache = json.loads(cache_file.read_text()) if cache_file.exists() else {}
    documents, sources, rows = [], [], []
    splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=180)
    for path in sorted((ROOT/'corpus').glob('*.pdf')):
        content = path.read_bytes()
        digest = hashlib.sha256(content).hexdigest()
        sources.append({'file':path.name,'sha256':digest})
        for page_number,page in enumerate(PdfReader(path).pages, 1):
            text = ' '.join((page.extract_text() or '').split())
            for n,chunk in enumerate(splitter.split_text(text)):
                cid = f'{path.stem}:p{page_number}:c{n}'
                row = {'clause_id':cid,'document':path.name,'page':page_number,'text':chunk,
                       'sha256':digest}
                rows.append(row)
                documents.append(Document(page_content=chunk,metadata={k:v for k,v in row.items() if k!='text'}))
    if not documents:
        raise ValueError('No text-layer PDF corpus found')
    fingerprint = hashlib.sha256(json.dumps(sources,sort_keys=True).encode()).hexdigest()
    meta_path = target/'metadata.json'
    if not force and meta_path.exists() and json.loads(meta_path.read_text())['fingerprint']==fingerprint:
        return json.loads(meta_path.read_text())
    embedder = LocalEmbeddings()
    vectors = []
    misses = 0
    for doc in documents:
        key = hashlib.sha256(doc.page_content.encode()).hexdigest()
        if force or key not in cache:
            cache[key] = embedder.embed_query(doc.page_content)
            misses += 1
        vectors.append(cache[key])
    store = FAISS.from_embeddings(zip([d.page_content for d in documents],vectors),embedder,
                                  metadatas=[d.metadata for d in documents])
    store.save_local(str(target))
    (target/'clauses.json').write_text(json.dumps(rows,indent=2),encoding='utf-8')
    cache_file.write_text(json.dumps(cache),encoding='utf-8')
    elapsed=time.monotonic()-start
    metadata={'fingerprint':fingerprint,'sources':sources,'built_at':time.time(),'chunks':len(rows),
              'seconds':elapsed,'chunks_per_second':len(rows)/elapsed,'new_embeddings':misses,
              'embedding':'HashingVectorizer-1024-word-1,2','chunk_size':1000,'overlap':180}
    meta_path.write_text(json.dumps(metadata,indent=2),encoding='utf-8')
    return metadata

class Corpus:
    def __init__(self):
        # No pickle loading: construct FAISS index and docstore from trusted JSON vectors.
        target=DATA/'index'
        self.rows=json.loads((target/'clauses.json').read_text(encoding='utf-8'))
        self.cache={}
        emb=LocalEmbeddings()
        self.store=FAISS.from_texts([r['text'] for r in self.rows],emb,
                                   metadatas=[{k:v for k,v in r.items() if k!='text'} for r in self.rows])
    def search(self, query, k=6):
        key=(query,k)
        if os.getenv('RETRIEVAL_CACHE','true').lower()=='true' and key in self.cache:
            return self.cache[key]
        result=[dict(d.metadata,text=d.page_content,score=float(score))
                for d,score in self.store.similarity_search_with_score(query,k=k)
                if float(score)<1.95]
        if len(self.cache)>=128:
            self.cache.clear()
        self.cache[key]=result
        return result
    def lookup(self, clause_id):
        return next((r for r in self.rows if r['clause_id']==clause_id),None)

@lru_cache(maxsize=1)
def get_corpus():
    """One immutable corpus and bounded query working set per worker process."""
    return Corpus()

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument('--reembed',action='store_true')
    args=parser.parse_args()
    print(json.dumps(index_corpus(args.reembed),indent=2))
