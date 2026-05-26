#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import base64
import hashlib
import hmac
from datetime import datetime, date, timedelta

from core.license.hwid   import get_hwid
from core.license._secret import get as _secret

_EPOCH       = date(2020, 1, 1)
_GRACE_DAYS  = 1
_B32_CHARS   = frozenset('ABCDEFGHIJKLMNOPQRSTUVWXYZ234567')


# ── Düşük seviye HMAC yardımcısı ─────────────────────────────────────────────

def _h(tag: str, data: 'str | bytes') -> bytes:
    key = (_secret() + tag).encode()
    msg = data if isinstance(data, bytes) else data.encode()
    return hmac.new(key, msg, hashlib.sha256).digest()


# ── Keygen (geliştirici aracı — exe'ye gömülmez) ─────────────────────────────

def generate_v2_key(hwid: str, module_id: str, expire: datetime) -> str:
    """
    V2 opaque lisans anahtarı üretir.
    Format: V2-XXXXXXXX-XXXXXXXX-XXXXXXXX-XXXXXXXX
    """
    days = (expire.date() - _EPOCH).days
    if not (0 <= days <= 0xFFFFFF):
        raise ValueError('Geçersiz tarih aralığı.')

    body = bytearray(16)
    body[0]   = 0x02
    body[1]   = (days >> 16) & 0xFF
    body[2]   = (days >>  8) & 0xFF
    body[3]   =  days        & 0xFF
    body[4:12] = _h('_H', hwid)[:8]
    body[12:16] = _h('_M', module_id)[:4]

    sig     = _h('_S', bytes(body))[:4]
    payload = bytes(body) + sig
    b32     = base64.b32encode(payload).decode()
    return 'V2-' + '-'.join(b32[i:i+8] for i in range(0, 32, 8))


# ── Doğrulama adımları (ayrıştırılmış) ───────────────────────────────────────

def _parse_key(key: str) -> 'bytes | None':
    k   = key.strip().upper()
    if not k.startswith('V2-'):
        return None
    b32 = k[3:].replace('-', '')
    if len(b32) != 32 or any(c not in _B32_CHARS for c in b32):
        return None
    try:
        payload = base64.b32decode(b32)
    except Exception:
        return None
    if len(payload) != 20 or payload[0] != 0x02:
        return None
    return payload


def _check_integrity(body: bytes, sig: bytes) -> bool:
    return sig == _h('_S', body)[:4]


def _check_expire(body: bytes) -> 'tuple[bool, datetime]':
    days   = (body[1] << 16) | (body[2] << 8) | body[3]
    expire = datetime.combine(_EPOCH + timedelta(days=days), datetime.min.time())
    return datetime.now() <= expire + timedelta(days=_GRACE_DAYS), expire


def _check_hwid(body: bytes) -> bool:
    return body[4:12] == _h('_H', get_hwid())[:8]


def _check_module(body: bytes, module_id: str) -> bool:
    return body[12:16] == _h('_M', module_id)[:4]


# ── Ana doğrulama fonksiyonu ──────────────────────────────────────────────────

def validate_v2_key(
    key: str, module_id: str
) -> 'tuple[bool, str, datetime | None]':
    """
    Returns: (valid, message, expire_datetime | None)
    """
    payload = _parse_key(key)
    if payload is None:
        return False, 'Geçersiz anahtar formatı.', None

    body, sig = payload[:16], payload[16:]

    if not _check_integrity(body, sig):
        return False, 'Geçersiz lisans anahtarı.', None

    ok_exp, expire = _check_expire(body)
    if not ok_exp:
        return False, f'Lisans süresi doldu. ({expire.strftime("%d.%m.%Y")})', None

    if not _check_hwid(body):
        return False, 'Bu lisans başka bir bilgisayara kayıtlıdır.', None

    if not _check_module(body, module_id):
        return False, 'Bu anahtar farklı bir modüle aittir.', None

    return True, 'Lisans geçerli.', expire
