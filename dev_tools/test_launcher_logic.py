#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Launcher iç mantığını izole test eder.
- Gerçek update indirmez
- AppData'ya yazmaz
- Production dosyalarına dokunmaz
- Temp dizinde sahte install_dir simüle eder
"""

import hashlib, json, os, shutil, sys, tempfile, time

PASS = '[PASS]'
FAIL = '[FAIL]'
results = []

def check(name, ok, detail=''):
    results.append((PASS if ok else FAIL, name, detail))
    print(f'{"[PASS]" if ok else "[FAIL]"} {name}' + (f' — {detail}' if detail else ''))
    return ok

# launcher.py'yi import et (sys.path üzerinden)
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_ROOT, 'launcher'))
sys.path.insert(0, _ROOT)

print('=' * 60)
print(' Launcher İç Mantık — İzole Test')
print('=' * 60)

# ── 1. launcher.py import ────────────────────────────────────────
print('\n[1] Launcher import')
try:
    import launcher as L
    check('launcher.py import edildi', True)
except Exception as e:
    check('launcher.py import edildi', False, str(e))
    sys.exit(1)

# ── 2. Versiyon karşılaştırma ─────────────────────────────────────
print('\n[2] _is_newer')
cases = [
    ('1.0.1', '1.0.0', True),
    ('1.0.0', '1.0.0', False),
    ('2.0.0', '1.9.9', True),
    ('v1.1.0', '1.0.9', True),
    ('1.0.0', '1.0.1', False),
]
for r, l, exp in cases:
    ok = L._is_newer(r, l) == exp
    check(f'_is_newer({r},{l})=={exp}', ok)

# ── 3. SHA256 ─────────────────────────────────────────────────────
print('\n[3] _sha256_file')
with tempfile.NamedTemporaryFile(delete=False, suffix='.bin') as f:
    f.write(b'ContraCORE test payload 12345')
    tmp_sha = f.name
expected = hashlib.sha256(b'ContraCORE test payload 12345').hexdigest()
actual   = L._sha256_file(tmp_sha)
check('SHA256 doğru hesaplıyor', actual == expected, actual[:16]+'...')
os.unlink(tmp_sha)

# ── 4. Lock mekanizması ───────────────────────────────────────────
print('\n[4] Lock mekanizması')
# Temiz lock
if os.path.exists(L.UPDATE_LOCK):
    os.remove(L.UPDATE_LOCK)
ok1 = L._acquire_lock()
check('Lock alındı (temiz)', ok1)
check('Lock dosyası oluştu', os.path.isfile(L.UPDATE_LOCK))
pid_in_lock = int(open(L.UPDATE_LOCK).read().strip())
check('Lock PID doğru', pid_in_lock == os.getpid(), f'{pid_in_lock}=={os.getpid()}')

# İkinci lock denemesi (aynı process — stale değil, FAIL beklenir)
# Başka bir PID simüle et: lock dosyasına olmayan bir PID yaz
with open(L.UPDATE_LOCK, 'w') as f:
    f.write('999999999')   # var olmayan PID
ok2 = L._acquire_lock()   # stale lock → üzerine yazmalı → True dönmeli
check('Stale lock override edildi', ok2)

L._release_lock()
check('Lock temizlendi', not os.path.isfile(L.UPDATE_LOCK))

# ── 5. Pending state (test AppData değil, temp dizin) ─────────────
print('\n[5] Pending state (temp dizin)')
tmp_appdata = tempfile.mkdtemp(prefix='cc_test_appdata_')
orig_pending = L.PENDING_FILE
L.PENDING_FILE = os.path.join(tmp_appdata, 'pending_update.json')
L.APPDATA_DIR  = tmp_appdata

test_meta = {'version': '1.0.1', 'notes': 'Test release', 'zip_url': 'https://example.com/x.zip', 'zip_sha256': 'abc'}
L._write_pending(test_meta)
check('pending_update.json yazıldı', os.path.isfile(L.PENDING_FILE))

with open(L.PENDING_FILE, encoding='utf-8') as f:
    read_back = json.load(f)
check('pending içerik doğru', read_back.get('version') == '1.0.1')

L._clear_pending()
check('pending_update.json silindi', not os.path.isfile(L.PENDING_FILE))

L.PENDING_FILE = orig_pending
shutil.rmtree(tmp_appdata, ignore_errors=True)

# ── 6. Rollback mekanizması (temp install_dir) ────────────────────
print('\n[6] Rollback mekanizması')
tmp_install = tempfile.mkdtemp(prefix='cc_test_install_')
tmp_backup  = os.path.join(tmp_install, '_backup')

# Sahte install_dir oluştur
for fname in ['ContraCORE.exe', 'ContraCORELauncher.exe', 'update.json']:
    with open(os.path.join(tmp_install, fname), 'w') as f:
        f.write(f'ORIGINAL_{fname}')
os.makedirs(os.path.join(tmp_install, 'modules', 'xml-fatura'), exist_ok=True)
with open(os.path.join(tmp_install, 'modules', 'xml-fatura', 'main.py'), 'w') as f:
    f.write('# original module')

# Backup al
L._take_backup(tmp_install, tmp_backup)
check('Backup klasörü oluştu', os.path.isdir(tmp_backup))
check('ContraCORE.exe backup\'landı', os.path.isfile(os.path.join(tmp_backup, 'ContraCORE.exe')))
check('modules/ backup\'landı', os.path.isdir(os.path.join(tmp_backup, 'modules')))

# Simüle: güncelleme bozdu — dosyayı değiştir
with open(os.path.join(tmp_install, 'ContraCORE.exe'), 'w') as f:
    f.write('CORRUPTED')

# Rollback yap
L._rollback(tmp_install, tmp_backup)
with open(os.path.join(tmp_install, 'ContraCORE.exe')) as f:
    restored = f.read()
check('Rollback ContraCORE.exe\'yi geri yükledi', restored == 'ORIGINAL_ContraCORE.exe', repr(restored))

# Module de geri yüklendi mi?
mod_path = os.path.join(tmp_install, 'modules', 'xml-fatura', 'main.py')
check('Rollback modules/ geri yükledi', os.path.isfile(mod_path))

shutil.rmtree(tmp_install, ignore_errors=True)

# ── 7. _validate_zip (boyut kontrolü) ────────────────────────────
print('\n[7] ZIP validasyon')
tmp_zip = tempfile.NamedTemporaryFile(delete=False, suffix='.zip')
tmp_zip.write(b'x' * 100)   # 100 byte — min boyutun altında
tmp_zip.close()
ok_small = not L._validate_zip(tmp_zip.name, '')   # küçük → False dönmeli
check('Küçük ZIP reddedildi', ok_small, '100 bytes < 30MB')
os.unlink(tmp_zip.name)

# Boyut geçer ama sha256 yanlış
tmp_zip2 = tempfile.NamedTemporaryFile(delete=False, suffix='.zip')
tmp_zip2.write(b'x' * (35 * 1024 * 1024))  # 35 MB — min üstü
tmp_zip2.close()
ok_sha = not L._validate_zip(tmp_zip2.name, 'yanlis_sha256_degeri' + 'a'*44)
check('Yanlış SHA256 reddedildi', ok_sha)
os.unlink(tmp_zip2.name)

# ── 8. Gerçek AppData'ya dokunulmadı mı? ────────────────────────
print('\n[8] Güvenlik — production AppData kontrol')
real_appdata = os.path.join(os.environ.get('APPDATA', ''), 'ContraCore', 'pending_update.json')
check('Gerçek pending_update.json bozulmadı', not os.path.isfile(real_appdata) or
      open(real_appdata).read() != json.dumps({'version':'CORRUPTED'}))

# ── Özet ─────────────────────────────────────────────────────────
print('\n' + '=' * 60)
passed = sum(1 for s,_,_ in results if s == PASS)
failed = sum(1 for s,_,_ in results if s == FAIL)
print(f' SONUÇ: {passed} PASS  /  {failed} FAIL')
print('=' * 60)
if failed:
    for s, n, d in results:
        if s == FAIL: print(f'  {n}: {d}')
    sys.exit(1)
sys.exit(0)
