#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Karşıt YMM — Renk paleti ve QSS yardımcıları
"""

# ── Renk Paleti (ContraCore standart) ─────────────────────────────────────────
BG      = '#F2F4F7'
CARD    = '#FFFFFF'
NAVY    = '#0B1F3A'
NAVY2   = '#162D4E'
GREEN   = '#22C55E'
GREEN2  = '#16A34A'
RED     = '#EF4444'
RED2    = '#DC2626'
GOLD    = '#C9A46A'
BORDER  = '#E5E7EB'
TEXT    = '#111827'
TEXT2   = '#6B7280'
TEXT3   = '#9CA3AF'
BLUE    = '#3B82F6'
BLUE2   = '#2563EB'
BLUE_BG = '#EFF6FF'
ORANGE  = '#F97316'
LOG_BG  = '#0F172A'

# ── Modüle Özgü Aksent ────────────────────────────────────────────────────────
ACCENT       = '#3B82F6'   # sidebar accent
ACCENT_HOVER = '#2563EB'


def card_ss() -> str:
    return f'QFrame{{background:{CARD};border-radius:16px;border:1px solid {BORDER};}}'


def input_ss(focus_color: str = BLUE) -> str:
    return f'''
        QLineEdit {{
            background: #FAFAFA;
            border: 1.5px solid {BORDER};
            border-radius: 10px;
            padding: 0 12px;
            font-size: 13px;
            color: {TEXT};
        }}
        QLineEdit:focus {{
            border-color: {focus_color};
            background: #FFFFFF;
        }}
        QLineEdit::placeholder {{
            color: {TEXT3};
        }}
    '''


def icon_btn_ss(hover_color: str = BLUE_BG, hover_border: str = BLUE) -> str:
    return f'''
        QPushButton {{
            background: #F3F4F6;
            border: 1.5px solid {BORDER};
            border-radius: 10px;
        }}
        QPushButton:hover {{
            background: {hover_color};
            border-color: {hover_border};
        }}
        QPushButton:pressed {{
            background: #DBEAFE;
        }}
    '''


def action_btn_ss(bg: str, hover: str, text_color: str = '#FFFFFF') -> str:
    return f'''
        QPushButton {{
            background: {bg};
            color: {text_color};
            border: none;
            border-radius: 12px;
            font-size: 12px;
            font-weight: 700;
            padding: 0 18px;
        }}
        QPushButton:hover {{ background: {hover}; }}
        QPushButton:disabled {{
            background: #E5E7EB;
            color: #9CA3AF;
        }}
    '''
