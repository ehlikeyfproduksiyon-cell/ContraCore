#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ContraCore — Developer Environment Reset

Tüm lisans, trial ve registry verilerini temizler.
Test ortamını sıfır noktasına döndürür.

KULLANIM:
    python dev_tools/reset_dev_environment.py
    python dev_tools/reset_dev_environment.py --dry-run   # ne silineceğini göster, silme
    python dev_tools/reset_dev_environment.py --list      # mevcut durumu göster

⚠  SADECE DEVELOPMENT/TEST ORTAMINDA KULLANIN.
   Production build'e dahil değildir.
"""

import os
import sys
import json
import shutil
import argparse
import platform
from pathlib import Path

# Windows konsolu UTF-8 zorlaması
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# ── Tüm storage lokasyonları ──────────────────────────────────────────────────

APPDATA     = os.environ.get('APPDATA', os.path.expanduser('~'))
PROGRAMDATA = os.environ.get('PROGRAMDATA', 'C:\\ProgramData')

LOCATIONS = {
    # ── Unified ContraCore lisansı ────────────────────────────────────────────
    'unified_license': {
        'desc': 'ContraCore Unified License',
        'type': 'file',
        'path': os.path.join(APPDATA, 'ContraCore', 'license.json'),
    },
    'unified_dir': {
        'desc': 'ContraCore AppData klasörü',
        'type': 'dir_if_empty',
        'path': os.path.join(APPDATA, 'ContraCore'),
    },

    # ── XML Fatura — AppData ──────────────────────────────────────────────────
    'xf_license': {
        'desc': 'XML Fatura legacy lisans anahtarı',
        'type': 'file',
        'path': os.path.join(APPDATA, 'XMLFaturaOtomasyonu', 'license.key'),
    },
    'xf_trial': {
        'desc': 'XML Fatura trial JSON',
        'type': 'file',
        'path': os.path.join(APPDATA, 'XMLFaturaOtomasyonu', 'trial.json'),
    },

    # ── XML Fatura — Registry ─────────────────────────────────────────────────
    'xf_registry': {
        'desc': 'XML Fatura trial registry (HKCU\\Software\\XMLFaturaOtomasyonu)',
        'type': 'registry',
        'key' : 'HKEY_CURRENT_USER',
        'path': r'Software\XMLFaturaOtomasyonu',
    },

    # ── XML Fatura — ProgramData gizli dosya ─────────────────────────────────
    'xf_sysfile': {
        'desc': 'XML Fatura gizli trial dosyası (%ProgramData%\\.xmlfatura\\t.dat)',
        'type': 'file',
        'path': os.path.join(PROGRAMDATA, '.xmlfatura', 't.dat'),
    },

    # ── Compare-191 — AppData ─────────────────────────────────────────────────
    'c191_license': {
        'desc': 'Compare-191 legacy lisans anahtarı',
        'type': 'file',
        'path': os.path.join(APPDATA, 'MuavinKarsilastirma', 'license.key'),
    },
    'c191_trial': {
        'desc': 'Compare-191 trial JSON',
        'type': 'file',
        'path': os.path.join(APPDATA, 'MuavinKarsilastirma', 'trial.json'),
    },

    # ── Compare-191 — Registry ────────────────────────────────────────────────
    'c191_registry': {
        'desc': 'Compare-191 trial registry (HKCU\\Software\\MuavinKarsilastirma)',
        'type': 'registry',
        'key' : 'HKEY_CURRENT_USER',
        'path': r'Software\MuavinKarsilastirma',
    },

    # ── Compare-191 — ProgramData gizli dosya ────────────────────────────────
    'c191_sysfile': {
        'desc': 'Compare-191 gizli trial dosyası (%ProgramData%\\.muavinkar\\t.dat)',
        'type': 'file',
        'path': os.path.join(PROGRAMDATA, '.muavinkar', 't.dat'),
    },
}


# ── Durum kontrol ─────────────────────────────────────────────────────────────

def _file_exists(path: str) -> bool:
    try:
        return os.path.isfile(path)
    except Exception:
        return False


def _reg_exists(hive_str: str, subkey: str) -> bool:
    if platform.system() != 'Windows':
        return False
    try:
        import winreg
        hive = getattr(winreg, hive_str)
        k    = winreg.OpenKey(hive, subkey)
        winreg.CloseKey(k)
        return True
    except Exception:
        return False


def _file_summary(path: str) -> str:
    """Dosya içeriğinin kısa özeti."""
    try:
        with open(path, encoding='utf-8') as f:
            raw = f.read(300)
        if path.endswith('.json'):
            data = json.loads(raw + '...' if len(raw) == 300 else raw)
            if 'key' in data:
                return f"key={data['key'][:12]}..."
            if 'modules' in data:
                mods = list(data['modules'].keys())
                return f"modules={mods}"
            if 'start_date' in data:
                return f"start={data['start_date']}, used={data.get('used_files', '?')}"
        return raw[:80].replace('\n', ' ')
    except Exception as e:
        return f"(okunamadı: {e})"


def _reg_summary(hive_str: str, subkey: str) -> str:
    try:
        import winreg
        hive   = getattr(winreg, hive_str)
        key    = winreg.OpenKey(hive, subkey)
        parts  = []
        i      = 0
        while True:
            try:
                name, val, _ = winreg.EnumValue(key, i)
                parts.append(f"{name}={val}")
                i += 1
            except OSError:
                break
        winreg.CloseKey(key)
        return ', '.join(parts[:4])
    except Exception:
        return ''


# ── Ana fonksiyonlar ──────────────────────────────────────────────────────────

def list_status():
    """Mevcut tüm lisans verilerinin durumunu gösterir."""
    print('\n' + '═' * 60)
    print('  ContraCore — Lisans Storage Durumu')
    print('═' * 60)

    for name, loc in LOCATIONS.items():
        ltype = loc['type']
        desc  = loc['desc']

        if ltype in ('file', 'dir_if_empty'):
            path   = loc['path']
            exists = _file_exists(path) if ltype == 'file' else os.path.isdir(path)
            status = '✅ VAR' if exists else '⬜ YOK'
            detail = _file_summary(path) if exists and ltype == 'file' else ''
            print(f'\n  {status}  {desc}')
            print(f'         {path}')
            if detail:
                print(f'         → {detail}')

        elif ltype == 'registry':
            exists = _reg_exists(loc['key'], loc['path'])
            status = '✅ VAR' if exists else '⬜ YOK'
            detail = _reg_summary(loc['key'], loc['path']) if exists else ''
            print(f'\n  {status}  {desc}')
            print(f'         HKCU\\{loc["path"]}')
            if detail:
                print(f'         → {detail}')

    print('\n' + '═' * 60 + '\n')


def reset_all(dry_run: bool = False):
    """Tüm lisans ve trial verilerini temizler."""
    mode = '[DRY-RUN] ' if dry_run else ''
    print(f'\n{mode}ContraCore — Environment Reset')
    print('─' * 50)

    deleted  = 0
    skipped  = 0
    errors   = []

    for name, loc in LOCATIONS.items():
        ltype = loc['type']
        desc  = loc['desc']

        if ltype == 'file':
            path = loc['path']
            if _file_exists(path):
                if dry_run:
                    print(f'  [SILINECEK] {desc}')
                    print(f'              {path}')
                    skipped += 1
                else:
                    try:
                        os.remove(path)
                        print(f'  ✓ Silindi : {desc}')
                        deleted += 1
                    except Exception as e:
                        print(f'  ✗ HATA    : {desc} — {e}')
                        errors.append(str(e))
            else:
                print(f'  – Yok zaten: {desc}')

        elif ltype == 'dir_if_empty':
            path = loc['path']
            if os.path.isdir(path):
                try:
                    contents = os.listdir(path)
                    if not contents:
                        if dry_run:
                            print(f'  [SİLİNECEK boş klasör] {path}')
                            skipped += 1
                        else:
                            os.rmdir(path)
                            print(f'  ✓ Boş klasör silindi: {path}')
                            deleted += 1
                    else:
                        print(f'  – Klasör dolu, atlandı: {path} ({contents})')
                except Exception as e:
                    errors.append(str(e))

        elif ltype == 'registry':
            if platform.system() != 'Windows':
                continue
            exists = _reg_exists(loc['key'], loc['path'])
            if exists:
                if dry_run:
                    print(f'  [SİLİNECEK] Registry: HKCU\\{loc["path"]}')
                    skipped += 1
                else:
                    try:
                        import winreg
                        hive = getattr(winreg, loc['key'])
                        _delete_reg_tree(hive, loc['path'])
                        print(f'  ✓ Registry silindi: HKCU\\{loc["path"]}')
                        deleted += 1
                    except Exception as e:
                        print(f'  ✗ Registry HATA: HKCU\\{loc["path"]} — {e}')
                        errors.append(str(e))
            else:
                print(f'  – Registry yok zaten: HKCU\\{loc["path"]}')

    print('─' * 50)
    if dry_run:
        print(f'  Dry-run: {skipped} öğe silinecek (gerçekte silme yapılmadı).\n')
    else:
        print(f'  Tamamlandı: {deleted} öğe silindi, {len(errors)} hata.\n')
        if errors:
            print('  Hatalar:')
            for e in errors:
                print(f'    • {e}')


def _delete_reg_tree(hive, path: str):
    """Registry anahtarını alt anahtarlarıyla birlikte siler."""
    import winreg
    try:
        key = winreg.OpenKey(hive, path, 0, winreg.KEY_ALL_ACCESS)
        while True:
            try:
                subkey = winreg.EnumKey(key, 0)
                _delete_reg_tree(hive, f'{path}\\{subkey}')
            except OSError:
                break
        winreg.CloseKey(key)
        winreg.DeleteKey(hive, path)
    except FileNotFoundError:
        pass


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description='ContraCore — Developer Environment Reset',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Örnekler:
  python dev_tools/reset_dev_environment.py           # Tümünü sil
  python dev_tools/reset_dev_environment.py --dry-run # Önizleme (silme)
  python dev_tools/reset_dev_environment.py --list    # Mevcut durum
        """
    )
    parser.add_argument('--dry-run', action='store_true',
                        help='Ne silineceğini göster, gerçekte silme yapma')
    parser.add_argument('--list',    action='store_true',
                        help='Mevcut tüm lisans verilerinin durumunu göster')
    parser.add_argument('--force',   action='store_true',
                        help='Onay sormadan sil (script/automation kullanımı için)')
    args = parser.parse_args()

    if args.list:
        list_status()
        return

    if not args.dry_run and not args.force:
        print('\n⚠  Bu işlem TÜM lisans ve trial verilerini silecek!')
        ans = input('   Devam etmek istiyor musunuz? [e/H]: ').strip().lower()
        if ans != 'e':
            print('   İptal edildi.\n')
            return

    reset_all(dry_run=args.dry_run)


if __name__ == '__main__':
    main()
