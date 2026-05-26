#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ContraCore — License Test Helper

Test senaryolarını hızlıca oluşturur ve uygular.
Gerçek HWID ile geçerli / geçersiz / expire edilmiş lisans durumları kurar.

KULLANIM (proje kökünden çalıştırın):
    python dev_tools/license_test_helper.py --scenario clean
    python dev_tools/license_test_helper.py --scenario xml-only
    python dev_tools/license_test_helper.py --scenario both-licensed
    python dev_tools/license_test_helper.py --scenario xml-expired
    python dev_tools/license_test_helper.py --scenario c191-only
    python dev_tools/license_test_helper.py --scenario xml-trial
    python dev_tools/license_test_helper.py --scenario both-trial
    python dev_tools/license_test_helper.py --scenario invalid-hwid
    python dev_tools/license_test_helper.py --scenario tampered-json
    python dev_tools/license_test_helper.py --scenario mixed-tiers
    python dev_tools/license_test_helper.py --keygen xml-fatura 2027-12-31
    python dev_tools/license_test_helper.py --info

⚠  SADECE DEVELOPMENT/TEST ORTAMINDA KULLANIN.
"""

import os
import sys
import json
import argparse
import hashlib
import hmac
from datetime import datetime, timedelta, date
from pathlib import Path

# Windows konsolu UTF-8 zorlaması
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# ── Proje root'unu path'e ekle ────────────────────────────────────────────────
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from core.license.manager import (
    get_hwid, generate_module_key_v2, validate_v2_key, activate_module,
    save_license, load_license, _sign, _make_payload,
    _LICENSE_FILE, _LICENSE_DIR,
)

APPDATA     = os.environ.get('APPDATA', os.path.expanduser('~'))
PROGRAMDATA = os.environ.get('PROGRAMDATA', 'C:\\ProgramData')


# ── Yardımcı — reset (reset script'ini içten çağırır) ────────────────────────

def _full_reset():
    """Tüm lisans verilerini siler (reset_dev_environment.py mantığı)."""
    import subprocess
    reset_script = os.path.join(ROOT, 'dev_tools', 'reset_dev_environment.py')
    subprocess.run([sys.executable, reset_script, '--force'], check=False)


def _quick_reset():
    """Sadece unified license.json'u siler (hızlı temizlik)."""
    if os.path.exists(_LICENSE_FILE):
        os.remove(_LICENSE_FILE)
        print('  ✓ license.json silindi')
    else:
        print('  – license.json zaten yok')


# ── Senaryo oluşturucular ─────────────────────────────────────────────────────

def _write_unified(modules_cfg: dict):
    """
    Verilen modül konfigürasyonuyla license.json yazar.

    modules_cfg örneği:
        {
          'xml-fatura':  {'enabled': True,  'expire_date': date(2027,1,1), 'tier': 'pro'},
          'compare-191': {'enabled': False, 'expire_date': None,           'tier': None},
        }
    """
    hwid    = get_hwid()
    modules = {}

    for mod_id, cfg in modules_cfg.items():
        enabled     = cfg.get('enabled', False)
        expire_date = cfg.get('expire_date')
        tier        = cfg.get('tier', 'pro')
        key         = cfg.get('key', '')

        # Geçerli modüller için V2 key oluştur (yoksa)
        if enabled and expire_date and not key:
            dt  = datetime.combine(expire_date, datetime.min.time())
            key = generate_module_key_v2(hwid, mod_id, dt)

        modules[mod_id] = {
            'enabled': enabled,
            'expire' : expire_date.strftime('%Y-%m-%d') if expire_date else None,
            'tier'   : tier,
            'key'    : key,
        }

    data = {'hwid': hwid, 'modules': modules}
    save_license(data)
    return data


