#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gen_update_json.py — Update manifest üretici

build_contracore.py tarafından otomatik çağrılır.
Manuel çalıştırma:
  python build_tools/gen_update_json.py --zip release/ContraCORE_update.zip

Tek gerçek kaynak: core/version.py → APP_VERSION
update.json her build'de buradan üretilir, manuel sync gerekmez.
"""

import argparse
import hashlib
import json
import os
import sys

_HERE    = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(_HERE)


def _sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            h.update(chunk)
    return h.hexdigest()


def _read_app_version() -> str:
    """core/version.py'dan APP_VERSION'ı okur (import yapmadan — build context güvenliği)."""
    version_file = os.path.join(ROOT_DIR, 'core', 'version.py')
    with open(version_file, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line.startswith('APP_VERSION'):
                # APP_VERSION = '1.0.1'  veya APP_VERSION    = "1.0.1"
                val = line.split('=', 1)[1].strip().strip("'\"")
                return val
    raise RuntimeError('APP_VERSION bulunamadı: core/version.py')


def generate(zip_path: str, out_path: str, notes: str = '', min_version: str = '1.0.0') -> dict:
    """
    update.json içeriğini üretir ve out_path'e yazar.

    Args:
        zip_path:    Oluşturulan ContraCORE_update.zip dosyasının tam yolu
        out_path:    update.json çıktı dosyası
        notes:       Sürüm notu (opsiyonel)
        min_version: Bu güncellemenin gerektirdiği minimum sürüm
    Returns:
        Üretilen dict
    """
    version = _read_app_version()

    sha256 = ''
    if zip_path and os.path.isfile(zip_path):
        print(f'[SHA256] Hesaplanıyor: {os.path.basename(zip_path)} ...', end=' ', flush=True)
        sha256 = _sha256_file(zip_path)
        print(sha256[:16] + '...')
    else:
        print(f'[WARN] ZIP bulunamadı, sha256 boş bırakıldı: {zip_path}')

    data = {
        'version':     version,
        'mandatory':   False,
        'notes':       notes,
        'zip_name':    'ContraCORE_update.zip',
        'zip_sha256':  sha256,
        'min_version': min_version,
    }

    os.makedirs(os.path.dirname(out_path) or '.', exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f'[OK] update.json uretildi: {out_path}  (version={version}, sha256={sha256[:16]}...)')
    return data


def main():
    parser = argparse.ArgumentParser(description='update.json üretici')
    parser.add_argument('--zip',         default='',         help='ZIP dosyası yolu (SHA256 için)')
    parser.add_argument('--out',         default=os.path.join(ROOT_DIR, 'update.json'),
                        help='Çıktı update.json yolu (varsayılan: proje kökü)')
    parser.add_argument('--notes',       default='',         help='Sürüm notu')
    parser.add_argument('--min-version', default='1.0.0',    help='Minimum sürüm')
    args = parser.parse_args()

    generate(
        zip_path    = args.zip,
        out_path    = args.out,
        notes       = args.notes,
        min_version = args.min_version,
    )


if __name__ == '__main__':
    main()
