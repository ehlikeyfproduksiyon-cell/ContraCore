#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ContraCore — Trial Yönetimi  (v2 — machine-bound + clock rollback koruması)

Üç katmanlı depolama:
  1. AppData JSON          (APPDATA/ContraCore/trial_{module}.json)
  2. Registry (açık)       HKCU/Software/ContraCore/Trial/{module}
  3. Registry (gizli)      HKCU/Software/Classes/CLSID/{machine-derived-guid}

Güvenlik:
  • HMAC imzası machine fingerprint içeriyor → başka makinede geçersiz
  • Format versiyonu v=2 → eski imzasız veriler otomatik reddedilir
  • Gizli registry yolu machine fingerprint'ten türetilen CLSID GUID →
    standart "ContraCore sil" bat script'i bu yolu bilemez
  • Üç kaynaktan herhangi biri geçerli aktif veri içeriyorsa trial aktif
  • Üç kaynaktan herhangi biri GEÇMİŞ veri içeriyorsa is_trial_started=True
    (süresi dolmuş trial yeniden başlatılamaz aynı makinede)
  • last_seen koruması: sistem saati geri alınırsa kota doldurulur →
    trial kalıcı olarak biter (CLOCK_ROLLBACK_DETECTED)
"""

import hashlib
import hmac
import json
import os
import platform
from datetime import datetime, timezone

_IS_WIN = platform.system() == 'Windows'

# ── AppData dizini ────────────────────────────────────────────────────────────
_DATA_DIR = os.path.join(
    os.environ.get('APPDATA', os.path.expanduser('~')), 'ContraCore'
)

# ── Modül konfigürasyonu ──────────────────────────────────────────────────────
_TRIAL_CFG: 'dict[str, dict]' = {
    'xml-fatura':  {'days': 30, 'max_files': 5000},
    'compare-191': {'days': 30, 'max_files': 5000},  # max_files = muavin satır sayısı
    'karsit-ymm':  {'days': 30, 'max_files': 10},    # max_files = karşıt firma sayısı
}
_DEFAULT_CFG = {'days': 30, 'max_files': 500}

# ── Rollback koruma sabitleri ─────────────────────────────────────────────────
_ROLLBACK_TOLERANCE_SEC  = 300   # 5 dakika — kısa NTP drift'i geçer
_LS_UPDATE_INTERVAL_SEC  = 600   # last_seen en fazla 10 dakikada bir yazılır


def _cfg(module_id: str) -> dict:
    return _TRIAL_CFG.get(module_id, _DEFAULT_CFG)


def get_trial_max_files(module_id: str) -> int:
    return _cfg(module_id)['max_files']


# ── Machine fingerprint ───────────────────────────────────────────────────────

def _mid() -> str:
    from core.license._machine import get_machine_id
    return get_machine_id()


# ── HMAC — ana imza (machine-bound, v2) ──────────────────────────────────────

def _trial_sign(start_date: str, used_files: int) -> str:
    from core.license._secret import get as _secret
    payload = f'{_mid()[:12]}:{start_date}:{used_files}'
    return hmac.new(
        _secret().encode(), payload.encode(), hashlib.sha256
    ).hexdigest()[:20]


def _trial_verify(data: dict) -> bool:
    """v=2 formatı ve machine-bound HMAC zorunludur."""
    try:
        if data.get('v') != 2:
            return False
        sd = data.get('start_date', '')
        uf = int(data.get('used_files', 0))
        stored_sig = data.get('sig')
        if not stored_sig:
            return False
        return stored_sig == _trial_sign(sd, uf)
    except Exception:
        return False


# ── HMAC — last_seen imzası (clock rollback koruması) ────────────────────────

def _ls_sign(last_seen: str) -> str:
    """last_seen ayrı alanla imzalanır — başka alanlara bağımlı değil."""
    from core.license._secret import get as _secret
    payload = f'{_mid()[:12]}:ls:{last_seen}'
    return hmac.new(
        _secret().encode(), payload.encode(), hashlib.sha256
    ).hexdigest()[:16]


def _ls_verify(last_seen: str, ls_sig: str) -> bool:
    try:
        return bool(ls_sig) and ls_sig == _ls_sign(last_seen)
    except Exception:
        return False


def _now_iso() -> str:
    return datetime.now().strftime('%Y-%m-%dT%H:%M:%S')


def _iso_to_ts(iso: str) -> 'float | None':
    """ISO string'i unix timestamp'e çevirir. Hata → None."""
    try:
        return datetime.strptime(iso, '%Y-%m-%dT%H:%M:%S').timestamp()
    except Exception:
        return None


# ── Rollback tespiti ──────────────────────────────────────────────────────────

def _check_rollback(last_seen_iso: str) -> bool:
    """
    Şu anki zaman, last_seen'den tolerance kadar GERİDEYSE rollback var.
    Timezone-safe: ikisi de localtime'dan türetildiği için tutarlı.
    """
    ls_ts = _iso_to_ts(last_seen_iso)
    if ls_ts is None:
        return False
    now_ts = datetime.now().timestamp()
    return now_ts < ls_ts - _ROLLBACK_TOLERANCE_SEC


# ── Yardımcı: aktif mi? ───────────────────────────────────────────────────────

def _is_active(data: dict, module_id: str) -> bool:
    try:
        cfg  = _cfg(module_id)
        sd   = datetime.strptime(data['start_date'], '%Y-%m-%d')
        used = int(data.get('used_files', 0))
        return (
            max(0, cfg['days']      - (datetime.now() - sd).days) > 0
            and max(0, cfg['max_files'] - used) > 0
        )
    except Exception:
        return False


# ─────────────────────────────────────────────────────────────────────────────
# KATMAN 1 — AppData JSON
# ─────────────────────────────────────────────────────────────────────────────

def _trial_file(module_id: str) -> str:
    safe = module_id.replace('-', '_')
    return os.path.join(_DATA_DIR, f'trial_{safe}.json')


def _file_read(module_id: str) -> 'dict | None':
    try:
        with open(_trial_file(module_id), 'r', encoding='utf-8') as f:
            data = json.load(f)
        if not _trial_verify(data):
            _log_trial_event(module_id, 'FILE_INVALID',
                             f"start_date={data.get('start_date')} — imza geçersiz")
            return None
        # last_seen alanını doğrula (opsiyonel — yoksa None)
        ls    = data.get('ls')
        ls_sg = data.get('lss')
        data['_ls_ok'] = _ls_verify(ls, ls_sg) if ls else None  # None = alan yok
        return data
    except Exception:
        return None


def _file_write(module_id: str, start_date: str, used_files: int,
                last_seen: 'str | None' = None):
    try:
        os.makedirs(_DATA_DIR, exist_ok=True)
        ls  = last_seen or _now_iso()
        sig = _trial_sign(start_date, used_files)
        lss = _ls_sign(ls)
        with open(_trial_file(module_id), 'w', encoding='utf-8') as f:
            json.dump({
                'v': 2, 'start_date': start_date, 'used_files': used_files,
                'sig': sig, 'ls': ls, 'lss': lss,
            }, f)
    except Exception:
        pass


# ─────────────────────────────────────────────────────────────────────────────
# KATMAN 2 — Registry (açık yol)
# ─────────────────────────────────────────────────────────────────────────────

def _reg_key(module_id: str) -> str:
    safe = module_id.replace('-', '_')
    return rf'Software\ContraCore\Trial\{safe}'


def _reg_read(module_id: str) -> 'dict | None':
    if not _IS_WIN:
        return None
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, _reg_key(module_id))
        sd, _ = winreg.QueryValueEx(key, 'start_date')
        uc, _ = winreg.QueryValueEx(key, 'used_count')
        vr, _ = winreg.QueryValueEx(key, 'vr')
        try:
            sg, _ = winreg.QueryValueEx(key, 'sig')
        except OSError:
            sg = None
        try:
            ls,  _ = winreg.QueryValueEx(key, 'ls')
            lss, _ = winreg.QueryValueEx(key, 'lss')
        except OSError:
            ls = lss = None
        winreg.CloseKey(key)
        data = {'v': int(vr) if vr else 0, 'start_date': sd,
                'used_files': int(uc), 'sig': sg, 'ls': ls, 'lss': lss}
        if not _trial_verify(data):
            _log_trial_event(module_id, 'REGISTRY_INVALID',
                             f'start_date={sd} — imza geçersiz')
            return None
        data['_ls_ok'] = _ls_verify(ls, lss) if ls else None
        return data
    except Exception:
        return None


def _reg_write(module_id: str, start_date: str, used_files: int,
               last_seen: 'str | None' = None):
    if not _IS_WIN:
        return
    try:
        import winreg
        ls  = last_seen or _now_iso()
        sig = _trial_sign(start_date, used_files)
        lss = _ls_sign(ls)
        key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, _reg_key(module_id))
        winreg.SetValueEx(key, 'start_date', 0, winreg.REG_SZ,    start_date)
        winreg.SetValueEx(key, 'used_count', 0, winreg.REG_DWORD, used_files)
        winreg.SetValueEx(key, 'sig',        0, winreg.REG_SZ,    sig)
        winreg.SetValueEx(key, 'vr',         0, winreg.REG_DWORD, 2)
        winreg.SetValueEx(key, 'ls',         0, winreg.REG_SZ,    ls)
        winreg.SetValueEx(key, 'lss',        0, winreg.REG_SZ,    lss)
        winreg.CloseKey(key)
    except Exception:
        pass


# ─────────────────────────────────────────────────────────────────────────────
# KATMAN 3 — Registry (gizli, CLSID-style)
# ─────────────────────────────────────────────────────────────────────────────

def _hidden_reg_key(module_id: str) -> str:
    safe = module_id.replace('-', '_')
    h    = hashlib.sha256(f'ccv2_{_mid()[:24]}_{safe}'.encode()).hexdigest()
    guid = f'{{{h[0:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:32]}}}'
    return rf'Software\Classes\CLSID\{guid}'


def _hidden_read(module_id: str) -> 'dict | None':
    if not _IS_WIN:
        return None
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, _hidden_reg_key(module_id))
        sd, _ = winreg.QueryValueEx(key, 'sd')
        uc, _ = winreg.QueryValueEx(key, 'uc')
        vr, _ = winreg.QueryValueEx(key, 'vr')
        try:
            sg, _ = winreg.QueryValueEx(key, 'sg')
        except OSError:
            sg = None
        try:
            ls,  _ = winreg.QueryValueEx(key, 'ls')
            lss, _ = winreg.QueryValueEx(key, 'lss')
        except OSError:
            ls = lss = None
        winreg.CloseKey(key)
        data = {'v': int(vr) if vr else 0, 'start_date': sd,
                'used_files': int(uc), 'sig': sg, 'ls': ls, 'lss': lss}
        if not _trial_verify(data):
            _log_trial_event(module_id, 'HIDDEN_INVALID',
                             f'start_date={sd} — imza geçersiz')
            return None
        data['_ls_ok'] = _ls_verify(ls, lss) if ls else None
        return data
    except Exception:
        return None


def _hidden_write(module_id: str, start_date: str, used_files: int,
                  last_seen: 'str | None' = None):
    if not _IS_WIN:
        return
    try:
        import winreg
        ls  = last_seen or _now_iso()
        sig = _trial_sign(start_date, used_files)
        lss = _ls_sign(ls)
        key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, _hidden_reg_key(module_id))
        winreg.SetValueEx(key, 'sd',  0, winreg.REG_SZ,    start_date)
        winreg.SetValueEx(key, 'uc',  0, winreg.REG_DWORD, used_files)
        winreg.SetValueEx(key, 'sg',  0, winreg.REG_SZ,    sig)
        winreg.SetValueEx(key, 'vr',  0, winreg.REG_DWORD, 2)
        winreg.SetValueEx(key, 'ls',  0, winreg.REG_SZ,    ls)
        winreg.SetValueEx(key, 'lss', 0, winreg.REG_SZ,    lss)
        winreg.CloseKey(key)
    except Exception:
        pass


# ─────────────────────────────────────────────────────────────────────────────
# Birleştirme (en kısıtlayıcı veriyi kullan)
# ─────────────────────────────────────────────────────────────────────────────

def _merge(*sources) -> 'dict | None':
    valid = [s for s in sources if s and s.get('start_date')]
    if not valid:
        return None
    earliest = min(valid, key=lambda x: x['start_date'])
    max_used = max(s.get('used_files', 0) for s in valid)
    # En büyük geçerli last_seen seçilir — rollback tespitinde en koruyucu
    max_ls = None
    for s in valid:
        ls = s.get('ls')
        if ls and s.get('_ls_ok'):   # sadece imzalı last_seen değerlerini al
            if max_ls is None or ls > max_ls:
                max_ls = ls
    return {
        'start_date': earliest['start_date'],
        'used_files': max_used,
        'last_seen':  max_ls,         # None = henüz last_seen kaydı yok
    }


# ─────────────────────────────────────────────────────────────────────────────
# Rollback sonrası kota doldurma
# Kota = max_files olduğunda trial kalıcı olarak biter —
# clock geri alınsa bile used_files HMAC ile imzalı, düzenlenemez.
# ─────────────────────────────────────────────────────────────────────────────

def _saturate_quota(module_id: str, start_date: str, detail: str):
    """Rollback tespit edildi → kota doldur → trial kalıcı biter."""
    max_f  = _cfg(module_id)['max_files']
    now_ls = _now_iso()
    _file_write(module_id, start_date, max_f, last_seen=now_ls)
    _reg_write(module_id, start_date, max_f, last_seen=now_ls)
    _hidden_write(module_id, start_date, max_f, last_seen=now_ls)
    _log_trial_event(module_id, 'CLOCK_ROLLBACK_DETECTED', detail)


# ─────────────────────────────────────────────────────────────────────────────
# Debug log
# ─────────────────────────────────────────────────────────────────────────────

def _log_trial_event(module_id: str, event: str, detail: str = ''):
    try:
        from core.crash_log import write_entry
        body = f'module  : {module_id}\nevent   : {event}'
        if detail:
            body += f'\ndetail  : {detail}'
        write_entry(f'TRIAL {event}', body)
    except Exception:
        pass


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def start_trial(module_id: str):
    """Deneme süresini başlatır — 3 konuma kaydeder."""
    sd  = datetime.now().strftime('%Y-%m-%d')
    ls  = _now_iso()
    _file_write(module_id, sd, 0, last_seen=ls)
    _reg_write(module_id, sd, 0, last_seen=ls)
    _hidden_write(module_id, sd, 0, last_seen=ls)
    _log_trial_event(module_id, 'TRIAL_STARTED',
                     f'start_date={sd} storage=file+registry+hidden')


def get_trial_status(module_id: str) -> 'tuple[bool, int, int, int]':
    """
    Returns: (aktif, kalan_gun, islenen, kalan)

    • Üç kaynaktan okur — en kısıtlayıcı değeri döner.
    • Eksik kaynak(lar) aktif kayıttan restore edilir.
    • last_seen rollback kontrolü yapılır — tespit edilirse kota doldurulur.
    • last_seen 10 dakikadan eskilse güncellenir.
    """
    cfg   = _cfg(module_id)
    max_f = cfg['max_files']
    max_d = cfg['days']

    d1 = _file_read(module_id)
    d2 = _reg_read(module_id)
    d3 = _hidden_read(module_id)
    data = _merge(d1, d2, d3)

    sources = sum(x is not None for x in (d1, d2, d3))
    if sources == 0:
        return False, 0, 0, max_f

    try:
        start       = datetime.strptime(data['start_date'], '%Y-%m-%d')
        elapsed     = (datetime.now() - start).days
        used        = int(data.get('used_files', 0))
        kalan_gun   = max(0, max_d - elapsed)
        kalan_dosya = max(0, max_f - used)
        aktif       = kalan_gun > 0 and kalan_dosya > 0

        sd       = data['start_date']
        max_ls   = data.get('last_seen')   # None = eski veri, henüz last_seen yok

        # ── Clock rollback kontrolü ───────────────────────────────────────────
        if max_ls and _check_rollback(max_ls):
            now_ts  = datetime.now().timestamp()
            ls_ts   = _iso_to_ts(max_ls)
            delta_m = int((ls_ts - now_ts) / 60)
            _saturate_quota(
                module_id, sd,
                f'now={_now_iso()} last_seen={max_ls} fark≈{delta_m} dakika geri'
            )
            return False, 0, max_f, 0

        # ── Eksik kaynakları restore et (sadece aktif trial) ──────────────────
        if aktif:
            now_ls = _now_iso()
            if d1 is None:
                _file_write(module_id, sd, used, last_seen=now_ls)
            if d2 is None:
                _reg_write(module_id, sd, used, last_seen=now_ls)
            if d3 is None:
                _hidden_write(module_id, sd, used, last_seen=now_ls)
            if sources < 3:
                _log_trial_event(module_id, 'RESTORE',
                                 f'sources={sources}/3 → eksik konumlar dolduruldu')

            # ── last_seen güncelle (throttled) ────────────────────────────────
            now_ts  = datetime.now().timestamp()
            ls_ts   = _iso_to_ts(max_ls) if max_ls else 0
            if now_ts - (ls_ts or 0) > _LS_UPDATE_INTERVAL_SEC:
                now_ls = _now_iso()
                _file_write(module_id, sd, used, last_seen=now_ls)
                _reg_write(module_id, sd, used, last_seen=now_ls)
                _hidden_write(module_id, sd, used, last_seen=now_ls)

        return aktif, kalan_gun, used, kalan_dosya
    except Exception:
        return False, 0, 0, max_f


def add_trial_usage(module_id: str, count: int):
    """Kullanım sayısını 3 konuma ekler. last_seen her zaman güncellenir."""
    _, _, used, _ = get_trial_status(module_id)
    new_used = used + count

    d1 = _file_read(module_id)
    d2 = _reg_read(module_id)
    d3 = _hidden_read(module_id)
    merged = _merge(d1, d2, d3)
    if not merged:
        return
    sd     = merged['start_date']
    now_ls = _now_iso()

    _file_write(module_id, sd, new_used, last_seen=now_ls)
    _reg_write(module_id, sd, new_used, last_seen=now_ls)
    _hidden_write(module_id, sd, new_used, last_seen=now_ls)


def is_trial_started(module_id: str) -> bool:
    """
    True döner eğer bu makinede trial başlatılmışsa (aktif VEYA süresi dolmuş).

    Katmanlar öncelik sırasıyla kontrol edilir:
      1. AppData dosyası — var ve geçerli (v=2, machine HMAC) → True
      2. Açık registry   — var, geçerli, AKTİF → dosyayı restore et, True
      3. Gizli registry  — var, geçerli (aktif OR süresi dolmuş) → True

    Gizli registry süresi dolmuş trial içeriyorsa bile True döner:
    aynı makinede yeniden deneme başlatılamaz.
    """
    # Katman 1: AppData
    d1 = _file_read(module_id)
    if d1 is not None:
        return True

    # Katman 2: açık registry — sadece aktif ise restore et
    d2 = _reg_read(module_id)
    if d2 is not None and _is_active(d2, module_id):
        _file_write(module_id, d2['start_date'], int(d2.get('used_files', 0)))
        _log_trial_event(module_id, 'RESTORE_FROM_REGISTRY',
                         f'start_date={d2["start_date"]} → dosyaya yazıldı')
        return True

    # Katman 3: gizli registry — aktif VEYA süresi dolmuş, her iki durumda True
    d3 = _hidden_read(module_id)
    if d3 is not None:
        if _is_active(d3, module_id):
            _file_write(module_id, d3['start_date'], int(d3.get('used_files', 0)))
            _reg_write(module_id, d3['start_date'], int(d3.get('used_files', 0)))
            _log_trial_event(module_id, 'RESTORE_FROM_HIDDEN',
                             f'start_date={d3["start_date"]} → file+registry yazıldı')
        else:
            _log_trial_event(module_id, 'HIDDEN_EXPIRED_BLOCK',
                             f'start_date={d3["start_date"]} — bu makinede trial tüketildi')
        return True

    _log_trial_event(module_id, 'IS_TRIAL_STARTED', 'False — hiçbir kayıt yok')
    return False