def _write_tampered_unified(modules_cfg: dict):
    """Geçerli JSON yazar, sonra imzasız / bozulmuş hale getirir."""
    data = _write_unified(modules_cfg)
    # JSON'u oku ve imzayı boz
    with open(_LICENSE_FILE, 'r', encoding='utf-8') as f:
        raw = json.load(f)
    raw['sig'] = 'TAMPERED0000TAMPERED'[:16]
    with open(_LICENSE_FILE, 'w', encoding='utf-8') as f:
        json.dump(raw, f, ensure_ascii=False, indent=2)


def _write_wrong_hwid_unified(modules_cfg: dict):
    """Farklı bir HWID ile imzalanmış lisans yazar."""
    fake_hwid  = 'DEAD-BEEF-CAFE-0000'
    modules    = {}
    for mod_id, cfg in modules_cfg.items():
        enabled     = cfg.get('enabled', False)
        expire_date = cfg.get('expire_date')
        tier        = cfg.get('tier', 'pro')
        key         = ''
        if enabled and expire_date:
            dt  = datetime.combine(expire_date, datetime.min.time())
            key = generate_module_key_v2(fake_hwid, mod_id, dt)
        modules[mod_id] = {
            'enabled': enabled,
            'expire' : expire_date.strftime('%Y-%m-%d') if expire_date else None,
            'tier'   : tier,
            'key'    : key,
        }
    data = {'hwid': fake_hwid, 'modules': modules}
    # İmzayı fake_hwid üzerinden hesapla (kendi içinde tutarlı ama HWID yanlış)
    payload     = _make_payload(data)
    data['sig'] = _sign(payload)
    os.makedirs(_LICENSE_DIR, exist_ok=True)
    with open(_LICENSE_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ── Senaryolar ────────────────────────────────────────────────────────────────

SCENARIOS = {}

def scenario(name, description):
    def decorator(fn):
        SCENARIOS[name] = {'fn': fn, 'desc': description}
        return fn
    return decorator


@scenario('clean', 'Tüm lisans verilerini sil — sıfır başlangıç (full reset)')
def scenario_clean():
    _full_reset()


@scenario('unified-clean', 'Sadece unified license.json sil, legacy/trial kayıtlarına dokunma')
def scenario_unified_clean():
    _quick_reset()


@scenario('xml-only', 'Unified: sadece XML Fatura lisanslı (2027-01-01), compare-191 kilitli')
def scenario_xml_only():
    _quick_reset()
    data = _write_unified({
        'xml-fatura':  {'enabled': True,  'expire_date': date(2027, 1, 1), 'tier': 'pro'},
        'compare-191': {'enabled': False, 'expire_date': None,              'tier': None},
    })
    _print_unified_result(data)


@scenario('c191-only', 'Unified: sadece Compare-191 lisanslı (2027-06-01), XML kilitli')
def scenario_c191_only():
    _quick_reset()
    data = _write_unified({
        'xml-fatura':  {'enabled': False, 'expire_date': None,             'tier': None},
        'compare-191': {'enabled': True,  'expire_date': date(2027, 6, 1), 'tier': 'pro'},
    })
    _print_unified_result(data)


@scenario('both-licensed', 'Unified: her iki modül lisanslı (XML: 2027-01-01, 191: 2027-06-01)')
def scenario_both_licensed():
    _quick_reset()
    data = _write_unified({
        'xml-fatura':  {'enabled': True, 'expire_date': date(2027, 1, 1), 'tier': 'pro'},
        'compare-191': {'enabled': True, 'expire_date': date(2027, 6, 1), 'tier': 'pro'},
    })
    _print_unified_result(data)


@scenario('xml-expired', 'Unified: XML süresi dolmuş (dün), compare-191 geçerli')
def scenario_xml_expired():
    _quick_reset()
    yesterday = date.today() - timedelta(days=2)   # grace period'dan da önce
    data = _write_unified({
        'xml-fatura':  {'enabled': True, 'expire_date': yesterday,        'tier': 'pro'},
        'compare-191': {'enabled': True, 'expire_date': date(2027, 6, 1), 'tier': 'pro'},
    })
    _print_unified_result(data)
    print('  ⚠  XML Fatura grace period (-1 gün) aşılmış → sidebar kilitli görünmeli')


@scenario('both-expired', 'Unified: her iki modül süresi dolmuş')
def scenario_both_expired():
    _quick_reset()
    expired = date.today() - timedelta(days=5)
    data = _write_unified({
        'xml-fatura':  {'enabled': True, 'expire_date': expired, 'tier': 'pro'},
        'compare-191': {'enabled': True, 'expire_date': expired, 'tier': 'pro'},
    })
    _print_unified_result(data)


@scenario('xml-trial', 'Legacy: XML trial başlat (unified yok, modül kendi trial sistemini kullanır)')
def scenario_xml_trial():
    _quick_reset()
    import importlib.util as _ilu
    xf_lic_path = os.path.join(ROOT, 'modules', 'xml-fatura', 'license.py')
    spec        = _ilu.spec_from_file_location('_xf_lic_reset', xf_lic_path)
    mod         = _ilu.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.start_trial()
    print('  ✓ XML Fatura trial başlatıldı (30 gün / 5000 dosya)')
    print('  ℹ  Unified license yok → modül kendi trial sistemine düşecek')


@scenario('both-trial', 'Legacy: her iki modül için trial başlat (unified yok)')
def scenario_both_trial():
    _quick_reset()
    import importlib.util as _ilu

    for mod_id, rel_path in [
        ('xml-fatura',  'modules/xml-fatura/license.py'),
        ('compare-191', 'modules/compare-191/license.py'),
    ]:
        lic_path = os.path.join(ROOT, rel_path)
        spec     = _ilu.spec_from_file_location(f'_lic_{mod_id}', lic_path)
        mod      = _ilu.module_from_spec(spec)
        spec.loader.exec_module(mod)
        mod.start_trial()
        aktif, kalan, islenen, kalan_d = mod.get_trial_status()
        print(f'  ✓ {mod_id}: trial başlatıldı — {kalan} gün kaldı')

    print('  ℹ  Unified license yok → modüller kendi trial sistemlerine düşecek')


@scenario('invalid-hwid', 'Unified: farklı HWID ile imzalanmış lisans (doğrulama başarısız olmalı)')
def scenario_invalid_hwid():
    _quick_reset()
    _write_wrong_hwid_unified({
        'xml-fatura':  {'enabled': True, 'expire_date': date(2027, 1, 1), 'tier': 'pro'},
        'compare-191': {'enabled': True, 'expire_date': date(2027, 6, 1), 'tier': 'pro'},
    })
    print('  ✓ Yanlış HWID ile imzalanmış license.json yazıldı')
    print('  ✓ load_license() None dönmeli → tüm modüller legacy path\'e düşmeli')
    # Doğrulama
    result = load_license()
    status = '✅ Beklenen davranış (None döndü)' if result is None else '✗ HATA: None beklendi ama veri döndü!'
    print(f'  Kontrol: {status}')


@scenario('tampered-json', 'Unified: imzası bozulmuş license.json (manipüle edilmiş gibi)')
def scenario_tampered_json():
    _quick_reset()
    _write_tampered_unified({
        'xml-fatura':  {'enabled': True, 'expire_date': date(2027, 1, 1), 'tier': 'pro'},
        'compare-191': {'enabled': True, 'expire_date': date(2027, 6, 1), 'tier': 'pro'},
    })
    print('  ✓ Bozulmuş imzalı license.json yazıldı')
    print('  ✓ load_license() None dönmeli → signature invalid')
    result = load_license()
    status = '✅ Beklenen davranış (None döndü)' if result is None else '✗ HATA: None beklendi ama veri döndü!'
    print(f'  Kontrol: {status}')


@scenario('mixed-tiers', 'Unified: XML=enterprise, 191=basic (tier alanı testi)')
def scenario_mixed_tiers():
    _quick_reset()
    data = _write_unified({
        'xml-fatura':  {'enabled': True, 'expire_date': date(2027, 1, 1), 'tier': 'enterprise'},
        'compare-191': {'enabled': True, 'expire_date': date(2027, 6, 1), 'tier': 'basic'},
    })
    _print_unified_result(data)


@scenario('grace-period', 'Unified: tam grace period sınırında (bugün expire + 0 gün = doldu, +1 = geçerli)')
def scenario_grace_period():
    _quick_reset()
    # Bugün expire: grace_days=1 ile yarın kadar geçerli
    today = date.today()
    data  = _write_unified({
        'xml-fatura':  {'enabled': True, 'expire_date': today, 'tier': 'pro'},
        'compare-191': {'enabled': True, 'expire_date': today, 'tier': 'pro'},
    })
    _print_unified_result(data)
    print(f'  ℹ  Expire: bugün ({today}) — grace_days=1 ile yarına kadar geçerli olmalı')


# ── Yardımcı çıktı ────────────────────────────────────────────────────────────

def _print_unified_result(data: dict):
    hwid = data.get('hwid', '?')
    print(f'\n  Unified License Yazıldı')
    print(f'  HWID    : {hwid}')
    print(f'  Dosya   : {_LICENSE_FILE}')
    for mod_id, m in data.get('modules', {}).items():
        enabled = '✅' if m.get('enabled') else '🔒'
        expire  = m.get('expire', '-') or '-'
        tier    = m.get('tier', '-') or '-'
        print(f'  {enabled} {mod_id:<15} expire={expire}  tier={tier}')
    print()


# ── Key üretici ───────────────────────────────────────────────────────────────

def keygen(module_id: str, expire_str: str):
    """Bu makine için belirtilen modül ve tarihe ait lisans anahtarı üretir."""
    try:
        expire = datetime.strptime(expire_str, '%Y-%m-%d')
    except ValueError:
        print(f'  ✗ Hatalı tarih formatı: {expire_str}  (beklenen: YYYY-MM-DD)\n')
        return

    hwid = get_hwid()
    key  = generate_module_key_v2(hwid, module_id, expire)

    print(f'\n  ─── V2 Key Generator ────────────────────────────────')
    print(f'  Modül   : {module_id}')
    print(f'  HWID    : {hwid}')
    print(f'  Expire  : {expire.strftime("%d.%m.%Y")}')
    print(f'  Anahtar : {key}')
    print(f'  ─────────────────────────────────────────────────────\n')


# ── Bilgi ─────────────────────────────────────────────────────────────────────

def show_info():
    print('\n  ═══════════════════════════════════════════════════')
    print('  ContraCore — License System Info')
    print('  ═══════════════════════════════════════════════════')
    print(f'\n  Bu Makine HWID : {get_hwid()}')
    print(f'\n  Unified License Dosyası:')
    print(f'    {_LICENSE_FILE}')

    data = load_license()
    if data:
        print('    Durum: ✅ GEÇERLİ')
        for mod_id, m in data.get('modules', {}).items():
            status = '✅ Aktif' if m.get('enabled') else '🔒 Kilitli'
            print(f'    • {mod_id}: {status}, expire={m.get("expire","?")}, tier={m.get("tier","?")}')
    else:
        print('    Durum: ⬜ YOK veya GEÇERSİZ')

    print(f'\n  Legacy Storage Lokasyonları:')
    locs = [
        ('XML Fatura lisans ',  os.path.join(APPDATA, 'XMLFaturaOtomasyonu', 'license.key')),
        ('XML Fatura trial  ',  os.path.join(APPDATA, 'XMLFaturaOtomasyonu', 'trial.json')),
        ('XML Fatura hidden ',  os.path.join(PROGRAMDATA, '.xmlfatura', 't.dat')),
        ('191 lisans        ',  os.path.join(APPDATA, 'MuavinKarsilastirma', 'license.key')),
        ('191 trial         ',  os.path.join(APPDATA, 'MuavinKarsilastirma', 'trial.json')),
        ('191 hidden        ',  os.path.join(PROGRAMDATA, '.muavinkar', 't.dat')),
    ]
    for desc, path in locs:
        exists = '✅' if os.path.isfile(path) else '⬜'
        print(f'    {exists} {desc}: {path}')

    print(f'\n  Registry Kayıtları:')
    reg_locs = [
        ('XML Fatura', r'Software\XMLFaturaOtomasyonu\Trial'),
        ('191 Karşıl.', r'Software\MuavinKarsilastirma\Trial'),
    ]
    for desc, rpath in reg_locs:
        try:
            import winreg
            k = winreg.OpenKey(winreg.HKEY_CURRENT_USER, rpath)
            winreg.CloseKey(k)
            status = '✅ VAR'
        except Exception:
            status = '⬜ YOK'
        print(f'    {status} {desc}: HKCU\\{rpath}')

    print()


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description='ContraCore — License Test Helper',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='\nMevcut senaryolar:\n' + '\n'.join(
            f'  {name:<20} {cfg["desc"]}' for name, cfg in SCENARIOS.items()
        )
    )
    parser.add_argument(
        '--scenario', '-s',
        choices=list(SCENARIOS.keys()),
        metavar='SENARYO',
        help='Uygulanacak test senaryosu'
    )
    parser.add_argument(
        '--keygen', '-k',
        nargs=2,
        metavar=('MODULE_ID', 'YYYY-MM-DD'),
        help='Bu makine için lisans anahtarı üret (örn: xml-fatura 2027-12-31)'
    )
    parser.add_argument(
        '--info', '-i',
        action='store_true',
        help='Mevcut lisans durumunu göster'
    )
    parser.add_argument(
        '--list', '-l',
        action='store_true',
        help='Kullanılabilir senaryoları listele'
    )
    args = parser.parse_args()

    print()

    if args.list:
        print('  Kullanılabilir test senaryoları:\n')
        for name, cfg in SCENARIOS.items():
            print(f'  {"--scenario " + name:<35} {cfg["desc"]}')
        print()
        return

    if args.info:
        show_info()
        return

    if args.keygen:
        keygen(args.keygen[0], args.keygen[1])
        return

    if args.scenario:
        cfg = SCENARIOS[args.scenario]
        print(f'  Senaryo : {args.scenario}')
        print(f'  Açıklama: {cfg["desc"]}\n')
        cfg['fn']()
        return

    # Argüman yoksa interaktif menü
    print('  ContraCore License Test Helper\n')
    print('  Kullanılabilir senaryolar:\n')
    names = list(SCENARIOS.keys())
    for i, name in enumerate(names, 1):
        print(f'  [{i:2d}] {name:<22} {SCENARIOS[name]["desc"]}')
    print(f'  [ k] Lisans anahtarı üret')
    print(f'  [ i] Mevcut durum bilgisi')
    print(f'  [ q] Çıkış\n')

    choice = input('  Seçim: ').strip().lower()

    if choice == 'q':
        return
    if choice == 'i':
        show_info()
        return
    if choice == 'k':
        mod = input('  Modül ID (xml-fatura / compare-191): ').strip()
        exp = input('  Expire tarihi (YYYY-MM-DD): ').strip()
        keygen(mod, exp)
        return

    try:
        idx = int(choice) - 1
        if 0 <= idx < len(names):
            name = names[idx]
            cfg  = SCENARIOS[name]
            print(f'\n  Senaryo : {name}')
            print(f'  Açıklama: {cfg["desc"]}\n')
            cfg['fn']()
        else:
            print('  Geçersiz seçim.\n')
    except ValueError:
        print('  Geçersiz seçim.\n')


if __name__ == '__main__':
    main()
