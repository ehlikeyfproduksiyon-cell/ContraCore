#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ContraCore — Unified Lisans Yöneticisi Dialog
"""

import os
import webbrowser
import urllib.parse
from datetime import datetime

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QFrame, QComboBox, QWidget, QApplication,
    QGraphicsDropShadowEffect, QSizePolicy,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui  import (
    QFont, QColor, QPixmap, QPainter, QLinearGradient,
    QPainterPath, QBrush, QFontMetrics,
)

from core.license.manager import (
    get_hwid, activate_module, get_all_module_statuses,
)

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LOGO_DIR = os.path.join(ROOT_DIR, 'Logom', 'big_logo')
WHATSAPP = '905310879339'

# Panel ile birebir aynı palet
BG      = '#F2F4F7'
CARD    = '#FFFFFF'
NAVY    = '#0B1F3A'
NAVY2   = '#162D4E'
NAVY3   = '#1E3660'
GOLD    = '#C9A46A'
GOLD_L  = '#E4C285'
BORDER  = '#E5E7EB'
TEXT    = '#111827'
TEXT2   = '#6B7280'
TEXT3   = '#9CA3AF'
GREEN   = '#22C55E'
RED     = '#EF4444'
AMBER   = '#F59E0B'
WHITE_D = '#A0AEC0'


def _gradient_text_pix(text, fam, sz, top, bot):
    font = QFont(fam, sz, QFont.Bold)
    fm   = QFontMetrics(font)
    w    = fm.horizontalAdvance(text) + 4
    h    = fm.height() + 4
    pix  = QPixmap(w, h)
    pix.fill(Qt.transparent)
    p    = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)
    path = QPainterPath()
    path.addText(2, fm.ascent() + 2, font, text)
    g = QLinearGradient(0, 2, 0, h - 2)
    g.setColorAt(0, QColor(top))
    g.setColorAt(1, QColor(bot))
    p.setBrush(QBrush(g))
    p.setPen(Qt.NoPen)
    p.drawPath(path)
    p.end()
    return pix


def _card_frame():
    f = QFrame()
    f.setObjectName('ccCard')
    f.setFrameShape(QFrame.NoFrame)
    # Sadece ccCard objectName'ini hedefle — child widget'lara border bulaşmasın
    f.setStyleSheet(f'''
        QFrame#ccCard {{
            background: {CARD};
            border-radius: 12px;
            border: 1px solid {BORDER};
        }}
    ''')
    return f


def _section_label(text):
    l = QLabel(text)
    l.setFont(QFont('Segoe UI', 9, QFont.Bold))
    l.setStyleSheet(f'color:{TEXT2}; background:transparent; letter-spacing:0.5px;')
    return l


# ── Modül Durum Satırı ────────────────────────────────────────────────────────

class _ModuleRow(QFrame):
    def __init__(self, label, status):
        super().__init__()
        self.setFrameShape(QFrame.NoFrame)
        self.setStyleSheet('background:transparent;')
        self.setFixedHeight(48)

        enabled = status.get('enabled', False)
        expire  = status.get('expire')

        if enabled is True:
            dot_clr  = '#16A34A'
            tag_txt  = 'Aktif'
            tag_bg   = '#DCFCE7'
            tag_clr  = '#15803D'
        elif enabled is None:
            dot_clr  = '#D97706'
            tag_txt  = 'Deneme'
            tag_bg   = '#FEF3C7'
            tag_clr  = '#92400E'
        else:
            dot_clr  = '#DC2626'
            tag_txt  = 'Lisanssız'
            tag_bg   = '#FEE2E2'
            tag_clr  = '#991B1B'

        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)

        # Renkli nokta
        dot = QLabel('●')
        dot.setFixedWidth(16)
        dot.setFont(QFont('Segoe UI', 9))
        dot.setStyleSheet(f'color:{dot_clr}; background:transparent;')
        lay.addWidget(dot)

        # Modül adı
        name = QLabel(label)
        name.setFont(QFont('Segoe UI', 10, QFont.Bold))
        name.setStyleSheet(f'color:{TEXT}; background:transparent;')
        lay.addWidget(name)

        # Tarih (lisanslıysa)
        if enabled is True and expire:
            try:
                exp_dt = datetime.strptime(expire, '%Y-%m-%d')
                days   = max(0, (exp_dt - datetime.now()).days)
                date_l = QLabel(f'{exp_dt.strftime("%d.%m.%Y")}  ·  {days} gün')
                date_l.setFont(QFont('Segoe UI', 9))
                date_l.setStyleSheet(f'color:{TEXT3}; background:transparent;')
                lay.addWidget(date_l)
            except ValueError:
                pass

        lay.addStretch()

        # Durum etiketi — sabit genişlik, hepsi aynı boyut
        tag = QLabel(tag_txt)
        tag.setFont(QFont('Segoe UI', 8, QFont.Bold))
        tag.setAlignment(Qt.AlignCenter)
        tag.setFixedSize(72, 22)
        tag.setStyleSheet(f'''
            color:{tag_clr};
            background:{tag_bg};
            border-radius:6px;
            border:none;
        ''')
        lay.addWidget(tag)


# ── Ana Dialog ────────────────────────────────────────────────────────────────

class LicenseManagerDialog(QDialog):
    module_activated = Signal(str)

    def __init__(self, module_registry, focused_module='', parent=None):
        super().__init__(parent)
        self._registry       = module_registry
        self._focused_module = focused_module
        self._hwid           = get_hwid()

        self.setWindowTitle('ContraCore — Lisans Yöneticisi')
        self.setFixedWidth(480)
        self.setWindowFlags(Qt.Dialog | Qt.WindowCloseButtonHint)
        self.setStyleSheet(f'QDialog {{ background:{BG}; }}')

        self._build()
        self._refresh_status()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._build_header())

        body = QWidget()
        body.setStyleSheet(f'background:{BG};')
        body_lay = QVBoxLayout(body)
        body_lay.setContentsMargins(20, 20, 20, 20)
        body_lay.setSpacing(16)

        body_lay.addWidget(self._build_hwid_card())
        body_lay.addWidget(self._build_status_card())
        body_lay.addWidget(self._build_activation_card())

        footer = QLabel('Developed by Serkan ŞAHİN  ©  2026')
        footer.setAlignment(Qt.AlignCenter)
        footer.setFont(QFont('Segoe UI', 8))
        footer.setStyleSheet(f'color:{TEXT3}; background:transparent;')
        body_lay.addWidget(footer)

        root.addWidget(body)

    # ── Header ───────────────────────────────────────────────────────────────

    def _build_header(self):
        f = QFrame()
        f.setFrameShape(QFrame.NoFrame)
        f.setFixedHeight(78)
        f.setStyleSheet(f'''
            QFrame {{
                background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
                    stop:0 {NAVY2}, stop:1 {NAVY});
                border-bottom: 1px solid {NAVY3};
            }}
        ''')
        lay = QHBoxLayout(f)
        lay.setContentsMargins(22, 0, 22, 0)
        lay.setSpacing(14)

        logo_lbl = QLabel()
        logo_lbl.setStyleSheet('background:transparent;')
        lp = os.path.join(LOGO_DIR, 'ContraCore.png')
        lpix = QPixmap(lp)
        if not lpix.isNull():
            logo_lbl.setPixmap(lpix.scaled(44, 44, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        lay.addWidget(logo_lbl)

        txt_col = QVBoxLayout()
        txt_col.setSpacing(2)
        txt_col.setContentsMargins(0, 0, 0, 0)

        title_row = QHBoxLayout()
        title_row.setSpacing(0)
        title_row.setContentsMargins(0, 0, 0, 0)
        for text, top, bot in [('Contra', '#FFFFFF', '#C0D0E8'), ('CORE', GOLD_L, GOLD)]:
            lbl = QLabel()
            lbl.setStyleSheet('background:transparent;')
            lbl.setPixmap(_gradient_text_pix(text, 'Coolvetica', 19, top, bot))
            title_row.addWidget(lbl)
        title_row.addStretch()
        txt_col.addLayout(title_row)

        sub = QLabel('Lisans Yöneticisi')
        sub.setFont(QFont('Segoe UI', 9))
        sub.setStyleSheet(f'color:{WHITE_D}; background:transparent;')
        txt_col.addWidget(sub)

        lay.addLayout(txt_col)
        lay.addStretch()

        lock = QLabel('🔐')
        lock.setFont(QFont('Segoe UI', 24))
        lock.setStyleSheet('background:transparent;')
        glow = QGraphicsDropShadowEffect()
        glow.setBlurRadius(16)
        glow.setColor(QColor(GOLD))
        glow.setOffset(0, 0)
        lock.setGraphicsEffect(glow)
        lay.addWidget(lock)
        return f

    # ── HWID Kartı ───────────────────────────────────────────────────────────

    def _build_hwid_card(self):
        card = _card_frame()
        lay  = QVBoxLayout(card)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(10)

        lay.addWidget(_section_label('BİLGİSAYAR KİMLİK KODU'))

        row = QHBoxLayout()
        row.setSpacing(8)

        self._hwid_lbl = QLabel(self._hwid)
        self._hwid_lbl.setFont(QFont('Consolas', 12, QFont.Bold))
        self._hwid_lbl.setFixedHeight(42)
        self._hwid_lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._hwid_lbl.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
        self._hwid_lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self._hwid_lbl.setStyleSheet(f'''
            color:{NAVY};
            background:#F8FAFC;
            border-radius:8px;
            border:1px solid {BORDER};
            padding:0 12px;
        ''')
        row.addWidget(self._hwid_lbl)

        copy_btn = QPushButton('Kopyala')
        copy_btn.setFont(QFont('Segoe UI', 9, QFont.Bold))
        copy_btn.setFixedSize(80, 42)
        copy_btn.setCursor(Qt.PointingHandCursor)
        copy_btn.setStyleSheet(f'''
            QPushButton {{
                background:{NAVY}; color:#FFFFFF;
                border:none; border-radius:8px;
            }}
            QPushButton:hover {{ background:{NAVY2}; }}
        ''')
        copy_btn.clicked.connect(self._copy_hwid)
        row.addWidget(copy_btn)
        lay.addLayout(row)

        self._copy_msg = QLabel('')
        self._copy_msg.setFont(QFont('Segoe UI', 9))
        self._copy_msg.setStyleSheet(f'color:{GREEN}; background:transparent;')
        lay.addWidget(self._copy_msg)

        wa_btn = QPushButton('📱  WhatsApp ile Gönder  —  0531 087 93 39')
        wa_btn.setFont(QFont('Segoe UI', 9, QFont.Bold))
        wa_btn.setFixedHeight(36)
        wa_btn.setCursor(Qt.PointingHandCursor)
        wa_btn.setStyleSheet('''
            QPushButton {
                background:#25D366; color:#FFFFFF;
                border:none; border-radius:8px;
                font-weight:700;
            }
            QPushButton:hover { background:#1DA855; }
        ''')
        wa_btn.clicked.connect(self._send_whatsapp)
        lay.addWidget(wa_btn)
        return card

    # ── Modül Durumları ───────────────────────────────────────────────────────

    def _build_status_card(self):
        self._status_card = _card_frame()
        self._status_lay  = QVBoxLayout(self._status_card)
        self._status_lay.setContentsMargins(16, 14, 16, 14)
        self._status_lay.setSpacing(0)
        return self._status_card

    def _refresh_status(self):
        # Temizle
        while self._status_lay.count():
            item = self._status_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self._status_lay.addWidget(_section_label('MODÜL DURUMLARI'))
        self._status_lay.addSpacing(8)

        from core.license.trial import is_trial_started
        all_ids  = [e['id'] for e in self._registry]
        statuses = get_all_module_statuses(all_ids)

        for i, entry in enumerate(self._registry):
            mid    = entry['id']
            status = statuses.get(mid, {'enabled': False, 'reason': '', 'expire': None})
            self._status_lay.addWidget(_ModuleRow(entry['label'], status))

            # Trial başlatılmamışsa "Deneme Başlat" butonu göster
            if not status.get('enabled') and not is_trial_started(mid):
                btn = QPushButton(f'▶  {entry["label"]} — Deneme Sürümünü Başlat')
                btn.setFont(QFont('Segoe UI', 9, QFont.Bold))
                btn.setFixedHeight(34)
                btn.setCursor(Qt.PointingHandCursor)
                btn.setStyleSheet(f'''
                    QPushButton {{
                        background: #7C3AED;
                        color: #FFFFFF;
                        border: none;
                        border-radius: 7px;
                        font-weight: 700;
                    }}
                    QPushButton:hover {{ background: #6D28D9; }}
                ''')
                btn.clicked.connect(lambda checked, m=mid: self._start_trial(m))
                self._status_lay.addSpacing(4)
                self._status_lay.addWidget(btn)

            # Modüller arası ince çizgi
            if i < len(self._registry) - 1:
                sep = QFrame()
                sep.setFrameShape(QFrame.HLine)
                sep.setFixedHeight(1)
                sep.setStyleSheet(f'background:{BORDER}; border:none;')
                self._status_lay.addWidget(sep)

        self.adjustSize()

    def _start_trial(self, module_id: str):
        from core.license.trial import start_trial
        start_trial(module_id)
        self.module_activated.emit(module_id)
        self.accept()

    # ── Aktivasyon Kartı ──────────────────────────────────────────────────────

    def _build_activation_card(self):
        card = _card_frame()
        lay  = QVBoxLayout(card)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(10)

        lay.addWidget(_section_label('LİSANS AKTİVASYONU'))

        # Modül seçici — her modül kendi accent rengiyle
        self._mod_btns  = []
        self._mod_sel   = 0
        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)

        for idx, e in enumerate(self._registry):
            accent = e.get('accent_color', GOLD)
            btn = QPushButton(e['label'])
            btn.setFont(QFont('Segoe UI', 9, QFont.Bold))
            btn.setFixedHeight(34)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setProperty('accent', accent)
            btn.setProperty('idx', idx)
            btn.setCheckable(True)
            self._mod_btns.append(btn)
            btn.clicked.connect(lambda checked, i=idx: self._select_mod(i))
            btn_row.addWidget(btn)

        lay.addLayout(btn_row)

        # Varsayılan seçim
        focused_idx = 0
        if self._focused_module:
            for i, e in enumerate(self._registry):
                if e['id'] == self._focused_module:
                    focused_idx = i
                    break
        self._select_mod(focused_idx)

        # Anahtar girişi
        self._key_input = QLineEdit()
        self._key_input.setPlaceholderText('V2-XXXXXXXX-XXXXXXXX-XXXXXXXX-XXXXXXXX')
        self._key_input.setFont(QFont('Consolas', 11))
        self._key_input.setFixedHeight(42)
        self._key_input.setMaxLength(42)
        self._key_input.setAlignment(Qt.AlignCenter)
        self._key_input.setStyleSheet(f'''
            QLineEdit {{
                background:{CARD}; color:{TEXT};
                border:1px solid {BORDER}; border-radius:8px;
                padding:0 14px;
            }}
            QLineEdit:focus {{ border:1.5px solid {GOLD}; }}
        ''')
        lay.addWidget(self._key_input)

        self._msg_lbl = QLabel('')
        self._msg_lbl.setFont(QFont('Segoe UI', 9))
        self._msg_lbl.setAlignment(Qt.AlignCenter)
        self._msg_lbl.setWordWrap(True)
        self._msg_lbl.setStyleSheet(f'color:{RED}; background:transparent;')
        lay.addWidget(self._msg_lbl)

        act_btn = QPushButton('Aktive Et')
        act_btn.setFont(QFont('Segoe UI', 10, QFont.Bold))
        act_btn.setFixedHeight(44)
        act_btn.setCursor(Qt.PointingHandCursor)
        act_btn.setStyleSheet(f'''
            QPushButton {{
                background:{NAVY}; color:#FFFFFF;
                border:none; border-radius:8px;
            }}
            QPushButton:hover {{ background:{NAVY2}; }}
        ''')
        act_btn.clicked.connect(self._activate)
        lay.addWidget(act_btn)
        return card

    def _select_mod(self, idx: int):
        self._mod_sel = idx
        for i, btn in enumerate(self._mod_btns):
            accent = btn.property('accent')
            if i == idx:
                btn.setChecked(True)
                btn.setStyleSheet(f'''
                    QPushButton {{
                        background:{accent};
                        color:{NAVY};
                        border:none;
                        border-radius:8px;
                        font-weight:700;
                    }}
                ''')
            else:
                btn.setChecked(False)
                btn.setStyleSheet(f'''
                    QPushButton {{
                        background:{CARD};
                        color:{TEXT2};
                        border:1px solid {BORDER};
                        border-radius:8px;
                        font-weight:600;
                    }}
                    QPushButton:hover {{
                        background:#F1F5F9;
                        color:{TEXT};
                        border-color:#94A3B8;
                    }}
                ''')

    # ── Aksiyonlar ────────────────────────────────────────────────────────────

    def _copy_hwid(self):
        QApplication.clipboard().setText(self._hwid)
        self._copy_msg.setText('✓  Kopyalandı')

    def _send_whatsapp(self):
        msg = f'Merhaba, ContraCore lisans talebim. Bilgisayar kodum: {self._hwid}'
        webbrowser.open(f'https://wa.me/{WHATSAPP}?text={urllib.parse.quote(msg)}')

    def _activate(self):
        key       = self._key_input.text().strip()
        entry     = self._registry[self._mod_sel]
        module_id = entry['id']
        label     = entry['label']

        if not key:
            self._msg(f'Lütfen lisans anahtarını girin.', AMBER)
            return

        self._msg('Doğrulanıyor…', TEXT2)
        QApplication.processEvents()

        success, msg, expire = activate_module(module_id, key)

        if success:
            exp_str = expire.strftime('%d.%m.%Y') if expire else ''
            self._msg(f'✓  {label} lisansı aktive edildi!  {exp_str}', GREEN)
            self._key_input.clear()
            self._refresh_status()
            self.module_activated.emit(module_id)
        else:
            self._msg(f'✕  {msg}', RED)

    def _msg(self, text, color):
        self._msg_lbl.setText(text)
        self._msg_lbl.setStyleSheet(f'color:{color}; background:transparent;')
