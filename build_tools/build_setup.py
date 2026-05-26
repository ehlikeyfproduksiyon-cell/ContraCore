#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ContraCORE — Setup Build Scripti
Inno Setup Compiler (ISCC.exe) çağırarak kurulum dosyası üretir.

Kullanım:
  python build_tools/build_setup.py
  python build_tools/build_setup.py --iscc "C:\\Program Files (x86)\\Inno Setup 6\\ISCC.exe"

Ön koşul:
  1. release/ContraCORE/ build edilmiş olmalı
     (python build_tools/build_contracore.py)
  2. ContraCORELauncher.exe release/ContraCORE/ içinde olmalı
     (python build_tools/build_launcher.py + build_contracore.py)
  3. Inno Setup 6 kurulu olmalı
     https://jrsoftware.org/isdl.php

Çıktı:
  release/setup/ContraCORE_Setup_vX.Y.Z.exe
"""

import argparse
import os
import subprocess
import sys

_HERE    = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(_HERE)

ISS_FILE    = os.path.join(ROOT_DIR, 'installer', 'ContraCORE.iss')
RELEASE_DIR = os.path.join(ROOT_DIR, 'release', 'ContraCORE')
OUTPUT_DIR  = os.path.join(ROOT_DIR, 'release', 'setup')

# Inno Setup kurulum arama yolları (sırasıyla denenir)
_ISCC_CANDIDATES = [
    r'C:\Program Files (x86)\Inno Setup 6\ISCC.exe',
    r'C:\Program Files\Inno Setup 6\ISCC.exe',
    r'C:\Program Files (x86)\Inno Setup 5\ISCC.exe',
    r'C:\Program Files\Inno Setup 5\ISCC.exe',
]


# ── Yardımcılar ──────────────────────────────────────────────────────────────

def _read_app_version() -> str:
    """core/version.py'dan APP_VERSION okur — import yapmadan."""
    version_file = os.path.join(ROOT_DIR, 'core', 'version.py')
    with open(version_file, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line.startswith('APP_VERSION'):
                return line.split('=', 1)[1].strip().strip("'\"")
    raise RuntimeError('APP_VERSION bulunamadı: core/version.py')


def _find_iscc(override: str = '') -> str:
    """ISCC.exe yolunu bulur. Bulamazsa hata."""
    if override:
        if os.path.isfile(override):
            return override
        raise FileNotFoundError(f'Belirtilen ISCC.exe bulunamadı: {override}')

    # PATH'te var mı?
    import shutil as _sh
    found = _sh.which('ISCC') or _sh.which('ISCC.exe')
    if found:
        return found

    # Sabit kurulum yolları
    for path in _ISCC_CANDIDATES:
        if os.path.isfile(path):
            return path

    raise FileNotFoundError(
        'Inno Setup Compiler (ISCC.exe) bulunamadı.\n'
        'Lütfen Inno Setup 6 kurun: https://jrsoftware.org/isdl.php\n'
        'Veya --iscc parametresi ile tam yolu belirtin.'
    )


def _banner(msg: str):
    print('\n' + '=' * 60)
    print(f'  {msg}')
    print('=' * 60)


def _preflight_check(version: str):
    """Build öncesi ön koşulları doğrular."""
    errors = []

    if not os.path.isdir(RELEASE_DIR):
        errors.append(f'release/ContraCORE/ bulunamadı — önce build_contracore.py çalıştır')

    launcher = os.path.join(RELEASE_DIR, 'ContraCORELauncher.exe')
    if not os.path.isfile(launcher):
        errors.append('ContraCORELauncher.exe yok — önce build_launcher.py çalıştır')

    contracore = os.path.join(RELEASE_DIR, 'ContraCORE.exe')
    if not os.path.isfile(contracore):
        errors.append('ContraCORE.exe yok — önce build_contracore.py çalıştır')

    if not os.path.isfile(ISS_FILE):
        errors.append(f'installer/ContraCORE.iss bulunamadı: {ISS_FILE}')

    if errors:
        print('\n[HATA] Ön koşul kontrolü başarısız:')
        for e in errors:
            print(f'  [X] {e}')
        sys.exit(1)

    print(f'[OK] Ön koşullar doğrulandı (versiyon: {version})')


# ── Ana fonksiyon ─────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description='ContraCORE Setup build scripti')
    parser.add_argument('--iscc', default='', help='ISCC.exe tam yolu (otomatik arama yerine)')
    args = parser.parse_args()

    _banner('ContraCORE Setup Build')

    # 1. Versiyon oku
    version = _read_app_version()
    print(f'APP_VERSION : {version}')
    print(f'ISS dosyası : {ISS_FILE}')
    print(f'Kaynak      : {RELEASE_DIR}')
    print(f'Çıktı       : {OUTPUT_DIR}')

    # 2. Ön koşul kontrolü
    _preflight_check(version)

    # 3. ISCC.exe bul
    try:
        iscc = _find_iscc(args.iscc)
    except FileNotFoundError as e:
        print(f'\n[HATA] {e}')
        sys.exit(1)
    print(f'ISCC.exe    : {iscc}')

    # 4. Çıktı dizini hazırla
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # 5. Inno Setup Compiler çalıştır
    _banner(f'Inno Setup Compiler — v{version}')

    cmd = [
        iscc,
        f'/DMyAppVersion={version}',   # core/version.py → tek kaynak
        ISS_FILE,
    ]
    print(f'Komut: {" ".join(cmd)}\n')

    result = subprocess.run(cmd, cwd=ROOT_DIR)

    if result.returncode != 0:
        print(f'\n[HATA] ISCC.exe çıkış kodu: {result.returncode}')
        sys.exit(result.returncode)

    # 6. Sonuç
    setup_exe = os.path.join(OUTPUT_DIR, f'ContraCORE_Setup_v{version}.exe')
    _banner('SETUP BUILD TAMAMLANDI')

    if os.path.isfile(setup_exe):
        size_mb = os.path.getsize(setup_exe) / (1024 * 1024)
        print(f'Setup       : {setup_exe}')
        print(f'Boyut       : {size_mb:.1f} MB')
    else:
        print(f'[WARN] Beklenen çıktı dosyası bulunamadı: {setup_exe}')
        print('ISCC logunu kontrol edin.')

    print()
    print('Müşteriye gönderilecek tek dosya:')
    print(f'  ContraCORE_Setup_v{version}.exe')
    print()


if __name__ == '__main__':
    main()
