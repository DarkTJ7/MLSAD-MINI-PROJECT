"""Download pinned, checksum-verified model data supplied by runtime manifest."""
import hashlib,json,os,urllib.request
from pathlib import Path

def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream,'sha256').hexdigest()

def install(manifest_path):
    manifest=json.loads(Path(manifest_path).read_text())
    root=Path(os.environ['MODEL_ASSET_DIR']);root.mkdir(parents=True,exist_ok=True)
    for row in manifest['files']:
        dest=root/row['path']
        if not dest.resolve().is_relative_to(root.resolve()):raise ValueError('Unsafe asset path')
        dest.parent.mkdir(parents=True,exist_ok=True)
        if not dest.exists() or digest(dest)!=row['sha256']:
            tmp=dest.with_suffix('.download')
            urllib.request.urlretrieve(row['url'],tmp)
            if digest(tmp)!=row['sha256']:raise ValueError('Model checksum mismatch')
            tmp.replace(dest)
    print(json.dumps({'assets_verified':len(manifest['files'])}))

if __name__=='__main__':install(os.environ['MODEL_MANIFEST_PATH'])
