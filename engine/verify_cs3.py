#!/usr/bin/env python3
"""Verify built CS3 zip structure and emit SHA-256/size metadata for each archive."""
import argparse, hashlib, json, zipfile
from pathlib import Path

def main():
    p=argparse.ArgumentParser(); p.add_argument('--root',default='.'); p.add_argument('--out',default='build/verification.json'); a=p.parse_args()
    root=Path(a.root); files=[f for f in root.rglob('*.cs3') if '.git' not in f.parts and 'build/artifacts' not in str(f)]
    result={'verified':True,'count':0,'archives':[],'errors':[]}
    for f in files:
        raw=f.read_bytes(); item={'path':str(f),'size':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),'manifest_found':False}
        try:
            with zipfile.ZipFile(f) as z:
                names=z.namelist(); manifest=next((n for n in names if n.endswith('manifest.json')),None)
                if not manifest: raise ValueError('manifest.json bulunamadı')
                data=json.loads(z.read(manifest).decode('utf-8')); item['manifest_found']=True; item['manifest_path']=manifest
                item['manifest_name']=data.get('name'); item['manifest_version']=data.get('version')
                if not data.get('name'): raise ValueError('manifest içinde name yok')
        except Exception as e:
            result['verified']=False; item['error']=str(e); result['errors'].append({'path':str(f),'error':str(e)})
        result['archives'].append(item)
    result['count']=len(files)
    if not files:
        result['verified']=False; result['errors'].append({'error':'Hiç .cs3 dosyası üretilmedi.'})
    out=Path(a.out); out.parent.mkdir(parents=True,exist_ok=True); out.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2))
    if not result['verified']: raise SystemExit(1)
if __name__=='__main__': main()
