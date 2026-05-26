#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ContraCore — Unified License Manager (public API)

Tüm dış kod bu modülü import eder; alt modüllere doğrudan erişmez.
"""

from datetime import datetime

from core.license.hwid      import get_hwid
from core.license.validator  import validate_v2_key
from core.license.storage    import (
    load_license, write_module_entry, read_module_entry, is_entry_valid,
)
from core.license.trial import (
    start_trial, get_trial_status, add_trial_usage,
    is_trial_started, get_trial_max_files,
)

TIERS = ('basic', 'pro', 'enterprise')

__all__ = [
    'get_hwid',
    'activate_module',
    'check_module_license',
    'is_module_licensed',
    'get_module_info',
    'get_all_module_statuses',
    'has_unified_license',
    'start_trial',
    'get_trial_status',
    'add_trial_usage',
    'is_trial_started',
    'get_trial_max_files',
]


def has_unified_license() -> bool:
    """Geçerli bir license.json var mı?"""
    return load_license() is not None


def activate_module(
    module_id: str, key: str, tier: str = 'pro'
) -> 'tuple[bool, str, datetime | None]':
    """
    Anahtarı doğrular; başarılıysa modülü license.json'a kaydeder.
    Returns: (success, message, expire)
    """
    valid, msg, expire = validate_v2_key(key, module_id)
    if not valid:
        return False, msg, None

    _tier = tier if tier in TIERS else 'pro'
    write_module_entry(module_id, key, expire, _tier)
    return True, 'Lisans başarıyla aktive edildi.', expire


def check_module_license(
    module_id: str,
) -> 'tuple[bool, str, datetime | None]':
    """
    Modülün lisans durumunu döner.
    Returns: (valid, message, expire)
    """
    valid, msg, expire = is_entry_valid(module_id)
    return valid, msg, expire


def is_module_licensed(module_id: str) -> 'tuple[bool, str]':
    """
    Kısa-devre lisans kontrolü.
    Returns: (licensed, reason)
    """
    valid, msg, _ = is_entry_valid(module_id)
    return valid, msg


def get_module_info(module_id: str) -> 'dict | None':
    """license.json'daki modül kaydını döner; yoksa None."""
    return read_module_entry(module_id)


def get_all_module_statuses(module_ids: 'list[str]') -> 'dict[str, dict]':
    """
    Sidebar ve lisans dialog'u için tüm modüllerin durumunu döner.
    Returns: { module_id: { 'enabled': bool|None, 'reason': str, 'expire': str|None } }

    enabled=True  → lisanslı
    enabled=None  → deneme (lisans yok ama trial var)
    enabled=False → lisanssız, trial da bitmş/başlatılmamış
    """
    data = load_license()
    result = {}

    for mid in module_ids:
        if data is None:
            # Unified license yok — trial durumuna bak
            aktif, _, _, _ = get_trial_status(mid)
            result[mid] = {
                'enabled': None if aktif else False,
                'reason' : '',
                'expire' : None,
            }
            continue

        entry = data.get('modules', {}).get(mid)
        if entry is None:
            aktif, _, _, _ = get_trial_status(mid)
            result[mid] = {
                'enabled': None if aktif else False,
                'reason' : '',
                'expire' : None,
            }
            continue

        valid, reason, _ = is_entry_valid(mid)
        result[mid] = {
            'enabled': valid,
            'reason' : reason,
            'expire' : entry.get('expire'),
        }

    return result
