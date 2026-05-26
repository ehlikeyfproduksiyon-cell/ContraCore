#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ContraCore — Runtime Crash Logger

Müşteri ortamında yakalanan istisnalar %APPDATA%\ContraCore\crash_log.txt
dosyasına yazılır. Log max 500 KB'da tutulur (eski kısım kırpılır).

Kullanım:
    from core.crash_log import install
    install()   # main.py başında bir kez çağır

Crash log konumu:
    %APPDATA%\ContraCore\crash_log.txt
"""

import os
import sys
import traceback
from datetime import datetime

_LOG_DIR  = os.path.join(os.environ.get('APPDATA', os.path.expanduser('~')), 'ContraCore')
_LOG_FILE = os.path.join(_LOG_DIR, 'crash_log.txt')
_MAX_SIZE = 500 * 1024   # 500 KB


def _trim_log():
    """Log dosyası _MAX_SIZE'ı aşarsa ilk yarısını sil."""
    try:
        if os.path.exists(_LOG_FILE) and os.path.getsize(_LOG_FILE) > _MAX_SIZE:
            with open(_LOG_FILE, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
            with open(_LOG_FILE, 'w', encoding='utf-8') as f:
                f.write('... [eski log kırpıldı] ...\n\n')
                f.write(content[len(content) // 2:])
    except Exception:
        pass


def write_entry(header: str, body: str):
    """Log dosyasına tek bir kayıt yazar."""
    try:
        os.makedirs(_LOG_DIR, exist_ok=True)
        _trim_log()
        ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        sep = '─' * 60
        entry = f'\n{sep}\n[{ts}] {header}\n{sep}\n{body}\n'
        with open(_LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(entry)
    except Exception:
        pass   # log hataları uygulamayı asla çökertmesin


def log_exception(exc_type, exc_value, exc_tb):
    """sys.excepthook uyumlu — yakalanmamış istisnaları loglar."""
    tb_str = ''.join(traceback.format_exception(exc_type, exc_value, exc_tb))
    write_entry(f'UNHANDLED EXCEPTION: {exc_type.__name__}', tb_str)
    # Orijinal hook'u da çağır (genelde stderr'e yazar; standalone'da /dev/null)
    sys.__excepthook__(exc_type, exc_value, exc_tb)


def install():
    """
    Uygulama başlangıcında bir kez çağrılır.
    - sys.excepthook'u log yazacak şekilde değiştirir.
    - Başlangıç kaydı yazar (sürüm, Python, platform).
    """
    sys.excepthook = log_exception

    import platform
    body = (
        f'Python   : {sys.version}\n'
        f'Platform : {platform.platform()}\n'
        f'Exe      : {sys.executable}\n'
        f'CWD      : {os.getcwd()}\n'
    )
    write_entry('APP START', body)
