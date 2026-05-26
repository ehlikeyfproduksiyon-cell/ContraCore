#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ContraCore — Ana Giriş Noktası
Developed by Serkan ŞAHİN © 2026

Tek QApplication oluşturur; Shell'i başlatır.
"""

import sys
import os

# ContraCore kök dizinini sys.path'e ekle
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from core.crash_log import install as _install_crash_log
_install_crash_log()

from PySide6.QtWidgets import QApplication
from PySide6.QtGui     import QFont
from PySide6.QtCore    import Qt

from core.shell import Shell


def main():
    app = QApplication(sys.argv)

    # Yüksek DPI (Qt6'da varsayılan aktif, try/except ile Qt5 uyumluluğu)
    try:
        app.setAttribute(Qt.AA_EnableHighDpiScaling, True)
        app.setAttribute(Qt.AA_UseHighDpiPixmaps,    True)
    except AttributeError:
        pass

    app.setFont(QFont('Segoe UI', 10))
    app.setApplicationName('ContraCore')
    app.setOrganizationName('Serkan ŞAHİN')

    shell = Shell()
    shell.show()

    sys.exit(app.exec())


if __name__ == '__main__':
    main()
