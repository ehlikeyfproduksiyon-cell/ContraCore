#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
191 Muavin Karşılaştırma — Aktivasyon Ekranı (PySide6)
Developed by Serkan ŞAHİN © 2026
"""
import sys, os, webbrowser, urllib.parse
from PySide6.QtWidgets import *
from PySide6.QtCore    import *
from PySide6.QtGui     import *

from core import _icons as _ic

def icon_path(name):
    return _ic.load(name)

class ActivationWindow(QDialog):
    def __init__(self, expired=False, expire_msg='', parent=None):
        super().__init__(parent)
        self.activated     = False
        self.trial_started = False
        self.expired       = expired
        self.expire_msg    = expire_msg
        self.setWindowTitle('191 Muavin Karşılaştırma — Lisans Aktivasyonu')
        self.setFixedSize(460, 580)
        self.setWindowFlags(Qt.Dialog | Qt.WindowCloseButtonHint)
        self._build()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(28, 24, 28, 24)
        lay.setSpacing(12)

        self.setStyleSheet('''
            QDialog { background: #F0F2F5; }
            QFrame#info_card {
                background: #FFFFFF;
                border-radius: 14px;
                border: 1px solid #E2E8F0;
            }
            QFrame#warn_frame {
                background: #FEF2F2;
                border-radius: 10px;
                border: 1px solid #FECACA;
            }
            QLabel#hwid_lbl {
                background: #F3F4F6;
                border-radius: 10px;
                border: 1px solid #E5E7EB;
                font-family: Consolas, monospace;
                font-size: 14px;
                font-weight: 800;
                color: #0B1F3A;
                padding: 0 10px;
            }
            QPushButton#btn_copy {
                background: #0B1F3A;
                color: #FFFFFF;
                border-radius: 10px;
                border: none;
                font-size: 11px;
                font-weight: 700;
            }
            QPushButton#btn_copy:hover { background: #162D4E; }
            QPushButton#btn_wa {
                background: #25D366;
                color: #FFFFFF;
                border-radius: 10px;
                border: none;
                font-size: 12px;
                font-weight: 600;
                padding: 0 14px;
            }
            QPushButton#btn_wa:hover { background: #1DA855; }
            QLineEdit#key_input {
                background: #FFFFFF;
                border: 1.5px solid #CBD5E1;
                border-radius: 10px;
                font-family: Consolas, monospace;
                font-size: 13px;
                color: #0F172A;
                padding: 0 14px;
            }
            QLineEdit#key_input:focus { border-color: #C9A46A; }
            QPushButton#btn_activate {
                background: #22C55E;
                color: #FFFFFF;
                border-radius: 12px;
                border: none;
                font-size: 14px;
                font-weight: 800;
            }
            QPushButton#btn_activate:hover { background: #16A34A; }
            QPushButton#btn_trial {
                background: transparent;
                color: #6B7280;
                border-radius: 12px;
                border: 1.5px solid #CBD5E1;
                font-size: 12px;
                font-weight: 600;
            }
            QPushButton#btn_trial:hover {
                background: #F1F5F9;
                border-color: #94A3B8;
                color: #374151;
            }
        ''')

        ttl = QLabel('🔐  LİSANS AKTİVASYONU')
        ttl.setAlignment(Qt.AlignCenter)
        ttl.setStyleSheet(
            'font-size:17px;font-weight:800;color:#0B1F3A;background:transparent;'
        )
        lay.addWidget(ttl)

        sub = QLabel('191 Muavin Karşılaştırma')
        sub.setAlignment(Qt.AlignCenter)
        sub.setStyleSheet('font-size:11px;color:#6B7280;background:transparent;')
        lay.addWidget(sub)

        if self.expired and self.expire_msg:
            warn = QFrame()
            warn.setObjectName('warn_frame')
            wl = QHBoxLayout(warn)
            wl.setContentsMargins(12, 8, 12, 8)
            wlbl = QLabel(f'⚠️  {self.expire_msg}')
            wlbl.setStyleSheet(
                'font-size:11px;font-weight:600;color:#DC2626;background:transparent;'
            )
            wlbl.setWordWrap(True)
            wl.addWidget(wlbl)
            lay.addWidget(warn)

        hwid_card = QFrame()
        hwid_card.setObjectName('info_card')
        hl = QVBoxLayout(hwid_card)
        hl.setContentsMargins(16, 12, 16, 12)
        hl.setSpacing(8)

        h_lbl = QLabel('Bilgisayar Kodunuz  (Bu kodu bize gönderin)')
        h_lbl.setStyleSheet(
            'font-size:10px;font-weight:700;color:#6B7280;'
            'letter-spacing:0.4px;background:transparent;'
        )
        hl.addWidget(h_lbl)

        from license import get_hwid
        self._hwid = get_hwid()

        hwid_row = QHBoxLayout()
        hwid_row.setSpacing(8)

        self.hwid_display = QLabel(self._hwid)
        self.hwid_display.setObjectName('hwid_lbl')
        self.hwid_display.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
        self.hwid_display.setFixedHeight(46)
        self.hwid_display.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        btn_copy = QPushButton('📋  Kopyala')
        btn_copy.setObjectName('btn_copy')
        btn_copy.setFixedSize(100, 46)
        btn_copy.setCursor(Qt.PointingHandCursor)
        btn_copy.clicked.connect(self._copy_hwid)

        hwid_row.addWidget(self.hwid_display)
        hwid_row.addWidget(btn_copy)
        hl.addLayout(hwid_row)

        btn_wa = QPushButton('📱  WhatsApp ile Gönder  →  0531 087 93 39')
        btn_wa.setObjectName('btn_wa')
        btn_wa.setFixedHeight(40)
        btn_wa.setCursor(Qt.PointingHandCursor)
        btn_wa.clicked.connect(self._open_whatsapp)
        hl.addWidget(btn_wa)

        lay.addWidget(hwid_card)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet('color:#E2E8F0;background:#E2E8F0;max-height:1px;')
        lay.addWidget(sep)

        key_lbl = QLabel('Lisans Anahtarınız')
        key_lbl.setStyleSheet(
            'font-size:11px;font-weight:700;color:#475569;background:transparent;'
        )
        lay.addWidget(key_lbl)

        self.key_input = QLineEdit()
        self.key_input.setObjectName('key_input')
        self.key_input.setPlaceholderText('XXXX-XXXX-XXXX-XXXX-XXXX-XXXX')
        self.key_input.setAlignment(Qt.AlignCenter)
        self.key_input.setFixedHeight(46)
        lay.addWidget(self.key_input)

        self.msg_lbl = QLabel('')
        self.msg_lbl.setAlignment(Qt.AlignCenter)
        self.msg_lbl.setFixedHeight(18)
        self.msg_lbl.setStyleSheet('font-size:11px;color:#EF4444;background:transparent;')
        lay.addWidget(self.msg_lbl)

        btn_act = QPushButton('✓   AKTİVE ET')
        btn_act.setObjectName('btn_activate')
        btn_act.setFixedHeight(52)
        btn_act.setCursor(Qt.PointingHandCursor)
        btn_act.clicked.connect(self._activate)
        lay.addWidget(btn_act)

        sep2 = QFrame()
        sep2.setFrameShape(QFrame.HLine)
        sep2.setStyleSheet('color:#E2E8F0;background:#E2E8F0;max-height:1px;')
        lay.addWidget(sep2)

        if not self.expired:
            btn_trial = QPushButton('🔓   Deneme Sürümünü Başlat')
            btn_trial.setObjectName('btn_trial')
            btn_trial.setFixedHeight(44)
            btn_trial.setCursor(Qt.PointingHandCursor)
            btn_trial.clicked.connect(self._start_trial)
            lay.addWidget(btn_trial)

            trial_info = QLabel('30 gün  •  Toplam 1000 karşılaştırma  •  Ücretsiz')
            trial_info.setAlignment(Qt.AlignCenter)
            trial_info.setStyleSheet(
                'font-size:9px;color:#9CA3AF;background:transparent;'
            )
            lay.addWidget(trial_info)

        dev = QLabel('Developed by Serkan ŞAHİN  ©  2026')
        dev.setAlignment(Qt.AlignCenter)
        dev.setStyleSheet('font-size:9px;color:#9CA3AF;background:transparent;')
        lay.addWidget(dev)

    def _copy_hwid(self):
        QApplication.clipboard().setText(self._hwid)
        self.msg_lbl.setText('✅  Bilgisayar kodu kopyalandı!')
        self.msg_lbl.setStyleSheet(
            'font-size:11px;color:#22C55E;background:transparent;'
        )

    def _start_trial(self):
        from license import start_trial, get_trial_status
        trial_active, _, _, _ = get_trial_status()
        if trial_active:
            self.trial_started = True
            self.accept()
            return
        start_trial()
        self.trial_started = True
        self.accept()

    def _open_whatsapp(self):
        msg   = (f'Merhaba, 191 Muavin Karşılaştırma lisans talebim. '
                 f'Bilgisayar kodum: {self._hwid}')
        phone = '905310879339'
        url   = f'https://wa.me/{phone}?text={urllib.parse.quote(msg)}'
        webbrowser.open(url)

    def _activate(self):
        from license import validate_key, save_license
        key = self.key_input.text().strip()

        if not key:
            self.msg_lbl.setText('⚠️  Lütfen lisans anahtarını girin.')
            self.msg_lbl.setStyleSheet(
                'font-size:11px;color:#EF4444;background:transparent;'
            )
            return

        valid, msg, expire = validate_key(key)

        if valid:
            save_license(key)
            self.activated = True
            exp = expire.strftime('%d.%m.%Y')

            dlg = QDialog(self)
            dlg.setWindowTitle('Aktivasyon Başarılı')
            dlg.setFixedSize(360, 210)
            dlg.setStyleSheet('QDialog { background:#FFFFFF; }')
            d_lay = QVBoxLayout(dlg)
            d_lay.setContentsMargins(30, 28, 30, 28)
            d_lay.setSpacing(10)

            ico = QLabel('✅')
            ico.setAlignment(Qt.AlignCenter)
            ico.setStyleSheet('font-size:38px;background:transparent;')
            d_lay.addWidget(ico)

            ttl2 = QLabel('Lisans Başarıyla Aktive Edildi!')
            ttl2.setAlignment(Qt.AlignCenter)
            ttl2.setStyleSheet(
                'font-size:14px;font-weight:800;color:#0F172A;background:transparent;'
            )
            d_lay.addWidget(ttl2)

            sub2 = QLabel(
                f'Geçerlilik: <b style="color:#22C55E;">{exp}</b> tarihine kadar.'
            )
            sub2.setAlignment(Qt.AlignCenter)
            sub2.setTextFormat(Qt.RichText)
            sub2.setStyleSheet(
                'font-size:12px;color:#475569;background:transparent;'
            )
            d_lay.addWidget(sub2)

            btn_ok = QPushButton('Tamam')
            btn_ok.setFixedHeight(42)
            btn_ok.setCursor(Qt.PointingHandCursor)
            btn_ok.setStyleSheet('''
                QPushButton {
                    background: #22C55E; color: #FFFFFF;
                    border-radius: 10px; border: none;
                    font-size: 13px; font-weight: 700;
                }
                QPushButton:hover { background: #16A34A; }
            ''')
            btn_ok.clicked.connect(dlg.accept)
            d_lay.addWidget(btn_ok)

            dlg.exec()
            self.accept()
        else:
            self.msg_lbl.setText(f'✗  {msg}')
            self.msg_lbl.setStyleSheet(
                'font-size:11px;color:#EF4444;background:transparent;'
            )

