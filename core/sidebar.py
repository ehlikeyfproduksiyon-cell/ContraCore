#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ContraCore — Sidebar Widget v2

Collapsible animated sidebar with premium visual design.
  • 260 px expanded  ↔  64 px collapsed (300 ms ease-in-out animation)
  • 3-state module items: licensed / trial / locked
  • Glow effect on active module
  • Logo: ContraCoreTextBeyaz2.png
"""

import os

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QFrame, QPushButton, QGraphicsDropShadowEffect,
    QSizePolicy,
)
from PySide6.QtCore import (
    Qt, Signal, QPropertyAnimation, QEasingCurve, QSize,
)
from PySide6.QtGui import (
    QIcon, QPixmap, QFont, QColor, QPainter, QLinearGradient,
    QPainterPath, QBrush, QFontMetrics,
)

# ── Renkler ───────────────────────────────────────────────────────────────────
NAVY       = '#0B1F3A'
NAVY2      = '#162D4E'
NAVY3      = '#1E3660'
GOLD       = '#C9A46A'
GOLD_LIGHT = '#E4C285'
AMBER      = '#F6AD55'
AMBER_DIM  = '#92400E'
AMBER_TXT  = '#FDE68A'
LOCKED_TXT = '#4A5568'
WHITE      = '#FFFFFF'
WHITE_DIM  = '#A0AEC0'
NAVY4      = '#253F6A'
BORDER     = '#1E3660'
GREEN      = '#4DCC78'

try:
    from core.version import APP_VERSION as _APP_VERSION
    VERSION = f'v{_APP_VERSION}'
except Exception:
    VERSION = 'v1.0.0'
EXPANDED_W   = 265
COLLAPSED_W  = 64
ANIM_MS      = 280

from core import _icons as _ic


# ── Yardımcılar ───────────────────────────────────────────────────────────────

def _icon_pix(name: str, size: int) -> QPixmap:
    return _ic.load(name).scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)


def _gradient_text_pix(text: str, family: str, size: int,
                        bold: bool, top: str, bottom: str) -> QPixmap:
    """Top→bottom gradient renkli metin pixmap'i oluşturur."""
    font = QFont(family, size, QFont.Bold if bold else QFont.Normal)
    fm   = QFontMetrics(font)
    w    = fm.horizontalAdvance(text) + 6
    h    = fm.height() + 6
    pix  = QPixmap(w, h)
    pix.fill(Qt.transparent)
    p    = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)
    path = QPainterPath()
    path.addText(3, fm.ascent() + 3, font, text)
    grad = QLinearGradient(0, 3, 0, h - 3)
    grad.setColorAt(0, QColor(top))
    grad.setColorAt(1, QColor(bottom))
    p.setBrush(QBrush(grad))
    p.setPen(Qt.NoPen)
    p.drawPath(path)
    p.end()
    return pix


# ── Tek Modül Öğesi ───────────────────────────────────────────────────────────

