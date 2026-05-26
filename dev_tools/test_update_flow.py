#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Update akışı uçtan uca test scripti.
Production dosyalarına dokunmaz — sadece okur ve simüle eder.
"""

import hashlib
import json
import os
import sys
import ssl
import urllib.request
import tempfile
import shutil

REPO        = 'ehlikeyfproduksiyon-cell/ContraCore'
API_URL     = f'https://api.github.com/repos/{REPO}/releases/latest'
RAW_UJ_URL  = f'https://raw.githubusercontent.com/{REPO}/main/update.json'
LOCAL_UJ    = os.path.join(os.path.dirname(__file__), '..', 'update.json')
RELEASE_DIR = os.path.join(os.path.dirname(__file__), '..', 'release', 'ContraCORE')

PASS = '[PASS]'
FAIL = '[FAIL]'
INFO = '[INFO]'

results = []

def check(name, ok, detail=''):
    status = PASS if ok else FAIL
    results.append((status, name, detail))
    print(f'{status} {name}' + (f' — {detail}' if detail else ''))
    return ok

def ssl_ctx():
    return ssl.create_default_context()

def http_get(url, timeout=15):
    req = urllib.request.Request(url, headers={'User-Agent': 'ContraCORE-test/1.0'})
    with urllib.request.urlopen(req, context=ssl_ctx(), timeout=timeout) as r:
        return r.read()

def sha256_file(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            h.update(chunk)
    return h.hexdigest()

print('=' * 60)
print(' ContraCORE Update Akışı — Uçtan Uca Test')
print('=' * 60)

# ── 1. update.json raw URL erişim ────────────────────────────────
print('\n[1] update.json raw URL')
try:
    raw = http_get(RAW_UJ_URL)
    meta = json.loads(raw)
    check('update.json erisilebilir', True, f"version={meta['version']}")
    check('zip_name mevcut', bool(meta.get('zip_name')), meta.get('zip_name'))
    check('zip_sha256 mevcut', len(meta.get('zip_sha256','')) == 64, meta.get('zip_sha256','')[:16]+'...')
except Exception as e:
    check('update.json erisilebilir', False, str(e))
    meta = {}

# ── 2. GitHub API — release ve ZIP asset URL ─────────────────────
print('\n[2] GitHub API release kontrolü')
zip_url = None
try:
    api_data = json.loads(http_get(API_URL))
    tag = api_data.get('tag_name','')
    check('Latest release mevcut', bool(tag), tag)
    zip_name = meta.get('zip_name', 'ContraCORE_update.zip')
    for asset in api_data.get('assets', []):
        if asset.get('name') == zip_name:
            zip_url = asset['browser_download_url']
            size_mb = asset['size'] / 1024 / 1024
            check('ZIP asset bulundu', True, f'{size_mb:.1f} MB')
            break
    if not zip_url:
        check('ZIP asset bulundu', False, f'{zip_name} asset listesinde yok')
except Exception as e:
    check('GitHub API erisilebilir', False, str(e))

# ── 3. Versiyon karşılaştırma mantığı ────────────────────────────
print('\n[3] Versiyon karşılaştırma')
def ver_tuple(v):
    try: return tuple(int(x) for x in v.lstrip('v').split('.'))
    except: return (0,)

def is_newer(remote, local):
    return ver_tuple(remote) > ver_tuple(local)

tests = [
    ('1.0.1', '1.0.0', True),
    ('1.0.0', '1.0.0', False),
    ('1.0.0', '1.0.1', False),
    ('2.0.0', '1.9.9', True),
    ('1.1.0', '1.0.9', True),
]
for remote, local, expected in tests:
    ok = is_newer(remote, local) == expected
    check(f'is_newer({remote}, {local}) == {expected}', ok)

# ── 4. Lokal release klasörü doğrulama ───────────────────────────
print('\n[4] Lokal release klasörü')
check('release/ContraCORE/ mevcut', os.path.isdir(RELEASE_DIR), RELEASE_DIR)
check('ContraCORE.exe mevcut', os.path.isfile(os.path.join(RELEASE_DIR, 'ContraCORE.exe')))
check('ContraCORELauncher.exe mevcut', os.path.isfile(os.path.join(RELEASE_DIR, 'ContraCORELauncher.exe')))
check('update.json mevcut', os.path.isfile(os.path.join(RELEASE_DIR, 'update.json')))

# ── 5. Lokal update.json — SHA256 tutarlılığı ────────────────────
print('\n[5] Lokal update.json + ZIP SHA256')
zip_path = os.path.join(os.path.dirname(LOCAL_UJ), 'release', 'ContraCORE_update.zip')
try:
    with open(LOCAL_UJ, encoding='utf-8') as f:
        local_meta = json.load(f)
    local_sha = local_meta.get('zip_sha256', '')
    remote_sha = meta.get('zip_sha256', '')
    check('Lokal ve remote sha256 eslesiyor', local_sha == remote_sha,
          f'{local_sha[:16]}... == {remote_sha[:16]}...')

    if os.path.isfile(zip_path):
        actual_sha = sha256_file(zip_path)
        check('ZIP sha256 dogrulandi', actual_sha == local_sha,
              f'actual={actual_sha[:16]}...')
    else:
        print(f'{INFO} ZIP lokal yok ({zip_path}) — dogrulama atlanacak')
except Exception as e:
    check('Lokal update.json okundu', False, str(e))

# ── 6. ZIP URL indirme simülasyonu (HEAD only — boyut kontrol) ────
print('\n[6] ZIP URL erisilebilirlik (HEAD)')
if zip_url:
    try:
        req = urllib.request.Request(zip_url, method='HEAD',
                                     headers={'User-Agent': 'ContraCORE-test/1.0'})
        with urllib.request.urlopen(req, context=ssl_ctx(), timeout=15) as r:
            content_len = int(r.headers.get('Content-Length', 0))
            size_mb = content_len / 1024 / 1024
            check('ZIP URL HEAD 200', r.status == 200, f'{size_mb:.1f} MB')
            check('ZIP boyutu makul (>50 MB)', size_mb > 50, f'{size_mb:.1f} MB')
    except Exception as e:
        check('ZIP URL erisilebilir', False, str(e))

# ── 7. Güvenlik — AppData'ya dokunulmadı mı? ─────────────────────
print('\n[7] Güvenlik kontrolleri')
appdata_cc = os.path.join(os.environ.get('APPDATA', ''), 'ContraCore')
pending    = os.path.join(appdata_cc, 'pending_update.json')
check('pending_update.json yok (temiz baslangic)', not os.path.isfile(pending))

lock = os.path.join(tempfile.gettempdir(), 'contracore_update.lock')
check('update.lock yok (baska updater calismiyor)', not os.path.isfile(lock))

# ── Özet ─────────────────────────────────────────────────────────
print('\n' + '=' * 60)
passed = sum(1 for s,_,_ in results if s == PASS)
failed = sum(1 for s,_,_ in results if s == FAIL)
print(f' SONUC: {passed} PASS  /  {failed} FAIL')
print('=' * 60)

if failed:
    print('\nBASARISIZ TESTLER:')
    for s, name, detail in results:
        if s == FAIL:
            print(f'  {name}: {detail}')
    sys.exit(1)
else:
    print('\nTum testler gecti — update akisi production-ready.')
    sys.exit(0)
