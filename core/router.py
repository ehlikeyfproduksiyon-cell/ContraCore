#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ContraCore — Module Router (statik mimari)

Modüller cc_modules paketi uzerinden dogrudan import edilir.
Nuitka tarafindan derlenir — Program Files'ta kaynak kod yoktur.
"""

import sys

from PySide6.QtWidgets import QWidget, QLabel, QVBoxLayout
from PySide6.QtCore    import Qt
from PySide6.QtGui     import QFont

# Statik adapter importlari — Nuitka bunlari derler
from cc_modules.xml_fatura  import adapter as _xf_adapter
from cc_modules.compare_191 import adapter as _c191_adapter

# ── Modül Kayıt Defteri ───────────────────────────────────────────────────────

MODULE_REGISTRY = [
    {
        'id'          : 'xml-fatura',
        'label'       : 'XML Fatura',
        'icon_file'   : 'xml.png',
        'accent_color': '#F6C244',
        '_adapter'    : _xf_adapter,
    },
    {
        'id'          : 'compare-191',
        'label'       : '191 Karşılaştır',
        'icon_file'   : '191m.png',
        'accent_color': '#4DCC78',
        '_adapter'    : _c191_adapter,
    },
]


class ModuleRouter:
    """
    Modülleri talep üzerine yükler ve önbellekte tutar.
    QStackedWidget ile birlikte çalışır; index yönetimi Shell'e aittir.
    """

    def __init__(self):
        self._cache: dict[str, QWidget] = {}
        self._hosts: dict[str, object]  = {}

    # ── Public API ────────────────────────────────────────────────────────────

    def load(self, module_id: str, parent=None) -> QWidget:
        if module_id in self._cache:
            return self._cache[module_id]
        widget = self._load_module(module_id, parent)
        self._cache[module_id] = widget
        return widget

    def invalidate(self, module_id: str):
        self._cache.pop(module_id, None)
        self._hosts.pop(module_id, None)

    def registry(self) -> list[dict]:
        return MODULE_REGISTRY

    # ── İç Yükleme ───────────────────────────────────────────────────────────

    def _load_module(self, module_id: str, parent=None) -> QWidget:
        entry = next((m for m in MODULE_REGISTRY if m['id'] == module_id), None)
        if entry is None:
            return self._error_widget(f'Bilinmeyen modül: {module_id}')

        adapter = entry.get('_adapter')
        if adapter is None:
            return self._error_widget(f'{entry["label"]} adapter bulunamadı.')

        try:
            widget, host = adapter.get_embedded_widget(parent=parent)
        except Exception as exc:
            return self._error_widget(f'{entry["label"]} başlatılamadı:\n{exc}')

        if widget is None:
            ls = adapter.get_license_status()
            if ls.get('trial_active') is False and not ls.get('valid') and not ls.get('needs_activation') is True:
                return self._trial_expired_widget(entry['label'])
            return self._activation_cancelled_widget(entry['label'])

        self._hosts[module_id] = host
        return widget

    # ── Placeholder Widget'lar ────────────────────────────────────────────────

    @staticmethod
    def _error_widget(message: str) -> QWidget:
        w   = QWidget()
        lay = QVBoxLayout(w)
        lay.setAlignment(Qt.AlignCenter)
        lbl = QLabel(f'Hata: {message}')
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setFont(QFont('Segoe UI', 11))
        lbl.setStyleSheet('color: #EF4444;')
        lbl.setWordWrap(True)
        lay.addWidget(lbl)
        return w

    @staticmethod
    def _activation_cancelled_widget(label: str) -> QWidget:
        w   = QWidget()
        w.setStyleSheet('background: #F2F4F7;')
        lay = QVBoxLayout(w)
        lay.setAlignment(Qt.AlignCenter)
        lbl = QLabel(f'{label} lisansi aktif degil.\nSidebar\'dan tekrar secerek aktivasyon yapabilirsiniz.')
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setFont(QFont('Segoe UI', 11))
        lbl.setStyleSheet('color: #6B7280;')
        lbl.setWordWrap(True)
        lay.addWidget(lbl)
        return w

    @staticmethod
    def _trial_expired_widget(label: str) -> QWidget:
        w   = QWidget()
        w.setStyleSheet('background: #F2F4F7;')
        lay = QVBoxLayout(w)
        lay.setAlignment(Qt.AlignCenter)
        title = QLabel('Deneme Surumunuz Bitti')
        title.setAlignment(Qt.AlignCenter)
        title.setFont(QFont('Segoe UI', 14))
        title.setStyleSheet('color: #1F2937; font-weight: 700; background: transparent;')
        lay.addWidget(title)
        sub = QLabel(f'{label} lisansi gerekli.\nSidebar\'dan tekrar secerek lisans alabilirsiniz.')
        sub.setAlignment(Qt.AlignCenter)
        sub.setFont(QFont('Segoe UI', 11))
        sub.setStyleSheet('color: #6B7280; background: transparent;')
        sub.setWordWrap(True)
        lay.addWidget(sub)
        return w