class ModuleItem(QFrame):
    """
    Sidebar modül satırı. Genişlemiş ve daraltılmış görünüm destekler.

    state : 'licensed' | 'trial' | 'locked'

    module_states ek alanları:
        expire      : datetime | None
        days_left   : int | None
        trial_days  : int | None
        has_update  : bool
    """
    clicked      = Signal(str)
    lock_clicked = Signal(str)

    ITEM_H = 76   # iki satır için yükseklik

    def __init__(self, module_id: str, label: str, icon_file: str,
                 state: str = 'licensed', tooltip: str = '',
                 days_left: int | None = None,
                 trial_days: int | None = None,
                 has_update: bool = False,
                 accent_color: str = ''):
        super().__init__()
        self.module_id    = module_id
        self.label_text   = label
        self.state        = state
        self._active      = False
        self._days_left   = days_left
        self._trial_days  = trial_days
        self._has_update  = has_update
        self._expanded    = True
        self._accent      = accent_color or GOLD

        self.setObjectName('moduleItem')
        self.setFrameShape(QFrame.NoFrame)
        self.setFixedHeight(self.ITEM_H)
        self._update_cursor()
        if tooltip:
            self.setToolTip(tooltip)

        # ── Dış layout: iç frame'i çevreler (hover/glow için padding) ─────────
        outer = QHBoxLayout(self)
        outer.setContentsMargins(6, 4, 6, 4)
        outer.setSpacing(0)

        # ── İç frame: glow + yuvarlak köşeler ─────────────────────────────────
        self._inner = QFrame()
        self._inner.setObjectName('moduleInner')
        self._inner.setFrameShape(QFrame.NoFrame)
        inner_lay = QHBoxLayout(self._inner)
        inner_lay.setContentsMargins(8, 8, 8, 8)
        inner_lay.setSpacing(10)

        # Sol aktif çubuk
        self._indicator = QFrame()
        self._indicator.setFixedSize(3, 36)
        self._indicator.setFrameShape(QFrame.NoFrame)
        inner_lay.addWidget(self._indicator)

        # İkon
        self._ico_lbl = QLabel()
        self._ico_lbl.setFixedSize(32, 32)
        self._ico_lbl.setAlignment(Qt.AlignCenter)
        self._ico_lbl.setStyleSheet('background:transparent;')
        pix = _icon_pix(icon_file, 32)
        if not pix.isNull():
            self._ico_lbl.setPixmap(pix)
        inner_lay.addWidget(self._ico_lbl)

        # Metin alanı (genişletilmiş modda görünür)
        self._text_area = QWidget()
        self._text_area.setStyleSheet('background:transparent;')
        text_lay = QVBoxLayout(self._text_area)
        text_lay.setContentsMargins(0, 0, 0, 0)
        text_lay.setSpacing(2)

        self._name_lbl = QLabel(label)
        self._name_lbl.setFont(QFont('Segoe UI', 11, QFont.Medium))
        self._name_lbl.setStyleSheet('background:transparent;')
        text_lay.addWidget(self._name_lbl)

        self._info_lbl = QLabel()
        self._info_lbl.setFont(QFont('Segoe UI', 9))
        self._info_lbl.setStyleSheet('background:transparent;')
        self._refresh_info()
        text_lay.addWidget(self._info_lbl)

        inner_lay.addWidget(self._text_area, 1)

        # TRIAL badge
        self._trial_badge = QLabel('TRIAL')
        self._trial_badge.setFont(QFont('Segoe UI', 7, QFont.Bold))
        self._trial_badge.setAlignment(Qt.AlignCenter)
        self._trial_badge.setContentsMargins(3, 1, 3, 1)
        self._trial_badge.setSizePolicy(
            self._trial_badge.sizePolicy().horizontalPolicy(),
            self._trial_badge.sizePolicy().verticalPolicy(),
        )
        self._trial_badge.setFixedHeight(14)
        self._trial_badge.setStyleSheet(
            'background:#ffcc00; color:#1a1a1a;'
            'border-radius:2px;'
        )
        self._trial_badge.setVisible(state == 'trial')
        inner_lay.addWidget(self._trial_badge)

        # Sağ ikon (license / new / lock)
        self._right_lbl = QLabel()
        self._right_lbl.setFixedSize(20, 20)
        self._right_lbl.setAlignment(Qt.AlignCenter)
        self._right_lbl.setStyleSheet('background:transparent;')
        self._refresh_right_icon()
        inner_lay.addWidget(self._right_lbl)

        outer.addWidget(self._inner)
        self._apply_style()

    # ── Info & sağ ikon ───────────────────────────────────────────────────────

    def _refresh_info(self):
        if self.state == 'licensed' and self._days_left is not None:
            self._info_lbl.setText(f'{self._days_left} gün kaldı')
            self._info_lbl.setStyleSheet(f'color:{GOLD}; background:transparent;')
        elif self.state == 'trial' and self._trial_days is not None:
            self._info_lbl.setText(f'⏳ {self._trial_days} Gün')
            self._info_lbl.setStyleSheet(f'color:{AMBER}; background:transparent;')
        elif self.state == 'locked':
            self._info_lbl.setText('Lisans Gerekli')
            self._info_lbl.setStyleSheet(f'color:{LOCKED_TXT}; background:transparent;')
        else:
            self._info_lbl.setText('')

    def _refresh_right_icon(self):
        self._right_lbl.setPixmap(QPixmap())
        self._right_lbl.setText('')

        def _try(names, size=18):
            for n in names:
                p = _icon_pix(n, size)
                if not p.isNull():
                    return p
            return QPixmap()

        if self._has_update:
            pix = _try(['new.png', 'update.png'])
            if not pix.isNull():
                self._right_lbl.setPixmap(pix)
            else:
                self._right_lbl.setText('🆕')
                self._right_lbl.setStyleSheet(f'color:{GOLD}; background:transparent; font-size:12px;')
            return

        if self.state == 'licensed':
            pix = _try(['license.png', 'check.png'])
            if not pix.isNull():
                self._right_lbl.setPixmap(pix)
            else:
                self._right_lbl.setText('🛡')
                self._right_lbl.setStyleSheet(f'color:{GOLD}; background:transparent; font-size:14px;')
        elif self.state == 'locked':
            pix = _try(['lock.png', 'warning.png'])
            if not pix.isNull():
                self._right_lbl.setPixmap(pix)
            else:
                self._right_lbl.setText('🔒')
                self._right_lbl.setStyleSheet(f'color:{LOCKED_TXT}; background:transparent; font-size:12px;')
        else:
            self._right_lbl.setText('')

    # ── State & collapse ──────────────────────────────────────────────────────

    def set_state(self, state: str, tooltip: str = '',
                  days_left: int | None = None,
                  trial_days: int | None = None,
                  has_update: bool = False):
        self.state       = state
        self._days_left  = days_left
        self._trial_days = trial_days
        self._has_update = has_update
        self.setToolTip(tooltip)
        self._update_cursor()
        self._refresh_info()
        self._refresh_right_icon()
        self._apply_style()
        self._trial_badge.setVisible(state == 'trial' and self._expanded)

    def set_active(self, active: bool):
        self._active = active
        self._apply_style()

    def set_expanded(self, expanded: bool):
        """Collapse/expand geçişinde metin alanlarını göster/gizle."""
        self._expanded = expanded
        self._text_area.setVisible(expanded)
        self._right_lbl.setVisible(expanded)
        self._indicator.setVisible(expanded)
        self._trial_badge.setVisible(expanded and self.state == 'trial')
        # Collapsed modda: iç layout marginleri ikonu ortalar
        inner_lay = self._inner.layout()
        if expanded:
            inner_lay.setContentsMargins(8, 8, 8, 8)
        else:
            # 64px outer - 2*6 margin = 52px inner, icon 32px → 10px each side
            inner_lay.setContentsMargins(10, 10, 10, 10)

    def _update_cursor(self):
        self.setCursor(Qt.ForbiddenCursor if self.state == 'locked' else Qt.PointingHandCursor)

    # ── Görsel uygulama ───────────────────────────────────────────────────────

    def _apply_style(self):
        if self.state == 'locked':
            self._apply_locked()
        elif self.state == 'trial':
            self._apply_trial()
        else:
            self._apply_licensed()

    def _glow(self, color: str, radius: int = 16):
        eff = QGraphicsDropShadowEffect()
        eff.setBlurRadius(radius)
        eff.setColor(QColor(color))
        eff.setOffset(0, 0)
        self._inner.setGraphicsEffect(eff)

    def _no_glow(self):
        self._inner.setGraphicsEffect(None)

    def _apply_locked(self):
        self._no_glow()
        self._inner.setStyleSheet('QFrame#moduleInner { background:transparent; border-radius:10px; }')
        self._indicator.setStyleSheet(f'background:{NAVY};border-radius:1px;')
        self._name_lbl.setStyleSheet(f'color:{LOCKED_TXT}; background:transparent;')

    def _apply_trial(self):
        if self._active:
            self._glow(self._accent, 18)
            accent_t = self._accent + '55'   # ~33% opaque transparan stop
            self._inner.setStyleSheet(f'''
                QFrame#moduleInner {{
                    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                        stop:0 {accent_t}, stop:0.6 {NAVY2}, stop:1 {NAVY2});
                    border-radius: 10px;
                    border: 1px solid {self._accent};
                }}
            ''')
            self._indicator.setStyleSheet(f'background:{self._accent};border-radius:1px;')
            self._name_lbl.setStyleSheet(f'color:{WHITE}; font-weight:600; background:transparent;')
        else:
            self._no_glow()
            self._inner.setStyleSheet('QFrame#moduleInner { background:transparent; border-radius:10px; }')
            self._indicator.setStyleSheet(f'background:{NAVY};border-radius:1px;')
            self._name_lbl.setStyleSheet(f'color:{AMBER}; background:transparent;')

    def _apply_licensed(self):
        if self._active:
            self._glow(self._accent, 20)
            accent_t = self._accent + '55'   # ~33% opaque transparan stop
            self._inner.setStyleSheet(f'''
                QFrame#moduleInner {{
                    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                        stop:0 {accent_t}, stop:0.6 {NAVY2}, stop:1 {NAVY2});
                    border-radius: 10px;
                    border: 1px solid {self._accent};
                }}
            ''')
            self._indicator.setStyleSheet(f'background:{self._accent};border-radius:1px;')
            self._name_lbl.setStyleSheet(f'color:{WHITE}; font-weight:600; background:transparent;')
        else:
            self._no_glow()
            self._inner.setStyleSheet('QFrame#moduleInner { background:transparent; border-radius:10px; }')
            self._indicator.setStyleSheet(f'background:{NAVY};border-radius:1px;')
            self._name_lbl.setStyleSheet(f'color:{WHITE_DIM}; background:transparent;')

    # ── Hover ─────────────────────────────────────────────────────────────────

    def enterEvent(self, event):
        if not self._active:
            self._inner.setStyleSheet(f'''
                QFrame#moduleInner {{
                    background:{NAVY2}; border-radius:10px;
                    border: 1px solid {BORDER};
                }}
            ''')
            self._name_lbl.setStyleSheet(f'color:{WHITE}; background:transparent;')
        super().enterEvent(event)

    def leaveEvent(self, event):
        if not self._active:
            self._apply_style()
        super().leaveEvent(event)

    # ── Tıklama ───────────────────────────────────────────────────────────────

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            if self.state == 'locked':
                self.lock_clicked.emit(self.module_id)
            else:
                self.clicked.emit(self.module_id)
        super().mousePressEvent(event)

    # ── Geriye dönük uyumluluk ────────────────────────────────────────────────

    @property
    def locked(self) -> bool:
        return self.state == 'locked'

    @locked.setter
    def locked(self, value: bool):
        self.state = 'locked' if value else 'licensed'
        self._update_cursor()
        self._apply_style()


