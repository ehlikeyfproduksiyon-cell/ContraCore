#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Shared build utilities for ContraCore build scripts.
"""

import os
import shutil
import subprocess
import sys

# ── Paths ──────────────────────────────────────────────────────────────────────
BUILD_TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR        = os.path.dirname(BUILD_TOOLS_DIR)
RELEASE_DIR     = os.path.join(ROOT_DIR, 'release')

ICON_CONTRACORE = os.path.join(ROOT_DIR, 'Logom', 'ico', 'ContraCoreAppRenkliBeyaz2.ico')
ICON_SETUP      = os.path.join(ROOT_DIR, 'Icon', 'SETUP.ico')


def banner(text: str):
    w = 60
    print('=' * w)
    print(f'  {text}')
    print('=' * w)


def check_nuitka():
    try:
        result = subprocess.run(
            [sys.executable, '-m', 'nuitka', '--version'],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            raise RuntimeError('Nuitka döndürdü hata kodu')
        version = result.stdout.strip().splitlines()[0]
        print(f'[OK] Nuitka: {version}')
    except FileNotFoundError:
        print('[HATA] Nuitka bulunamadı. Yüklemek için:')
        print('       pip install nuitka')
        sys.exit(1)


def verify_icon(path: str, label: str) -> bool:
    if os.path.exists(path):
        print(f'[OK] {label}: {os.path.basename(path)}')
        return True
    print(f'[UYARI] {label} bulunamadı: {path}')
    return False


def copy_icon_to_build(icon_src: str, build_dir: str) -> str | None:
    """Copy icon into build dir and return the destination path."""
    if not os.path.exists(icon_src):
        return None
    dst = os.path.join(build_dir, os.path.basename(icon_src))
    shutil.copy2(icon_src, dst)
    return dst


def ensure_release_dir(name: str) -> str:
    path = os.path.join(RELEASE_DIR, name)
    os.makedirs(path, exist_ok=True)
    return path


def copy_data_dir(src: str, dst_parent: str, dir_name: str | None = None):
    """Copy a directory into dst_parent. dir_name overrides the folder name."""
    if not os.path.exists(src):
        print(f'[UYARI] Kaynak bulunamadı, atlanıyor: {src}')
        return
    name = dir_name or os.path.basename(src)
    dst  = os.path.join(dst_parent, name)
    if os.path.exists(dst):
        shutil.rmtree(dst)
    shutil.copytree(src, dst)
    print(f'[OK] Kopyalandı: {name}/')


def run_nuitka(args: list[str]):
    cmd = [sys.executable, '-m', 'nuitka'] + args
    print('\nNuitka komutu:')
    print('  ' + ' '.join(cmd))
    print()
    result = subprocess.run(cmd, cwd=ROOT_DIR)
    if result.returncode != 0:
        print(f'\n[HATA] Nuitka build başarısız (exit {result.returncode})')
        sys.exit(result.returncode)
    print('\n[OK] Nuitka build tamamlandı.')


def move_dist_to_release(dist_name: str, release_dir: str):
    """
    Nuitka outputs to ROOT_DIR/<script>.dist by default.
    Move/merge it into release_dir.
    """
    dist_path = os.path.join(ROOT_DIR, dist_name)
    if not os.path.exists(dist_path):
        print(f'[HATA] Beklenen dist klasörü bulunamadı: {dist_path}')
        sys.exit(1)

    if os.path.exists(release_dir):
        shutil.rmtree(release_dir)
    shutil.move(dist_path, release_dir)
    print(f'[OK] Release tasindi: {release_dir}')
