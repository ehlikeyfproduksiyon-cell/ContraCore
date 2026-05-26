#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ContraCore — 191 Karşılaştır Modül Adaptörü (cc_modules statik versiyon)
Nuitka tarafından derlenir — kaynak kod Program Files'ta görünmez.
"""

import sys
import types

_MODULE_ID = 'compare-191'


def _install_context():
    """
    gui.py icindeki 'from license import ...', 'from activation import ...' ve
    'import karsilastir' cagrilarini cc_modules paketine yonlendirir.
    Inline import olduklari icin widget olusturulmadan once cagrilmasi yeterli.
    """
    from core.license import manager, trial
    from cc_modules.compare_191 import activation as _activation
    from cc_modules.compare_191 import karsilastir as _karsilastir

    shim = types.ModuleType('license')
    shim.check_license    = lambda: manager.check_module_license(_MODULE_ID)
    shim.add_trial_usage  = lambda count: trial.add_trial_usage(_MODULE_ID, count)
    shim.get_trial_status = lambda: trial.get_trial_status(_MODULE_ID)
    shim.TRIAL_MAX_FILES  = trial.get_trial_max_files(_MODULE_ID)
    sys.modules['license']    = shim
    sys.modules['activation'] = _activation
    sys.modules['karsilastir'] = _karsilastir


# ── Lisans durumu ─────────────────────────────────────────────────────────────

def get_license_status() -> dict:
    from core.license import manager, trial

    valid, _, expire = manager.check_module_license(_MODULE_ID)
    if valid:
        return {'valid': True, 'trial_active': False, 'expire': expire,
                'trial_status': None, 'needs_activation': False}

    aktif, kalan_gun, islenen, kalan = trial.get_trial_status(_MODULE_ID)
    if aktif:
        return {'valid': False, 'trial_active': True, 'expire': None,
                'trial_status': (kalan_gun, islenen, kalan), 'needs_activation': False}

    return {'valid': False, 'trial_active': False, 'expire': None,
            'trial_status': None, 'needs_activation': True}


def run_activation_dialog(parent=None) -> dict:
    from core.license.activation_dialog import LicenseManagerDialog
    from core.router import MODULE_REGISTRY

    dlg = LicenseManagerDialog(
        module_registry=MODULE_REGISTRY,
        focused_module=_MODULE_ID,
        parent=parent,
    )
    activated = False

    def _on_activated(mid):
        nonlocal activated
        if mid == _MODULE_ID:
            activated = True

    dlg.module_activated.connect(_on_activated)
    dlg.exec()
    return {'activated': activated, 'trial_started': False}


# ── Widget oluşturucu ─────────────────────────────────────────────────────────

def get_embedded_widget(parent=None):
    from core.license import manager, trial

    valid, _, expire = manager.check_module_license(_MODULE_ID)
    trial_status = None

    if not valid:
        aktif, kalan_gun, islened, kalan = trial.get_trial_status(_MODULE_ID)

        if not aktif and not trial.is_trial_started(_MODULE_ID):
            trial.start_trial(_MODULE_ID)
            aktif, kalan_gun, islened, kalan = trial.get_trial_status(_MODULE_ID)

        if aktif:
            trial_status = (kalan_gun, islened, kalan)
        else:
            return None, None

    return _build_host(expire=expire if valid else None, trial_status=trial_status)


def _build_host(expire, trial_status):
    _install_context()

    from cc_modules.compare_191 import gui as _gui

    host = _gui.MainWindow(
        expire_date=expire,
        trial_status=trial_status,
    )

    tray = getattr(host, '_tray', None)
    if tray is not None:
        tray.hide()

    central = host.centralWidget()
    central._cc_host_window = host
    return central, host
