#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ContraCore — Update State

pending_update.json IPC dosyasını okur/siler.
Launcher tarafından yazılır; ContraCORE.exe başlarken okur.
"""

import json
import os

_STATE_FILE = os.path.join(
    os.environ.get('APPDATA', ''), 'ContraCore', 'pending_update.json'
)


def read_pending() -> 'dict | None':
    """pending_update.json varsa içeriğini döner, yoksa None."""
    try:
        with open(_STATE_FILE, encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return None


def clear_pending():
    """pending_update.json'ı siler (güncelleme tamamlanınca Launcher siler, ama yedek)."""
    try:
        os.remove(_STATE_FILE)
    except Exception:
        pass
