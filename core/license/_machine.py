#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ContraCore — internal, do not distribute
"""
Machine fingerprint — hardware-bound identifier.
Combines MachineGuid + volume serial → stable, no-admin, deterministic.
"""

import hashlib
import os
import platform

_CACHE: 'str | None' = None


def get_machine_id() -> str:
    """
    Returns a 64-char hex machine fingerprint.
    Stable across reboots; changes only on major hardware/OS reinstall.
    Falls back to env vars on non-Windows.
    """
    global _CACHE
    if _CACHE:
        return _CACHE

    parts: list[str] = []

    if platform.system() == 'Windows':
        # 1. MachineGuid — HKLM, readable without admin
        try:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r'SOFTWARE\Microsoft\Cryptography'
            )
            val, _ = winreg.QueryValueEx(key, 'MachineGuid')
            winreg.CloseKey(key)
            if val:
                parts.append(val)
        except Exception:
            pass

        # 2. Volume serial of system drive (C:\)
        try:
            import ctypes
            serial = ctypes.c_ulong(0)
            ctypes.windll.kernel32.GetVolumeInformationW(
                'C:\\', None, 0, ctypes.byref(serial), None, None, None, 0
            )
            if serial.value:
                parts.append(str(serial.value))
        except Exception:
            pass

    # Non-Windows / fallback
    if not parts:
        parts.append(os.environ.get('COMPUTERNAME', 'cc_unknown'))
        parts.append(os.environ.get('USERNAME',     'cc_user'))

    _CACHE = hashlib.sha256('|'.join(parts).encode()).hexdigest()
    return _CACHE
