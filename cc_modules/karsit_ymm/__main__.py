# -*- coding: utf-8 -*-
import sys
from PySide6.QtWidgets import QApplication
from cc_modules.karsit_ymm.gui import MainWindow

app = QApplication(sys.argv)
w = MainWindow(expire_date=None, trial_status=(30, 0, 999))
w.show()
sys.exit(app.exec())
