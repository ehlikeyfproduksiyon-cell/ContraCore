# -*- coding: utf-8 -*-
"""
ContraCore — Global Tema Yöneticisi

Tüm modüller buraya register olur; toggle() hepsini birden günceller.
"""
import json
import os

_STATE_FILE = os.path.join(
    os.environ.get('APPDATA', os.path.expanduser('~')),
    'ContraCore', 'theme.json'
)

_dark: bool = False
_callbacks: list = []

# ── Açık mod renkleri (kaynak) ────────────────────────────────────────────────
_BG       = '#F2F4F7'
_CARD     = '#FFFFFF'
_NAVY     = '#0B1F3A'
_NAVY2    = '#162D4E'
_BORDER   = '#E5E7EB'
_TEXT     = '#111827'
_TEXT2    = '#6B7280'
_TEXT3    = '#9CA3AF'
_BLUE_BG  = '#EFF6FF'

# ── Koyu mod renkleri (hedef) ─────────────────────────────────────────────────
DARK_BG      = '#0F172A'
DARK_CARD    = '#1E293B'
DARK_BORDER  = '#334155'
DARK_TEXT    = '#F1F5F9'
DARK_TEXT2   = '#94A3B8'
DARK_TEXT3   = '#64748B'
DARK_BLUE_BG = '#1E3A5F'
DARK_INPUT   = '#0F1E33'


def is_dark() -> bool:
    return _dark


def load():
    global _dark
    try:
        with open(_STATE_FILE, encoding='utf-8') as f:
            _dark = json.load(f).get('dark', False)
    except Exception:
        _dark = False


def toggle():
    global _dark
    _dark = not _dark
    _save()
    _notify()


def register(callback):
    """Modül _apply_theme fonksiyonunu kaydet; anında mevcut temayı uygula."""
    if callback not in _callbacks:
        _callbacks.append(callback)
    try:
        callback()
    except Exception:
        pass


def unregister(callback):
    try:
        _callbacks.remove(callback)
    except ValueError:
        pass


def _save():
    try:
        os.makedirs(os.path.dirname(_STATE_FILE), exist_ok=True)
        with open(_STATE_FILE, 'w', encoding='utf-8') as f:
            json.dump({'dark': _dark}, f)
    except Exception:
        pass


def _notify():
    for cb in list(_callbacks):
        try:
            cb()
        except Exception:
            pass


def build_theme_map() -> list[tuple[str, str]]:
    """Açık→koyu renk eşlemesi. Her modül aynı map'i kullanır."""
    pairs = [
        (f'color:{_TEXT}',    f'color:{DARK_TEXT}'),
        (f'color:{_TEXT2}',   f'color:{DARK_TEXT2}'),
        (f'color:{_TEXT3}',   f'color:{DARK_TEXT3}'),
        (f'color:{_NAVY}',    f'color:{DARK_TEXT}'),
        (f'color:{_NAVY2}',   f'color:{DARK_TEXT2}'),
        (f'color:#15803D',    f'color:#34D399'),
        (f'color:#1A1200',    f'color:{DARK_TEXT}'),
        (f'color:#E2F8F0',    f'color:{DARK_TEXT}'),
        (f'background:{_CARD}',    f'background:{DARK_CARD}'),
        (f'background:#FFFFFF',    f'background:{DARK_CARD}'),
        (f'background:{_BG}',      f'background:{DARK_BG}'),
        (f'background:#F2F4F7',    f'background:{DARK_BG}'),
        (f'background:{_BLUE_BG}', f'background:{DARK_BLUE_BG}'),
        (f'background:#EFF6FF',    f'background:{DARK_BLUE_BG}'),
        (f'background:#FAFAFA',    f'background:{DARK_INPUT}'),
        (f'background:#F9FAFB',    f'background:{DARK_INPUT}'),
        (f'background:#F8FAFC',    f'background:{DARK_INPUT}'),
        (f'background:#F3F4F6',    f'background:{DARK_INPUT}'),
        (f'background:#FFF7ED',    f'background:{DARK_INPUT}'),
        (f'background:#FFF5F5',    f'background:{DARK_INPUT}'),
        (f'background:#F0FDF4',    f'background:{DARK_INPUT}'),
        (f'background:#F0F9FF',    f'background:{DARK_INPUT}'),
        (f'border:1px solid {_BORDER}',   f'border:1px solid {DARK_BORDER}'),
        (f'border:1.5px solid {_BORDER}', f'border:1.5px solid {DARK_BORDER}'),
        (f'border:2px solid {_BORDER}',   f'border:2px solid {DARK_BORDER}'),
    ]
    expanded = []
    for light, dark in pairs:
        expanded.append((light, dark))
        for prop in ('color:', 'background:', 'border:1px solid', 'border:1.5px solid', 'border:2px solid'):
            if light.startswith(prop):
                rest_l = light[len(prop):]
                rest_d = dark[len(prop):]
                spaced = (f'{prop} {rest_l}', f'{prop} {rest_d}')
                if spaced not in expanded:
                    expanded.append(spaced)
    return expanded


_THEME_MAP = None


def get_theme_map() -> list[tuple[str, str]]:
    global _THEME_MAP
    if _THEME_MAP is None:
        _THEME_MAP = build_theme_map()
    return _THEME_MAP


def apply_to_widget(root_widget, exclude_types=()):
    """root_widget ve tüm alt widget'larına mevcut temayı uygula."""
    from PySide6.QtWidgets import QWidget
    if root_widget is None:
        return
    theme_map = get_theme_map()
    targets = [root_widget] + list(root_widget.findChildren(QWidget))
    for w in targets:
        if exclude_types and isinstance(w, exclude_types):
            continue
        orig = w.property('_orig_ss')
        if orig is None:
            cur = w.styleSheet()
            if cur:
                w.setProperty('_orig_ss', cur)
                orig = cur
        if not orig:
            continue
        if _dark:
            new_ss = orig
            for lc, dk in theme_map:
                new_ss = new_ss.replace(lc, dk)
            w.setStyleSheet(new_ss)
        else:
            w.setStyleSheet(orig)


def make_toggle_button():
    """Standart dark/light mod toggle butonu oluştur."""
    from PySide6.QtWidgets import QPushButton
    from PySide6.QtGui import QFont
    btn = QPushButton('☀️' if _dark else '🌙')
    btn.setFixedSize(38, 38)
    btn.setFont(QFont('Segoe UI', 14))
    from PySide6.QtCore import Qt
    btn.setCursor(Qt.PointingHandCursor)
    btn.setToolTip('Koyu / Açık mod')
    btn.setStyleSheet('''
        QPushButton {
            background: rgba(255,255,255,0.08);
            border: 1px solid rgba(255,255,255,0.15);
            border-radius: 19px;
            font-size: 16px;
        }
        QPushButton:hover {
            background: rgba(255,255,255,0.18);
            border-color: rgba(255,255,255,0.35);
        }
    ''')
    return btn


load()
