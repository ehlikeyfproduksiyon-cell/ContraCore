#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ContraCore License Manager — Production Build Script
!! BU ARAÇ MÜŞTERİYE GÖNDERİLMEZ — SADECE GELİŞTİRİCİ KULLANIMI !!

Çıktı: release/LicenseManager/ContraCORE License Manager.exe  (standalone, no console)

Kullanım:
  python build_tools/build_license_manager.py
  python build_tools/build_license_manager.py --clean
"""

import argparse
import os
import shutil
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from _build_common import (
    ROOT_DIR, RELEASE_DIR,
    ICON_SETUP,
    banner, check_nuitka, verify_icon,
    copy_data_dir, run_nuitka, move_dist_to_release,
)

# ── Config ─────────────────────────────────────────────────────────────────────
APP_NAME       = 'ContraCORE License Manager'
EXE_NAME       = 'ContraCORE License Manager'
ENTRY_SCRIPT   = os.path.join(ROOT_DIR, 'tools', 'license_manager.py')
RELEASE_SUBDIR = os.path.join(RELEASE_DIR, 'LicenseManager')

# Nuitka dist folder is named after the script file (license_manager.dist)
DIST_NAME  = 'license_manager.dist'
BUILD_NAME = 'license_manager.build'


def _clean():
    for path in [RELEASE_SUBDIR,
                 os.path.join(ROOT_DIR, DIST_NAME),
                 os.path.join(ROOT_DIR, BUILD_NAME)]:
        if os.path.exists(path):
            shutil.rmtree(path)
            print(f'[OK] Temizlendi: {path}')


def _copy_runtime_assets(release_dir: str):
    """Copy assets required by the License Manager at runtime."""
    # Icon/ — used for UI images in the tools
    copy_data_dir(os.path.join(ROOT_DIR, 'Icon'),  release_dir)
    # Logom/ — logo assets displayed in the manager
    copy_data_dir(os.path.join(ROOT_DIR, 'Logom'), release_dir)

    # tools/customers.json — the license database (copy if it exists, else create empty)
    db_src = os.path.join(ROOT_DIR, 'tools', 'customers.json')
    db_dst = os.path.join(release_dir, 'customers.json')
    if os.path.exists(db_src):
        shutil.copy2(db_src, db_dst)
        print('[OK] customers.json kopyalandı.')
    else:
        import json
        with open(db_dst, 'w', encoding='utf-8') as f:
            json.dump({'customers': []}, f, indent=2)
        print('[OK] Boş customers.json oluşturuldu.')

    # tools/logs/ directory
    logs_dst = os.path.join(release_dir, 'logs')
    os.makedirs(logs_dst, exist_ok=True)

    print('[OK] Runtime assets kopyalandı.')


def main():
    parser = argparse.ArgumentParser(
        description='ContraCORE License Manager production build\n'
                    '!! MÜŞTERİYE GÖNDERİLMEZ !!',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument('--clean', action='store_true', help='Build öncesi temizle')
    args = parser.parse_args()

    banner(f'License Manager Build')
    print('!! BU ARAÇ MÜŞTERİYE GÖNDERİLMEZ — SADECE GELİŞTİRİCİ KULLANIMI !!')

    if args.clean:
        print('\n[TEMIZLIK]')
        _clean()

    # ── Pre-flight ────────────────────────────────────────────────────────────
    check_nuitka()
    icon_ok = verify_icon(ICON_SETUP, 'License Manager icon')

    print(f'\nEntry  : {ENTRY_SCRIPT}')
    print(f'Release: {RELEASE_SUBDIR}')

    # ── Nuitka args ───────────────────────────────────────────────────────────
    nuitka_args = [
        '--standalone',
        '--windows-disable-console',

        '--lto=yes',
        '--jobs=4',

        '--enable-plugin=pyside6',

        f'--windows-product-name={APP_NAME}',
        '--windows-company-name=Serkan ŞAHİN',
        '--windows-product-version=1.0.0.0',
        '--windows-file-version=1.0.0.0',
        f'--windows-file-description={APP_NAME}',

        f'--output-filename={EXE_NAME}.exe',
        f'--output-dir={ROOT_DIR}',

        # tools package contains all license manager widgets
        '--include-package=tools',
        '--include-package-data=tools',

        # core is needed for key_service, license validation etc.
        '--include-package=core',
        '--include-package-data=core',
    ]

    if icon_ok:
        nuitka_args.append(f'--windows-icon-from-ico={ICON_SETUP}')

    nuitka_args.append(ENTRY_SCRIPT)

    # ── Build ─────────────────────────────────────────────────────────────────
    print('\n[BUILD BAŞLIYOR]')
    run_nuitka(nuitka_args)

    # ── Move dist to release ──────────────────────────────────────────────────
    move_dist_to_release(DIST_NAME, RELEASE_SUBDIR)

    # ── Copy runtime assets ───────────────────────────────────────────────────
    print('\n[ASSETS KOPYALANİYOR]')
    _copy_runtime_assets(RELEASE_SUBDIR)

    # ── Summary ───────────────────────────────────────────────────────────────
    exe_path = os.path.join(RELEASE_SUBDIR, f'{EXE_NAME}.exe')
    banner('BUILD TAMAMLANDI')
    print(f'Exe    : {exe_path}')
    print(f'Klasör : {RELEASE_SUBDIR}')
    print()
    print('!! Bu klasörü müşteriye GÖNDERME !!')
    print()


if __name__ == '__main__':
    main()
