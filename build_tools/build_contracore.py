#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ContraCore — Production Build Script
Çıktı: release/ContraCORE/ContraCORE.exe  (standalone, no console)

Kullanım:
  python build_tools/build_contracore.py
  python build_tools/build_contracore.py --clean   # önce release/ContraCORE/ temizle
"""

import argparse
import os
import shutil
import sys

# Build tools dizinini path'e ekle
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from _build_common import (
    ROOT_DIR, RELEASE_DIR,
    ICON_CONTRACORE,
    banner, check_nuitka, verify_icon,
    copy_icon_to_build, ensure_release_dir,
    copy_data_dir, run_nuitka, move_dist_to_release,
)

# ── Config ─────────────────────────────────────────────────────────────────────
APP_NAME     = 'ContraCORE'
EXE_NAME     = 'ContraCORE'
ENTRY_SCRIPT = os.path.join(ROOT_DIR, 'main.py')
RELEASE_SUBDIR = os.path.join(RELEASE_DIR, APP_NAME)

# Nuitka outputs <script_basename>.dist next to the script
DIST_NAME    = 'main.dist'      # Nuitka default for main.py
BUILD_NAME   = 'main.build'


def _clean():
    for path in [RELEASE_SUBDIR,
                 os.path.join(ROOT_DIR, DIST_NAME),
                 os.path.join(ROOT_DIR, BUILD_NAME)]:
        if os.path.exists(path):
            shutil.rmtree(path)
            print(f'[OK] Temizlendi: {path}')


def _copy_runtime_assets(release_dir: str):
    """Copy assets that the exe needs at runtime, relative to release_dir.

    Yeni mimaride Icon/, Logom/ ve modules/ artik exe icine gomulu gelir.
    Sadece Launcher ve update.json kopyalanir.
    """

    # ContraCORELauncher.exe — build_tools/dist/ altında kesinlikle olmalı
    launcher_src = os.path.join(_HERE, 'dist', 'ContraCORELauncher.exe')
    if not os.path.isfile(launcher_src):
        raise RuntimeError(
            f'ContraCORELauncher.exe bulunamadı: {launcher_src}\n'
            f'Önce: python build_tools/build_launcher.py'
        )
    shutil.copy2(launcher_src, release_dir)
    size_mb = os.path.getsize(launcher_src) / (1024 * 1024)
    print(f'[OK] ContraCORELauncher.exe kopyalandı ({size_mb:.1f} MB).')

    # update.json — lokal versiyon bilgisi (--zip ile sonradan üretilir, şimdi yoksa sorun değil)
    update_json_src = os.path.join(ROOT_DIR, 'update.json')
    if os.path.isfile(update_json_src):
        shutil.copy2(update_json_src, release_dir)
        print('[OK] update.json kopyalandı.')
    else:
        print('[INFO] update.json proje kökünde yok — --zip ile otomatik üretilecek.')

    print('[OK] Runtime assets kopyalandı.')


def _copy_module_assets(src: str, dst: str):
    """
    Copy a module directory for release.
    - .py files are compiled to .pyc (no source in release)
    - keygen.py and dev-only files are never included
    """
    import py_compile as _pyc

    SKIP_DIRS     = {'__pycache__', '.claude', 'build', 'dist', 'CALISAN', 'Referans'}
    SKIP_EXTS     = {'.pyc', '.pyo', '.spec', '.bat', '.md', '.psd', '.disabled'}
    # Files that must NEVER reach a customer machine
    SKIP_NAMES    = {'keygen.py', 'recent_files.json'}
    # Dev output / sample input files — skip anything whose name starts with these
    SKIP_PREFIXES = ('test_', 'muavin_', 'ikdvl_', 'Indirilecek_', 'internetvd_')

    os.makedirs(dst, exist_ok=True)
    for entry in os.scandir(src):
        name = entry.name
        if entry.is_dir(follow_symlinks=False):
            if name in SKIP_DIRS:
                continue
            _copy_module_assets(entry.path, os.path.join(dst, name))
        else:
            ext = os.path.splitext(name)[1].lower()
            if ext in SKIP_EXTS:
                continue
            if name in SKIP_NAMES:
                print(f'[GUVENLIK] Atlandi (keygen/dev): {entry.path}')
                continue
            if any(name.startswith(p) for p in SKIP_PREFIXES):
                print(f'[GUVENLIK] Atlandi (dev dosyasi): {name}')
                continue
            if ext == '.py':
                # Compile source to .pyc — no raw source in release
                pyc_name = os.path.splitext(name)[0] + '.pyc'
                pyc_dst  = os.path.join(dst, pyc_name)
                try:
                    _pyc.compile(entry.path, cfile=pyc_dst, doraise=True)
                    print(f'[COMPILE] {name} --> {pyc_name}')
                except _pyc.PyCompileError as exc:
                    print(f'[WARN] Compile hatasi ({name}): {exc} -- kaynak kopyalaniyor')
                    shutil.copy2(entry.path, os.path.join(dst, name))
            else:
                shutil.copy2(entry.path, os.path.join(dst, name))


def _verify_release(release_dir: str, check_update_json: bool = False):
    """
    Build sonrası release klasörünü doğrular.
    Eksik kritik dosya varsa RuntimeError fırlatır — build durur.
    """
    required = [
        'ContraCORE.exe',
        'ContraCORELauncher.exe',
    ]
    if check_update_json:
        required.append('update.json')

    missing = [r for r in required if not os.path.exists(os.path.join(release_dir, r))]

    if missing:
        lines = '\n'.join(f'  - {m}' for m in missing)
        raise RuntimeError(
            f'Release klasörü eksik dosyalar içeriyor:\n{lines}\n'
            f'Kaynak: {release_dir}'
        )

    print('[OK] Release doğrulandı:')
    for r in required:
        size = os.path.getsize(os.path.join(release_dir, r))
        label = r if not r.endswith('.exe') else r
        print(f'     {label}  ({size // 1024} KB)' if size < 1024*1024
              else f'     {label}  ({size/1024/1024:.1f} MB)')


def _create_update_zip(release_dir: str) -> str:
    """
    ContraCORE_update.zip oluşturur (sabit isim — updater için).
    Versiyonlu ZIP yerine her zaman aynı isim kullanılır.
    Döner: zip dosyasının tam yolu
    """
    import zipfile as _zf

    zip_path = os.path.join(os.path.dirname(release_dir), 'ContraCORE_update.zip')
    print(f'\n[ZIP] Oluşturuluyor: {zip_path}')

    SKIP_DIRS  = {'__pycache__', '_backup', '_temp_apply', '.claude'}
    SKIP_EXTS  = {'.pyc', '.pyo', '.log', '.tmp'}

    file_count = 0
    with _zf.ZipFile(zip_path, 'w', _zf.ZIP_DEFLATED, compresslevel=6) as zf:
        for root, dirs, files in os.walk(release_dir):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
            for fname in files:
                if os.path.splitext(fname)[1].lower() in SKIP_EXTS:
                    continue
                abs_path = os.path.join(root, fname)
                rel_path = os.path.relpath(abs_path, release_dir)
                zf.write(abs_path, rel_path.replace('\\', '/'))
                file_count += 1

    size_mb = os.path.getsize(zip_path) / (1024 * 1024)
    print(f'[OK] ZIP: {os.path.basename(zip_path)}  ({size_mb:.1f} MB, {file_count} dosya)')
    return zip_path


def main():
    parser = argparse.ArgumentParser(description='ContraCORE production build')
    parser.add_argument('--clean',   action='store_true', help='Build öncesi temizle')
    parser.add_argument('--zip',     action='store_true', help='ZIP + update.json üret (otomatik SHA256)')
    args = parser.parse_args()

    banner(f'ContraCORE Build — {APP_NAME}')

    if args.clean:
        print('\n[TEMIZLIK]')
        _clean()

    # ── Pre-flight ────────────────────────────────────────────────────────────
    check_nuitka()
    icon_ok = verify_icon(ICON_CONTRACORE, 'ContraCORE icon')

    print(f'\nEntry  : {ENTRY_SCRIPT}')
    print(f'Release: {RELEASE_SUBDIR}')

    # ── Asset embedding (Icon + Logom → core/_icons.py) ─────────────────────
    print('\n[ASSET EMBED]')
    import importlib.util as _ilu
    _ga_spec = _ilu.spec_from_file_location('gen_assets', os.path.join(_HERE, 'gen_assets.py'))
    _ga = _ilu.module_from_spec(_ga_spec)
    _ga_spec.loader.exec_module(_ga)
    _ga.generate()

    # ── Nuitka args ───────────────────────────────────────────────────────────
    nuitka_args = [
        # Output mode
        '--standalone',
        '--windows-disable-console',

        # Optimisation
        '--lto=yes',
        '--jobs=4',

        # PySide6 support
        '--enable-plugin=pyside6',

        # Windows metadata
        f'--windows-product-name={APP_NAME}',
        '--windows-company-name=Serkan ŞAHİN',
        '--windows-product-version=1.0.0.0',
        '--windows-file-version=1.0.0.0',
        f'--windows-file-description={APP_NAME}',

        # Exe name
        f'--output-filename={EXE_NAME}.exe',

        # Output location (next to main.py → main.dist)
        f'--output-dir={ROOT_DIR}',

        # Include the whole project as source packages
        '--include-package=core',
        # Compiled module packages (assetler + kaynak kod derlenip exe icine girer)
        '--include-package=cc_modules',

        # Third-party runtime dependencies
        '--include-package=xlsxwriter',  # xml-fatura Excel yazma
        '--include-package=openpyxl',   # compare-191
        '--include-package=xlrd',        # compare-191 (.xls support)
        '--include-package=bs4',         # xml-fatura (HTML parsing)
        '--include-package=pdfplumber',  # xml-fatura (PDF reading)
        '--include-package=pdfminer',    # pdfplumber dependency
        '--include-package=lxml',        # xml-fatura (XML/HTML parsing)

        # Include non-Python data files embedded in packages if any
        '--include-package-data=core',
    ]

    # Icon
    if icon_ok:
        nuitka_args.append(f'--windows-icon-from-ico={ICON_CONTRACORE}')

    nuitka_args.append(ENTRY_SCRIPT)

    # ── Build ─────────────────────────────────────────────────────────────────
    print('\n[BUILD BAŞLIYOR]')
    run_nuitka(nuitka_args)

    # ── Move dist to release ──────────────────────────────────────────────────
    move_dist_to_release(DIST_NAME, RELEASE_SUBDIR)

    # ── Copy runtime assets ───────────────────────────────────────────────────
    print('\n[ASSETS KOPYALANIYOR]')
    _copy_runtime_assets(RELEASE_SUBDIR)

    # ── Release doğrulama (kritik dosyalar mevcut mu?) ────────────────────────
    print('\n[RELEASE DOGRULAMA]')
    _verify_release(RELEASE_SUBDIR, check_update_json=False)

    # ── ZIP + SHA256 + update.json (otomatik) ─────────────────────────────────
    zip_path    = None
    update_json = None

    if args.zip:
        print('\n[ZIP + UPDATE.JSON AŞAMASI]')

        # 1. ContraCORE_update.zip oluştur (sabit isim)
        zip_path = _create_update_zip(RELEASE_SUBDIR)

        # 2. update.json üret (version=APP_VERSION, sha256 otomatik)
        import importlib.util as _ilu
        _gen_script = os.path.join(_HERE, 'gen_update_json.py')
        _spec = _ilu.spec_from_file_location('gen_update_json', _gen_script)
        _gen  = _ilu.module_from_spec(_spec)
        _spec.loader.exec_module(_gen)

        # Proje kökündeki update.json'ı güncelle (GitHub'a push edilecek kaynak)
        root_update_json = os.path.join(ROOT_DIR, 'update.json')
        _gen.generate(
            zip_path    = zip_path,
            out_path    = root_update_json,
        )

        # 3. Release klasörüne de kopyala
        release_update_json = os.path.join(RELEASE_SUBDIR, 'update.json')
        shutil.copy2(root_update_json, release_update_json)
        print(f'[OK] update.json release klasörüne kopyalandı.')

        update_json = root_update_json

        # 4. ZIP sonrası tam doğrulama (update.json dahil)
        print('\n[ZIP SONRASI DOGRULAMA]')
        _verify_release(RELEASE_SUBDIR, check_update_json=True)

    # ── Summary ───────────────────────────────────────────────────────────────
    exe_path = os.path.join(RELEASE_SUBDIR, f'{EXE_NAME}.exe')
    banner('BUILD TAMAMLANDI')
    print(f'Exe         : {exe_path}')
    print(f'Klasör      : {RELEASE_SUBDIR}')
    if zip_path:
        print(f'Update ZIP  : {zip_path}')
        print(f'update.json : {update_json}')
    print()
    if zip_path:
        print('Sonraki adımlar:')
        print('  1. update.json  -->  GitHub main branch\'e push et')
        print(f'  2. ContraCORE_update.zip  -->  GitHub release\'e yukle')
    else:
        print('Müşteriye gönderilebilir: release/ContraCORE/ klasörünün tamamı')
    print()


if __name__ == '__main__':
    main()
