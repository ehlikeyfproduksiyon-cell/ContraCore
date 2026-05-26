#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ContraCORELauncher Build Script
Çıktı: build_tools/dist/ContraCORELauncher.exe  (onefile, no console)

Kullanım:
  python build_tools/build_launcher.py
"""

import os
import subprocess
import sys

_HERE    = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(_HERE)
LAUNCHER_SCRIPT = os.path.join(ROOT_DIR, 'launcher', 'launcher.py')
DIST_DIR        = os.path.join(_HERE, 'dist')
OUT_EXE         = os.path.join(DIST_DIR, 'ContraCORELauncher.exe')
ICON_PATH       = os.path.join(ROOT_DIR, 'Icon', 'contralogoo.ico')


def main():
    print('=' * 60)
    print(' ContraCORELauncher Build')
    print('=' * 60)

    # Kaynak dosya kontrolü
    if not os.path.isfile(LAUNCHER_SCRIPT):
        print(f'[HATA] Launcher kaynak bulunamadı: {LAUNCHER_SCRIPT}')
        sys.exit(1)

    # PyInstaller kontrolü
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        print('[HATA] PyInstaller yüklü değil: pip install pyinstaller')
        sys.exit(1)

    os.makedirs(DIST_DIR, exist_ok=True)

    cmd = [
        sys.executable, '-m', 'PyInstaller',
        '--onefile',
        '--noconsole',
        '--name', 'ContraCORELauncher',
        '--distpath', DIST_DIR,
        '--workpath', os.path.join(_HERE, 'build_launcher_tmp'),
        '--specpath', os.path.join(_HERE, 'build_launcher_tmp'),
    ]

    if os.path.isfile(ICON_PATH):
        cmd += ['--icon', ICON_PATH]
    else:
        print(f'[WARN] Ikon bulunamadı: {ICON_PATH}')

    cmd.append(LAUNCHER_SCRIPT)

    print(f'Komut: {" ".join(cmd)}\n')
    result = subprocess.run(cmd, cwd=ROOT_DIR)

    if result.returncode != 0:
        print(f'\n[HATA] PyInstaller çıkış kodu: {result.returncode}')
        sys.exit(result.returncode)

    # Kesin doğrulama — exe yoksa hard error
    if not os.path.isfile(OUT_EXE):
        print(f'\n[HATA] Build tamamlandı ama exe üretilmedi: {OUT_EXE}')
        sys.exit(1)

    size_mb = os.path.getsize(OUT_EXE) / (1024 * 1024)
    print(f'\n[OK] ContraCORELauncher.exe — {size_mb:.1f} MB')
    print(f'     Konum: {OUT_EXE}')
    print('\nSonraki adım:')
    print('  python build_tools/build_contracore.py --clean [--zip]')


if __name__ == '__main__':
    main()
