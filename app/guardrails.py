"""Conservative lexical baseline; documented multilingual/paraphrase limitations."""
import re
import unicodedata
import html
import base64
import os
from urllib.parse import unquote
from .semantic import scan_text

INJECTION = re.compile(r'ignore\s+(all\s+|any\s+|the\s+)?(previous|prior|system)|system\s*prompt|developer\s*message|<\|im_start\|>|you are now|reveal.*(secret|key)|call\s+(a\s+)?tool|override.*instruction', re.I)
TOXIC = re.compile(r'\b(kill yourself|idiot|moron|fuck|bastard)\b', re.I)
DETERMINATION = re.compile(r'\b(claim (is |has been )?(approved|rejected)|we (approve|reject)|guaranteed (payment|coverage))\b', re.I)

def normalize(text):
    text=unicodedata.normalize('NFKC',html.unescape(unquote(text)))
    text=''.join(c for c in text if unicodedata.category(c)!='Cf')
    for token in re.findall(r'\b[A-Za-z0-9+/]{24,}={0,2}',text):
        try:
            decoded=base64.b64decode(token+'='*((-len(token))%4),validate=True).decode('utf-8')
            if decoded.isprintable():text+=' '+decoded
        except (ValueError,UnicodeError):pass
    return text

def strings(value):
    if isinstance(value,str):yield value
    elif isinstance(value,dict):
        for item in value.values():yield from strings(item)
    elif isinstance(value,(list,tuple)):
        for item in value:yield from strings(item)

def inspect(value):
    text=normalize(' '.join(strings(value)))
    if INJECTION.search(text):
        return 'prompt_injection'
    if TOXIC.search(text):
        return 'toxicity'
    if re.search(r'forget.*instructions|disregard.*rules|act as.*(admin|system)|\[/?INST\]|<\s*/?\s*(system|assistant)',text,re.I):
        return 'prompt_injection'
    try:
        if scan_text(text)['blocked']:return 'model_guardrail'
    except Exception:
        return 'safety_unavailable'
    return None

def output_safe(text):
    text=normalize(text)
    if DETERMINATION.search(text) or INJECTION.search(text) or TOXIC.search(text):return False
    try:
        report=scan_text(text)
        return not any(w['toxicity']>=float(os.getenv('TOXICITY_THRESHOLD','.9')) for w in report.get('windows',[]))
    except Exception:return False
