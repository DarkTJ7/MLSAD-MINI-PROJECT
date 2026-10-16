"""CPU ONNX classifiers; models are data, never remotely executed Python code."""
import json
import os
from functools import lru_cache
from pathlib import Path
import numpy as np
from tokenizers import Tokenizer
import onnxruntime as ort

class Classifier:
    def __init__(self,path):
        root=Path(path)
        self.labels=json.loads((root/'config.json').read_text())['id2label']
        self.tokenizer=Tokenizer.from_file(str(root/'tokenizer.json'))
        self.tokenizer.enable_truncation(max_length=512)
        options=ort.SessionOptions();options.intra_op_num_threads=2;options.inter_op_num_threads=1
        self.session=ort.InferenceSession(str(root/'model.onnx'),sess_options=options,providers=['CPUExecutionProvider'])
    def score(self,text,pair=None,multilabel=False):
        encoded=self.tokenizer.encode(text,pair)
        values={'input_ids':encoded.ids,'attention_mask':encoded.attention_mask,'token_type_ids':encoded.type_ids}
        inputs={i.name:np.array([values[i.name]],dtype=np.int64) for i in self.session.get_inputs()}
        logits=self.session.run(None,inputs)[0][0].astype(float)
        scores=1/(1+np.exp(-np.clip(logits,-50,50))) if multilabel else np.exp(logits-logits.max())/np.exp(logits-logits.max()).sum()
        return {self.labels[str(i)].lower():float(v) for i,v in enumerate(scores)}

@lru_cache(maxsize=3)
def classifier(kind):
    return Classifier(os.environ['SAFETY_'+kind.upper()+'_PATH'])

def windows(text,words=160,overlap=30):
    tokens=text.split()
    if not tokens: return ['']
    return [' '.join(tokens[i:i+words]) for i in range(0,len(tokens),words-overlap)]

def screen(text):
    reports=[]
    for chunk in windows(text):
        reports.append(_screen_window(chunk))
    return {'blocked':any(x['injection']>=float(os.getenv('INJECTION_THRESHOLD','.8')) or
                          x['toxicity']>=float(os.getenv('TOXICITY_THRESHOLD','.9')) for x in reports),
            'windows':reports,'method':'onnx-classifiers-v1'}

@lru_cache(maxsize=2048)
def _screen_window(chunk):
    a=classifier('injection').score(chunk);b=classifier('toxicity').score(chunk,multilabel=True)
    return {'injection':max((v for k,v in a.items() if k in ('injection','label_1')),default=0),
            'toxicity':max(b.values(),default=0)}

def entail(premise,hypothesis):
    reports=[classifier('nli').score(chunk,hypothesis) for chunk in windows(premise)]
    best=max(reports,key=lambda r:r.get('entailment',0))
    return {'supported':best.get('entailment',0)>=float(os.getenv('ENTAILMENT_THRESHOLD','.65')) and
                        best.get('contradiction',1)<.2,'scores':best,'method':'nli-deberta-cpu'}

class Encoder:
    def __init__(self,path):
        root=Path(path);self.tokenizer=Tokenizer.from_file(str(root/'tokenizer.json'))
        self.tokenizer.enable_truncation(max_length=256)
        options=ort.SessionOptions();options.intra_op_num_threads=2
        self.session=ort.InferenceSession(str(root/'model.onnx'),sess_options=options,providers=['CPUExecutionProvider'])
    def encode(self,text):
        encoded=self.tokenizer.encode(text)
        values={'input_ids':encoded.ids,'attention_mask':encoded.attention_mask,'token_type_ids':encoded.type_ids}
        inputs={i.name:np.array([values[i.name]],dtype=np.int64) for i in self.session.get_inputs()}
        output=self.session.run(None,inputs)[0]
        vector=output[0].mean(axis=0) if output.ndim==3 else output[0]
        return vector/(np.linalg.norm(vector)+1e-12)

@lru_cache(maxsize=1)
def encoder():return Encoder(os.environ['SAFETY_EMBEDDING_PATH'])

def relevance(query,passages):
    model=encoder();q=model.encode(query)
    scores=[float(np.clip(np.dot(q,model.encode(p)),-1,1)) for p in passages]
    return {'mean_cosine':sum(scores)/len(scores) if scores else None,'scores':scores,'method':'sentence-embedding-cosine'}
