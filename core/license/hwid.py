#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import hashlib
import platform
import subprocess


def get_hwid() -> str:
    """
    XXXX-XXXX-XXXX-XXXX formatında donanım kimliği döner.
    Birincil kaynak: Windows MachineGuid (registry).
    Yedek: CPU ProcessorId.
    """
    parts = []

    if platform.system() == 'Windows':
        try:
            import winreg
            key  = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                                  r'SOFTWARE\Microsoft\Cryptography')
            guid, _ = winreg.QueryValueEx(key, 'MachineGuid')
            winreg.CloseKey(key)
            if guid and guid.strip():
                parts.append(guid.replace('-', '').upper()[:16])
        except Exception:
            pass

        if not parts:
            try:
                out = subprocess.check_output(
                    'wmic cpu get ProcessorId /value',
                    shell=True, stderr=subprocess.DEVNULL
                ).decode(errors='ignore')
                for line in out.strip().splitlines():
                    if '=' in line:
                        val = line.split('=')[1].strip()
                        if val:
                            parts.append(val)
                            break
            except Exception:
                pass

        if not parts:
            parts.append('CPU0')
    else:
        parts.append(platform.node())
        parts.append(platform.processor())

    raw = '_'.join(filter(None, parts)) or 'DEFAULT'
    h   = hashlib.sha256(raw.encode()).hexdigest().upper()
    return f'{h[0:4]}-{h[4:8]}-{h[8:12]}-{h[12:16]}'
