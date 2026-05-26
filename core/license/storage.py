#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import hashlib
import hmac
import json
import os
from datetime import datetime, timedelta

from core.license.hwid    import get_hwid
from core.license._secret  import get as _secret

_LICENSE_DIR  = os.path.join(
    os.environ.get('APPDATA', os.path.expanduser('~')), 'ContraCore'
)
_LICENSE_FILE = os.path.join(_LICENSE_DIR, 'license.json')

_GRACE_DAYS = 1


# ── JSON imzası ───────────────────────────────────────────────────────────────

def _make_payload(data: dict) -> str:
    hwid    = data.get('hwid', '')
    modules = data.get('modules', {})
    parts   = [hwid]
    for mid in sorted(modules):
        m = modules[mid]
        parts.append(
            f"{mid}:{m.get('enabled',False)}:{m.get('expire','')}:"
            f"{m.get('tier','')}:{m.get('key','')}"
        )
    return '|'.join(parts)


def _sign(payload: str) -> str:
    return hmac.new(
        _secret().encode(), payload.encode(), hashlib.sha256
    ).hexdigest()[:16].upper()


# ── Okuma / Yazma ─────────────────────────────────────────────────────────────

def load_license() -> 'dict | None':
    """
    license.json yükler ve doğrular.
    HMAC imzası geçersizse veya HWID eşleşmezse None döner.
    """
    if not os.path.exists(_LICENSE_FILE):
        return None
    try:
        with open(_LICENSE_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        sig  = data.pop('sig', '')
        valid = _sign(_make_payload(data)) == sig
        data['sig'] = sig
        if not valid:
            return None
        if data.get('hwid') != get_hwid():
            return None
        return data
    except Exception:
        return None


def save_license(data: dict):
    """İmzalayıp license.json'a yazar."""
    os.makedirs(_LICENSE_DIR, exist_ok=True)
    d = {k: v for k, v in data.items() if k != 'sig'}
    d['sig'] = _sign(_make_payload(d))
    with open(_LICENSE_FILE, 'w', encoding='utf-8') as f:
        json.dump(d, f, ensure_ascii=False, indent=2)


# ── Modül kaydı ───────────────────────────────────────────────────────────────

def write_module_entry(module_id: str, key: str, expire: datetime, tier: str):
    """Modülü license.json'a kaydeder; diğer modüllere dokunmaz."""
    data = load_license() or {'hwid': get_hwid(), 'modules': {}}
    data['hwid'] = get_hwid()
    data.setdefault('modules', {})[module_id] = {
        'enabled': True,
        'expire' : expire.strftime('%Y-%m-%d'),
        'tier'   : tier,
        'key'    : key,
    }
    save_license(data)


def read_module_entry(module_id: str) -> 'dict | None':
    """Modülün license.json'daki kaydını döner; geçersiz/yoksa None."""
    data = load_license()
    if data is None:
        return None
    return data.get('modules', {}).get(module_id)


def is_entry_valid(module_id: str) -> 'tuple[bool, str, datetime | None]':
    """
    License.json'daki kayda göre modülün geçerli olup olmadığını döner.
    Returns: (valid, reason, expire)
    """
    entry = read_module_entry(module_id)
    if entry is None:
        return False, 'Modül lisansınıza kayıtlı değil.', None
    if not entry.get('enabled', False):
        return False, 'Modül lisansınızda aktif değil.', None

    exp_str = entry.get('expire')
    if exp_str:
        try:
            expire = datetime.strptime(exp_str, '%Y-%m-%d')
            if datetime.now() > expire + timedelta(days=_GRACE_DAYS):
                return False, f'Lisans süresi doldu. ({expire.strftime("%d.%m.%Y")})', None
            return True, 'Lisans geçerli.', expire
        except ValueError:
            pass

    return True, 'Lisans geçerli.', None