# ── Yardımcı widget'lar ───────────────────────────────────────────────────────

class _Divider(QFrame):
    def __init__(self):
        super().__init__()
        self.setFixedHeight(1)
        self.setFrameShape(QFrame.NoFrame)
        self.setStyleSheet(f'background:{BORDER};')


# ── Ana Sidebar ───────────────────────────────────────────────────────────────

class Sidebar(QFrame):
    """
    ContraCore ana sidebar.

    Sinyaller:
        module_selected(module_id)
        activation_requested(module_id)  — '' = footer butonu

    module_states formatı:
        {
          module_id: {
            'state'     : 'licensed'|'trial'|'locked',
            'tooltip'   : str,
            'expire'    : datetime|None,
            'days_left' : int|None,
            'trial_days': int|None,
            'has_update': bool,
          }
        }
    """
    module_selected      = Signal(str)
    activation_requested = Signal(str)
    update_clicked       = Signal()

    def __init__(self, modules: list[dict],
                 module_states: 'dict[str, dict] | None' = None,
                 locked_ids:   'set[str] | None'         = None,
                 lock_reasons: 'dict[str, str] | None'   = None):
        super().__init__()
        self._items     : dict[str, ModuleItem] = {}
        self._active_id : str | None            = None
        self._collapsed  = False

        if module_states is None:
            module_states = _legacy_to_states(modules, locked_ids, lock_reasons)
        self._module_states = module_states

        self.setFrameShape(QFrame.NoFrame)
        self.setStyleSheet(f'QFrame {{ background:{NAVY}; }}')
        self.setFixedWidth(EXPANDED_W)

        # ── Animasyon ─────────────────────────────────────────────────────────
        self._anim = QPropertyAnimation(self, b'maximumWidth')
        self._anim.setDuration(ANIM_MS)
        self._anim.setEasingCurve(QEasingCurve.InOutCubic)
        self._anim_min = QPropertyAnimation(self, b'minimumWidth')
        self._anim_min.setDuration(ANIM_MS)
        self._anim_min.setEasingCurve(QEasingCurve.InOutCubic)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._build_logo())
        root.addWidget(_Divider())
        root.addSpacing(8)

        for entry in modules:
            mid  = entry['id']
            info = module_states.get(mid, {})
            item = ModuleItem(
                module_id    = mid,
                label        = entry['label'],
                icon_file    = entry['icon_file'],
                state        = info.get('state', 'locked'),
                tooltip      = info.get('tooltip', ''),
                days_left    = info.get('days_left'),
                trial_days   = info.get('trial_days'),
                has_update   = info.get('has_update', False),
                accent_color = entry.get('accent_color', ''),
            )
            item.clicked.connect(self._on_item_clicked)
            item.lock_clicked.connect(self._on_lock_clicked)
            self._items[mid] = item
            root.addWidget(item)

        root.addSpacing(8)
        root.addWidget(_Divider())

        spacer = QFrame()
        spacer.setFrameShape(QFrame.NoFrame)
        spacer.setStyleSheet(f'background:{NAVY};')
        root.addWidget(spacer, 1)

        root.addWidget(_Divider())
        root.addWidget(self._build_footer())

    # ── Logo Bölümü ───────────────────────────────────────────────────────────

    def _build_logo(self) -> QFrame:
        self._logo_frame = QFrame()
        self._logo_frame.setFrameShape(QFrame.NoFrame)
        self._logo_frame.setFixedHeight(80)
        self._logo_frame.setStyleSheet(f'background:{NAVY};')

        lay = QHBoxLayout(self._logo_frame)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        # Geniş logo (expanded)
        self._logo_big = QLabel()
        self._logo_big.setAlignment(Qt.AlignCenter)
        self._logo_big.setStyleSheet('background:transparent;')
        big_pix = _ic.load('sidebarlogo.png')
        if not big_pix.isNull():
            target_w = int(EXPANDED_W * 0.74)
            scaled   = big_pix.scaledToWidth(target_w, Qt.SmoothTransformation)
            self._logo_big.setPixmap(scaled)
        else:
            self._logo_big.setText('ContraCore')
            self._logo_big.setFont(QFont('Segoe UI', 13, QFont.Bold))
            self._logo_big.setStyleSheet(f'color:{WHITE}; background:transparent;')
        lay.addWidget(self._logo_big, 1)

        # Küçük logo (collapsed)
        self._logo_small = QLabel()
        self._logo_small.setAlignment(Qt.AlignCenter)
        self._logo_small.setFixedSize(COLLAPSED_W, 80)
        self._logo_small.setStyleSheet('background:transparent;')
        sm_pix  = _ic.load('contralogoo.png').scaled(36, 36, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        if not sm_pix.isNull():
            self._logo_small.setPixmap(sm_pix)
        else:
            self._logo_small.setText('CC')
            self._logo_small.setFont(QFont('Segoe UI', 10, QFont.Bold))
            self._logo_small.setStyleSheet(f'color:{GOLD}; background:transparent;')
        self._logo_small.setVisible(False)
        lay.addWidget(self._logo_small)

        # Toggle tab — sağ kenara gömülü ince şerit
        self._toggle_btn = QPushButton()
        self._toggle_btn.setFixedSize(14, 48)
        self._toggle_btn.setCursor(Qt.PointingHandCursor)
        self._toggle_btn.setToolTip('Sidebar')
        self._toggle_btn.setStyleSheet(f'''
            QPushButton {{
                background:{NAVY3};
                border:none;
                border-top-left-radius: 0px;
                border-bottom-left-radius: 0px;
                border-top-right-radius: 6px;
                border-bottom-right-radius: 6px;
            }}
            QPushButton:hover {{
                background:{NAVY4};
            }}
        ''')
        # Chevron ikonunu QPainter ile çiz
        self._toggle_btn.clicked.connect(self._toggle_collapse)
        self._toggle_btn.paintEvent = self._paint_toggle
        lay.addWidget(self._toggle_btn, 0, Qt.AlignVCenter)

        return self._logo_frame

    def _paint_toggle(self, event):
        """Toggle butonunu özel çizer — sağa/sola bakan ince chevron."""
        from PySide6.QtGui import QPen
        btn = self._toggle_btn
        p   = QPainter(btn)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(btn.rect(), QColor(NAVY3 if not btn.underMouse() else NAVY4))
        # Yuvarlak köşeler
        from PySide6.QtGui import QPainterPath as _PP
        path = _PP()
        r = btn.rect()
        path.moveTo(r.left(), r.top())
        path.lineTo(r.right() - 5, r.top())
        path.quadTo(r.right(), r.top(), r.right(), r.top() + 5)
        path.lineTo(r.right(), r.bottom() - 5)
        path.quadTo(r.right(), r.bottom(), r.right() - 5, r.bottom())
        path.lineTo(r.left(), r.bottom())
        path.closeSubpath()
        p.fillPath(path, QColor(NAVY3 if not btn.underMouse() else NAVY4))
        # Chevron
        cx, cy = r.width() // 2, r.height() // 2
        pen = QPen(QColor(WHITE_DIM), 1.5, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        p.setPen(pen)
        if self._collapsed:
            # ▶ sağa bakan
            p.drawLine(cx - 2, cy - 5, cx + 2, cy)
            p.drawLine(cx + 2, cy, cx - 2, cy + 5)
        else:
            # ◀ sola bakan
            p.drawLine(cx + 2, cy - 5, cx - 2, cy)
            p.drawLine(cx - 2, cy, cx + 2, cy + 5)
        p.end()

    # ── Footer ────────────────────────────────────────────────────────────────

    def _build_footer(self) -> QFrame:
        self._footer_frame = QFrame()
        self._footer_frame.setFrameShape(QFrame.NoFrame)
        self._footer_frame.setFixedHeight(88)
        self._footer_frame.setStyleSheet(f'background:{NAVY};')

        # Expanded footer
        self._footer_expanded = QFrame()
        self._footer_expanded.setFrameShape(QFrame.NoFrame)
        self._footer_expanded.setStyleSheet('background:transparent;')
        exp_lay = QVBoxLayout(self._footer_expanded)
        exp_lay.setContentsMargins(12, 10, 12, 10)
        exp_lay.setSpacing(6)

        # Güncelleme butonu — başlangıçta gizli, set_app_update() ile gösterilir
        self._update_btn = QPushButton('↑  Güncelleme Mevcut')
        self._update_btn.setFont(QFont('Segoe UI', 9, QFont.Bold))
        self._update_btn.setFixedHeight(30)
        self._update_btn.setCursor(Qt.PointingHandCursor)
        self._update_btn.setStyleSheet('''
            QPushButton {
                background: #0970fc;
                color: #ffffff;
                border: none; border-radius: 6px; font-weight: 700;
            }
            QPushButton:hover { background: #1a7ffd; }
            QPushButton:pressed { background: #0558cc; }
        ''')
        self._update_btn.clicked.connect(self._on_update_btn_clicked)
        self._update_btn.setVisible(False)
        exp_lay.addWidget(self._update_btn)

        self._lic_btn = QPushButton('🔑 Lisans Yönetimi')
        self._lic_btn.setFont(QFont('Segoe UI', 9, QFont.Bold))
        self._lic_btn.setFixedHeight(32)
        self._lic_btn.setCursor(Qt.PointingHandCursor)
        self._lic_btn.setStyleSheet('''
            QPushButton {
                background: #ffcc00;
                color: #1a1a2e;
                border: none;
                border-radius: 8px;
                font-weight: 700;
                letter-spacing: 0.3px;
            }
            QPushButton:hover {
                background: #ffd633;
            }
        ''')
        self._lic_btn.clicked.connect(lambda: self.activation_requested.emit(''))
        exp_lay.addWidget(self._lic_btn)

        ver = QLabel(f'ContraCORE  ·  {VERSION}')
        ver.setFont(QFont('Segoe UI', 8))
        ver.setStyleSheet(f'color:{WHITE_DIM}; background:transparent;')
        exp_lay.addWidget(ver)

        # Collapsed footer (sadece anahtar ikonu)
        self._footer_collapsed = QFrame()
        self._footer_collapsed.setFrameShape(QFrame.NoFrame)
        self._footer_collapsed.setStyleSheet('background:transparent;')
        col_lay = QVBoxLayout(self._footer_collapsed)
        col_lay.setContentsMargins(0, 10, 0, 10)
        col_lay.setAlignment(Qt.AlignCenter)

        col_btn = QPushButton('🔑')
        col_btn.setFixedSize(36, 36)
        col_btn.setCursor(Qt.PointingHandCursor)
        col_btn.setFont(QFont('Segoe UI', 14))
        col_btn.setStyleSheet(f'''
            QPushButton {{
                background:{NAVY3}; border:none; border-radius:8px;
            }}
            QPushButton:hover {{ background:{NAVY2}; }}
        ''')
        col_btn.clicked.connect(lambda: self.activation_requested.emit(''))
        col_lay.addWidget(col_btn, 0, Qt.AlignCenter)
        self._footer_collapsed.setVisible(False)

        root_lay = QVBoxLayout(self._footer_frame)
        root_lay.setContentsMargins(0, 0, 0, 0)
        root_lay.setSpacing(0)
        root_lay.addWidget(self._footer_expanded)
        root_lay.addWidget(self._footer_collapsed)

        return self._footer_frame

    # ── Collapse / Expand ─────────────────────────────────────────────────────

    def _toggle_collapse(self):
        self._collapsed = not self._collapsed
        self._toggle_btn.update()   # chevron yönünü yenile
        target_w = COLLAPSED_W if self._collapsed else EXPANDED_W

        # Metinleri animasyondan önce gizle/göster
        if self._collapsed:
            self._logo_big.setVisible(False)
            self._logo_small.setVisible(True)
            self._footer_expanded.setVisible(False)
            self._footer_collapsed.setVisible(True)
            self._toggle_btn.setText('▶')
            for item in self._items.values():
                item.set_expanded(False)
        else:
            self._logo_small.setVisible(False)
            self._logo_big.setVisible(True)
            self._footer_collapsed.setVisible(False)
            self._footer_expanded.setVisible(True)
            self._toggle_btn.setText('◀')
            for item in self._items.values():
                item.set_expanded(True)

        self._anim.stop()
        self._anim_min.stop()
        self._anim.setStartValue(self.width())
        self._anim.setEndValue(target_w)
        self._anim_min.setStartValue(self.width())
        self._anim_min.setEndValue(target_w)
        self._anim.start()
        self._anim_min.start()

    # ── Navigasyon ────────────────────────────────────────────────────────────

    def _on_item_clicked(self, module_id: str):
        self.set_active(module_id)
        self.module_selected.emit(module_id)

    def _on_lock_clicked(self, module_id: str):
        self.activation_requested.emit(module_id)

    def set_active(self, module_id: str):
        if self._active_id and self._active_id in self._items:
            self._items[self._active_id].set_active(False)
        self._active_id = module_id
        if module_id in self._items:
            self._items[module_id].set_active(True)

    # ── State güncellemesi ────────────────────────────────────────────────────

    def update_module_states(self, module_states: 'dict[str, dict]'):
        self._module_states = module_states
        for mid, item in self._items.items():
            info = module_states.get(mid, {})
            item.set_state(
                state      = info.get('state', 'locked'),
                tooltip    = info.get('tooltip', ''),
                days_left  = info.get('days_left'),
                trial_days = info.get('trial_days'),
                has_update = info.get('has_update', False),
            )

    def update_lock_status(self, locked_ids: 'set[str]',
                           lock_reasons: 'dict[str, str]'):
        states = {}
        for mid in self._items:
            if mid in locked_ids:
                states[mid] = {'state': 'locked', 'tooltip': lock_reasons.get(mid, '')}
            else:
                states[mid] = {'state': 'licensed', 'tooltip': ''}
        self.update_module_states(states)

    def mark_modules_updated(self, module_ids: list):
        """Belirtilen modüllerin sidebar itemlerinde new.png badge gösterir."""
        for mid in module_ids:
            item = self._items.get(mid)
            if item:
                item.set_state(
                    item.state,
                    tooltip   = item.toolTip(),
                    days_left = item._days_left,
                    trial_days= item._trial_days,
                    has_update= True,
                )

    def set_app_update(self, version: str):
        """Güncelleme butonu gösterilir, lisans butonu korunur."""
        try:
            self._update_btn.setText(f'↑  Güncelleme v{version}')
            self._update_btn.setToolTip(f'ContraCORE {version} mevcut — tıkla, güncelle')
            self._update_btn.setVisible(True)
            self._footer_frame.setFixedHeight(108)
        except Exception:
            pass


    def _on_update_btn_clicked(self):
        """Güncelle butonuna basıldığında onay dialog'u gösterir."""
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
        from PySide6.QtCore import Qt
        from PySide6.QtGui import QFont

        version = self._update_btn.text().replace('↑  Güncelleme ', '').strip()

        dlg = QDialog(self.window())
        dlg.setWindowTitle('Güncelleme')
        dlg.setFixedWidth(380)
        dlg.setModal(True)
        dlg.setStyleSheet('QDialog { background: #0B1F3A; }')

        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(28, 24, 28, 20)
        lay.setSpacing(16)

        title = QLabel(f'Güncelleme Mevcut — {version}')
        title.setFont(QFont('Segoe UI', 11, QFont.Bold))
        title.setStyleSheet('color: #ffffff; background: transparent;')
        lay.addWidget(title)

        msg = QLabel('Program güncellenecek ve yeniden başlatılacak.\nDevam etmek istiyor musunuz?')
        msg.setFont(QFont('Segoe UI', 9))
        msg.setStyleSheet('color: #A0AEC0; background: transparent;')
        msg.setWordWrap(True)
        lay.addWidget(msg)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        btn_row.addStretch()

        btn_style_no = '''
            QPushButton {
                background: #1E3660; color: #A0AEC0;
                border: 1px solid #2D4A6A; border-radius: 6px;
                padding: 0 20px; font-size: 9pt;
            }
            QPushButton:hover { background: #2D4A6A; color: #ffffff; }
        '''
        btn_style_yes = '''
            QPushButton {
                background: #0970fc; color: #ffffff;
                border: none; border-radius: 6px;
                padding: 0 20px; font-size: 9pt; font-weight: 700;
            }
            QPushButton:hover { background: #1a7ffd; }
            QPushButton:pressed { background: #0558cc; }
        '''

        no_btn = QPushButton('Daha Sonra')
        no_btn.setFixedHeight(34)
        no_btn.setCursor(Qt.PointingHandCursor)
        no_btn.setStyleSheet(btn_style_no)
        no_btn.clicked.connect(dlg.reject)
        btn_row.addWidget(no_btn)

        yes_btn = QPushButton('Güncelle')
        yes_btn.setFixedHeight(34)
        yes_btn.setCursor(Qt.PointingHandCursor)
        yes_btn.setStyleSheet(btn_style_yes)
        yes_btn.clicked.connect(dlg.accept)
        btn_row.addWidget(yes_btn)

        lay.addLayout(btn_row)

        if dlg.exec() == QDialog.Accepted:
            self.update_clicked.emit()


# ── Yardımcı: eski arayüzden dönüşüm ─────────────────────────────────────────

def _legacy_to_states(modules, locked_ids, lock_reasons) -> 'dict[str, dict]':
    locked_ids   = locked_ids   or set()
    lock_reasons = lock_reasons or {}
    result = {}
    for entry in modules:
        mid = entry['id']
        if mid in locked_ids:
            result[mid] = {'state': 'locked', 'tooltip': lock_reasons.get(mid, '')}
        else:
            result[mid] = {'state': 'licensed', 'tooltip': ''}
    return result
