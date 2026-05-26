#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ContraCORELauncher — Bootstrap & Auto-Updater

Akış:
  1. Güncelleme kontrolü (GitHub API + update.json)
  2. Varsa Tkinter dialog: "Şimdi Güncelle" / "Sonra"
     - Şimdi → ZIP indir → SHA256 doğrula → yedek al → güvenli uygula → ContraCORE aç
     - Sonra  → pending_update.json yaz → ContraCORE aç
  3. Güncelleme yoksa → doğrudan ContraCORE aç

--do-update flag ile çağrıldığında: ContraCORE'un kapanmasını bekle,
pending_update.json'dan ZIP bilgisini al, güncelle, ContraCORE'u tekrar aç.

Güvenlik notları:
- SSL verify=True, kapatılmaz
- SHA256 + minimum boyut kontrolü
- GitHub API timeout sonrası sessizce bypass → ContraCORE açılır
- ContraCORELauncher.exe kendini overwrite etmez (çalışırken kilitli)
- Tüm hatalar %TEMP%/contracore_launcher_log.txt'e yazılır
"""

import argparse
import ctypes
import hashlib
import json
import os
import shutil
import ssl
import subprocess
import sys
import tempfile
import time
import urllib.request

# ── Sabitler ─────────────────────────────────────────────────────────────────

GITHUB_REPO     = 'ehlikeyfproduksiyon-cell/ContraCore'
GITHUB_API_URL  = f'https://api.github.com/repos/{GITHUB_REPO}/releases/latest'
UPDATE_JSON_URL = f'https://raw.githubusercontent.com/{GITHUB_REPO}/main/update.json'

APPDATA_DIR  = os.path.join(os.environ.get('APPDATA', ''), 'ContraCore')
PENDING_FILE = os.path.join(APPDATA_DIR, 'pending_update.json')
UPDATE_LOCK  = os.path.join(tempfile.gettempdir(), 'contracore_update.lock')
LOG_FILE     = os.path.join(tempfile.gettempdir(), 'contracore_launcher_log.txt')

CONTRACORE_EXE = 'ContraCORE.exe'
LAUNCHER_EXE   = 'ContraCORELauncher.exe'
LOCAL_VER_FILE = 'update.json'

TIMEOUT     = 10    # HTTP istek zaman aşımı (saniye)
MIN_ZIP_MB  = 30    # Bozuk ZIP koruması (minimum boyut)


# ── Loglama ───────────────────────────────────────────────────────────────────

def _log(msg: str):
    """Tüm loglar %TEMP%/contracore_launcher_log.txt'e gider."""
    try:
        ts = time.strftime('%Y-%m-%d %H:%M:%S')
        line = f'[{ts}] {msg}\n'
        with open(LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(line)
    except Exception:
        pass


# ── SSL + HTTP ────────────────────────────────────────────────────────────────

def _ssl_ctx() -> ssl.SSLContext:
    return ssl.create_default_context()   # verify=True, kapatılmaz


def _http_get(url: str, timeout: int = TIMEOUT) -> bytes:
    req = urllib.request.Request(url, headers={'User-Agent': 'ContraCORELauncher/1.0'})
    with urllib.request.urlopen(req, context=_ssl_ctx(), timeout=timeout) as r:
        return r.read()


# ── Versiyon karşılaştırma ────────────────────────────────────────────────────

def _ver_tuple(v: str) -> tuple:
    try:
        return tuple(int(x) for x in v.lstrip('v').split('.'))
    except Exception:
        return (0,)


def _is_newer(remote: str, local: str) -> bool:
    return _ver_tuple(remote) > _ver_tuple(local)


# ── SHA256 ────────────────────────────────────────────────────────────────────

def _sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            h.update(chunk)
    return h.hexdigest()


# ── Dizin tespiti ─────────────────────────────────────────────────────────────

def _install_dir() -> str:
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


# ── PID kontrolü (Windows-safe, os.kill kullanılmaz) ─────────────────────────

def _pid_exists(pid: int) -> bool:
    """Tasklist ile PID'in hâlâ çalışıp çalışmadığını kontrol eder."""
    try:
        out = subprocess.check_output(
            ['tasklist', '/FI', f'PID eq {pid}', '/NH'],
            creationflags=subprocess.CREATE_NO_WINDOW,
            text=True, timeout=5,
        )
        return str(pid) in out
    except Exception:
        return False


# ── Update Lock (PID tabanlı) ─────────────────────────────────────────────────

def _acquire_lock() -> bool:
    if os.path.exists(UPDATE_LOCK):
        try:
            pid = int(open(UPDATE_LOCK).read().strip())
            if _pid_exists(pid):
                _log(f'Lock var ve PID {pid} çalışıyor — başka updater aktif.')
                return False
        except Exception:
            pass   # stale lock — devam et
    try:
        with open(UPDATE_LOCK, 'w') as f:
            f.write(str(os.getpid()))
        return True
    except Exception:
        return True   # yazılamazsa yine devam


def _release_lock():
    try:
        os.remove(UPDATE_LOCK)
    except Exception:
        pass


# ── Lokal versiyon ────────────────────────────────────────────────────────────

def _local_version(install_dir: str) -> str:
    try:
        with open(os.path.join(install_dir, LOCAL_VER_FILE), encoding='utf-8') as f:
            return json.load(f).get('version', '0.0.0')
    except Exception:
        return '0.0.0'


# ── Remote meta (GitHub API + update.json) ────────────────────────────────────

def _fetch_remote_meta() -> 'dict | None':
    """
    GitHub API'den ZIP URL'yi, raw branch'ten update.json meta'yı getirir.
    Herhangi bir hata (rate limit, timeout, DNS fail) → sessizce None döner.
    """
    try:
        # 1. update.json'dan meta oku
        raw  = _http_get(UPDATE_JSON_URL)
        meta = json.loads(raw)
    except Exception as e:
        _log(f'update.json indirilemedi: {e}')
        return None

    try:
        # 2. GitHub API'den ZIP asset URL'sini bul
        api_data = json.loads(_http_get(GITHUB_API_URL))
        zip_name = meta.get('zip_name', '')
        zip_url  = None
        for asset in api_data.get('assets', []):
            if asset.get('name') == zip_name:
                zip_url = asset.get('browser_download_url')
                break
        if not zip_url:
            _log(f'ZIP asset bulunamadı GitHub API\'de: {zip_name}')
            return None
        meta['zip_url'] = zip_url
    except Exception as e:
        _log(f'GitHub API başarısız: {e}')
        return None

    return meta


def _check_for_update(install_dir: str) -> 'dict | None':
    local  = _local_version(install_dir)
    meta   = _fetch_remote_meta()
    if meta is None:
        return None
    remote = meta.get('version', '0.0.0')
    if _is_newer(remote, local):
        _log(f'Güncelleme mevcut: {local} → {remote}')
        return meta
    return None


# ── Dialog (Tkinter) ──────────────────────────────────────────────────────────

def _show_update_dialog(meta: dict) -> str:
    """'update' veya 'later' döner."""
    try:
        import tkinter as tk

        result = ['later']
        root   = tk.Tk()
        root.title('ContraCORE — Güncelleme Mevcut')
        root.resizable(False, False)
        root.configure(bg='#0B1F3A')

        w, h = 420, 210
        sw = root.winfo_screenwidth()
        sh = root.winfo_screenheight()
        root.geometry(f'{w}x{h}+{(sw-w)//2}+{(sh-h)//2}')

        tk.Label(root, text='Yeni Güncelleme',
                 font=('Segoe UI', 14, 'bold'),
                 fg='#C9A46A', bg='#0B1F3A').pack(pady=(20, 4))

        version = meta.get('version', '?')
        notes   = meta.get('notes', '') or ''
        tk.Label(root, text=f'Sürüm {version} hazır.',
                 font=('Segoe UI', 10), fg='#FFFFFF', bg='#0B1F3A').pack()

        if notes:
            tk.Label(root, text=notes,
                     font=('Segoe UI', 9), fg='#A0AEC0', bg='#0B1F3A',
                     wraplength=380).pack(pady=(4, 0))

        btn_frame = tk.Frame(root, bg='#0B1F3A')
        btn_frame.pack(pady=20)

        def _update():
            result[0] = 'update'
            root.destroy()

        def _later():
            result[0] = 'later'
            root.destroy()

        tk.Button(btn_frame, text='Şimdi Güncelle',
                  font=('Segoe UI', 10, 'bold'),
                  bg='#ffcc00', fg='#1a1a2e', relief='flat',
                  padx=16, pady=6, cursor='hand2',
                  command=_update).pack(side='left', padx=8)

        tk.Button(btn_frame, text='Sonra',
                  font=('Segoe UI', 10),
                  bg='#1E3660', fg='#FFFFFF', relief='flat',
                  padx=16, pady=6, cursor='hand2',
                  command=_later).pack(side='left', padx=8)

        root.protocol('WM_DELETE_WINDOW', _later)
        root.mainloop()
        return result[0]

    except Exception as e:
        _log(f'Dialog hatası: {e}')
        return 'later'


# ── İndirme & Doğrulama ───────────────────────────────────────────────────────

def _download_zip(url: str, dest: str) -> bool:
    try:
        _log(f'İndiriliyor: {url}')
        req = urllib.request.Request(url, headers={'User-Agent': 'ContraCORELauncher/1.0'})
        with urllib.request.urlopen(req, context=_ssl_ctx(), timeout=180) as r, \
             open(dest, 'wb') as f:
            shutil.copyfileobj(r, f)
        _log(f'İndirme tamamlandı: {os.path.getsize(dest) / 1024 / 1024:.1f} MB')
        return True
    except Exception as e:
        _log(f'İndirme hatası: {e}')
        return False


def _validate_zip(path: str, expected_sha256: str) -> bool:
    try:
        size_mb = os.path.getsize(path) / (1024 * 1024)
        if size_mb < MIN_ZIP_MB:
            _log(f'ZIP çok küçük: {size_mb:.1f} MB < {MIN_ZIP_MB} MB')
            return False
        if expected_sha256:
            actual = _sha256_file(path)
            if actual.lower() != expected_sha256.lower():
                _log(f'SHA256 uyuşmazlık:\n  beklenen: {expected_sha256}\n  gerçek:   {actual}')
                return False
        return True
    except Exception as e:
        _log(f'ZIP doğrulama hatası: {e}')
        return False


# ── Yedekleme ─────────────────────────────────────────────────────────────────

def _take_backup(install_dir: str, backup_dir: str):
    """Güncelleme öncesi kritik dosyaları yedekler."""
    os.makedirs(backup_dir, exist_ok=True)
    items = [CONTRACORE_EXE, LAUNCHER_EXE, LOCAL_VER_FILE,
             'modules', 'Icon', 'Logom']
    for item in items:
        src = os.path.join(install_dir, item)
        dst = os.path.join(backup_dir, item)
        if os.path.isdir(src):
            if os.path.exists(dst):
                shutil.rmtree(dst)
            shutil.copytree(src, dst)
        elif os.path.isfile(src):
            shutil.copy2(src, dst)
    _log('Yedek alındı.')


# ── Güvenli Uygulama (_temp_apply staging) ───────────────────────────────────

def _apply_update(extracted_dir: str, install_dir: str):
    """
    Yeni dosyaları güvenli şekilde uygular.

    Akış:
    1. Tüm yeni içerik install_dir/_temp_apply/ dizinine kopyalanır (staging)
    2. Staging başarılıysa hedef klasörler replace edilir
    3. ContraCORELauncher.exe overwrite edilmez (çalışırken kilitli)

    Bu sayede kopyalama aşamasında exception olsa mevcut kurulum bozulmaz.
    Rollback yedekten yapılır.
    """
    temp_apply = os.path.join(install_dir, '_temp_apply')
    if os.path.exists(temp_apply):
        shutil.rmtree(temp_apply)
    os.makedirs(temp_apply)

    # ── 1. Staging: extracted → _temp_apply ──────────────────────────────────
    for folder in ('modules', 'Icon', 'Logom'):
        src = os.path.join(extracted_dir, folder)
        if os.path.isdir(src):
            shutil.copytree(src, os.path.join(temp_apply, folder))

    for entry in os.scandir(extracted_dir):
        if entry.is_file():
            if entry.name.lower() == LAUNCHER_EXE.lower():
                # Çalışırken overwrite edilemez — skip
                _log(f'{LAUNCHER_EXE} güncelleme sırasında skip edildi (çalışıyor).')
                continue
            shutil.copy2(entry.path, os.path.join(temp_apply, entry.name))

    _log('Staging tamamlandı.')

    # ── 2. Replace: _temp_apply → install_dir ────────────────────────────────
    for folder in ('modules', 'Icon', 'Logom'):
        staged = os.path.join(temp_apply, folder)
        target = os.path.join(install_dir, folder)
        if os.path.isdir(staged):
            if os.path.exists(target):
                shutil.rmtree(target)
            shutil.move(staged, target)

    for entry in os.scandir(temp_apply):
        if entry.is_file():
            shutil.move(entry.path, os.path.join(install_dir, entry.name))

    # ── 3. Temizlik ───────────────────────────────────────────────────────────
    try:
        shutil.rmtree(temp_apply, ignore_errors=True)
    except Exception:
        pass

    _log('Replace tamamlandı.')


# ── Rollback ──────────────────────────────────────────────────────────────────

def _rollback(install_dir: str, backup_dir: str):
    try:
        _log('Rollback başlıyor...')
        if not os.path.isdir(backup_dir):
            _log('Yedek yok, rollback yapılamadı.')
            return
        # Yarım apply varsa temizle
        temp_apply = os.path.join(install_dir, '_temp_apply')
        if os.path.exists(temp_apply):
            shutil.rmtree(temp_apply, ignore_errors=True)
        for entry in os.scandir(backup_dir):
            dst = os.path.join(install_dir, entry.name)
            if entry.is_dir():
                if os.path.exists(dst):
                    shutil.rmtree(dst)
                shutil.copytree(entry.path, dst)
            else:
                shutil.copy2(entry.path, dst)
        _log('Rollback tamamlandı.')
    except Exception as e:
        _log(f'Rollback hatası: {e}')


# ── Hata dialog ───────────────────────────────────────────────────────────────

def _show_error(msg: str):
    try:
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror('ContraCORE Güncelleme Hatası', msg)
        root.destroy()
    except Exception:
        pass


# ── Pending state ─────────────────────────────────────────────────────────────

def _write_pending(meta: dict):
    try:
        os.makedirs(APPDATA_DIR, exist_ok=True)
        with open(PENDING_FILE, 'w', encoding='utf-8') as f:
            json.dump(meta, f, ensure_ascii=False)
    except Exception as e:
        _log(f'pending_update.json yazılamadı: {e}')


def _clear_pending():
    try:
        os.remove(PENDING_FILE)
    except Exception:
        pass


# ── Ana güncelleme işlemi ─────────────────────────────────────────────────────

def _run_update(install_dir: str, meta: 'dict | None' = None) -> bool:
    """True = başarılı, False = başarısız (rollback yapıldı veya başlanamadı)."""
    if not _acquire_lock():
        return False

    tmp_dir    = tempfile.mkdtemp(prefix='cc_update_')
    backup_dir = os.path.join(install_dir, '_backup')
    success    = False

    try:
        # Meta kaynağı
        if meta is None:
            try:
                with open(PENDING_FILE, encoding='utf-8') as f:
                    meta = json.load(f)
            except Exception as e:
                _log(f'pending_update.json okunamadı: {e}')
                return False

        zip_url  = meta.get('zip_url', '')
        sha256   = meta.get('zip_sha256', '')
        zip_path = os.path.join(tmp_dir, 'update.zip')

        if not zip_url:
            _log('zip_url boş — güncelleme iptal.')
            _show_error('Güncelleme URL\'si eksik.\nLütfen tekrar deneyin.')
            return False

        # 1. İndir
        if not _download_zip(zip_url, zip_path):
            _show_error('Güncelleme dosyası indirilemedi.\nİnternet bağlantınızı kontrol edin.')
            return False

        # 2. Doğrula
        if not _validate_zip(zip_path, sha256):
            _show_error('Güncelleme dosyası bozuk veya değiştirilmiş.\nGüncelleme iptal edildi.')
            return False

        # 3. Extract
        extracted_dir = os.path.join(tmp_dir, 'extracted')
        os.makedirs(extracted_dir)
        shutil.unpack_archive(zip_path, extracted_dir, 'zip')

        # Sağlık kontrolü
        if not os.path.isfile(os.path.join(extracted_dir, CONTRACORE_EXE)):
            _show_error('Güncelleme paketi geçersiz: ContraCORE.exe bulunamadı.')
            return False

        # 4. Yedek al
        _take_backup(install_dir, backup_dir)

        # 5. Güvenli uygula (_temp_apply staging)
        _log('Güncelleme uygulanıyor...')
        _apply_update(extracted_dir, install_dir)

        # 6. Lokal update.json güncelle
        try:
            local_ver_path = os.path.join(install_dir, LOCAL_VER_FILE)
            with open(local_ver_path, encoding='utf-8') as f:
                local_data = json.load(f)
            local_data['version'] = meta.get('version', local_data.get('version'))
            with open(local_ver_path, 'w', encoding='utf-8') as f:
                json.dump(local_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            _log(f'update.json lokal güncelleme hatası (kritik değil): {e}')

        _clear_pending()

        # 7. Yedek temizle
        try:
            shutil.rmtree(backup_dir)
        except Exception:
            pass

        _log(f"Güncelleme başarılı: {meta.get('version')}")
        success = True

    except Exception as e:
        _log(f'Güncelleme hatası: {e}')
        _rollback(install_dir, backup_dir)
        _show_error(f'Güncelleme sırasında hata oluştu:\n{e}\n\nProgram önceki sürüme geri döndürüldü.')

    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        _release_lock()

    return success


# ── ContraCORE durumu ─────────────────────────────────────────────────────────

def _is_contracore_running() -> bool:
    try:
        out = subprocess.check_output(
            ['tasklist', '/FI', f'IMAGENAME eq {CONTRACORE_EXE}', '/NH'],
            creationflags=subprocess.CREATE_NO_WINDOW,
            text=True, timeout=5,
        )
        return CONTRACORE_EXE.lower() in out.lower()
    except Exception:
        return False


def _wait_for_contracore_close(timeout_s: int = 30):
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if not _is_contracore_running():
            return
        time.sleep(0.5)
    _log('ContraCORE kapanmadı, zaman aşımı.')


def _launch_contracore(install_dir: str):
    exe = os.path.join(install_dir, CONTRACORE_EXE)
    if not os.path.isfile(exe):
        _show_error(f'{CONTRACORE_EXE} bulunamadı:\n{exe}')
        return
    subprocess.Popen([exe], cwd=install_dir)
    _log(f'{CONTRACORE_EXE} başlatıldı.')


# ── Ana akış ─────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('--do-update', action='store_true')
    args, _ = parser.parse_known_args()

    install_dir = _install_dir()
    _log(f'Launcher başladı — install_dir={install_dir}, do_update={args.do_update}')

    if args.do_update:
        _wait_for_contracore_close()
        _run_update(install_dir)
        _launch_contracore(install_dir)
        return

    # Zaten açıksa geç
    if _is_contracore_running():
        _log('ContraCORE zaten çalışıyor.')
        return

    # Güncelleme kontrolü — hata olursa sessizce geç
    meta = None
    try:
        meta = _check_for_update(install_dir)
    except Exception as e:
        _log(f'Güncelleme kontrolü exception: {e}')

    if meta is None:
        _launch_contracore(install_dir)
        return

    choice = _show_update_dialog(meta)

    if choice == 'update':
        _run_update(install_dir, meta)
        # Başarılı veya başarısız, her durumda ContraCORE aç
        _launch_contracore(install_dir)
    else:
        _write_pending(meta)
        _launch_contracore(install_dir)


if __name__ == '__main__':
    main()
