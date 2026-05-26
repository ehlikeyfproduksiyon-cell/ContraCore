#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ContraCore — Ana Shell Penceresi

Sidebar + QStackedWidget mimarisi.
Modülleri lazy-load eder; mevcut modül UI'larına dokunmaz.
"""

import os
import sys

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QStackedWidget,
    QLabel, QVBoxLayout, QPushButton, QMessageBox,
)
from PySide6.QtCore import Qt, QTimer
from datetime import datetime as _dt
from PySide6.QtGui  import QIcon, QFont, QPixmap

from core.sidebar import Sidebar
from core.router  import ModuleRouter

from core import _icons as _ic


class Shell(QMainWindow):
    """
    ContraCore ana penceresi.

    Layout:
        ┌─────────┬────────────────────────────┐
        │         │                            │
        │ Sidebar │   QStackedWidget           │
        │ (220px) │   (Aktif Modül Widget'ı)   │
        │         │                            │
        └─────────┴────────────────────────────┘
    """

    def __init__(self):
        super().__init__()
        self._router        = ModuleRouter()
        self._stacked       = QStackedWidget()
        self._stack_index   : dict[str, int] = {}   # module_id → stack index
        self._active_module : str | None     = None

        self._setup_window()
        self._setup_ui()
        self._open_default_module()

        # Pending update (Launcher tarafından yazıldı)
        from core.update_state import read_pending, clear_pending, read_last_update, clear_last_update
        from core.version import APP_VERSION
        self._pending_update = read_pending()
        if self._pending_update:
            # Eğer pending versiyon mevcut versiyondan yüksek değilse geçersiz — temizle
            def _ver(s):
                try: return tuple(int(x) for x in str(s).split('.'))
                except: return (0,)
            if _ver(self._pending_update.get('version', '0')) <= _ver(APP_VERSION):
                clear_pending()
                self._pending_update = None
            else:
                QTimer.singleShot(1500, self._show_update_banner)

        # Güncelleme tamamlandı mı? — "Neler Yeni" dialogu
        last = read_last_update()
        if last:
            clear_last_update()
            QTimer.singleShot(800, lambda: self._show_whats_new(last))

    # ── Pencere Ayarları ──────────────────────────────────────────────────────

    def _setup_window(self):
        self.setWindowTitle('ContraCore')
        self.setMinimumSize(1060, 660)

        # Status bar'ı gizle — aksi hâlde pencerenin altında beyaz şerit kalır
        self.statusBar().hide()

        # Drag & drop olaylarının alt widget'lara (FolderCard / FileCard) ulaşması için
        self.setAcceptDrops(True)

        # Shell arka planını navy yap: sidebar ile aynı renk.
        # QStackedWidget içindeki modülün kendi arka planı bunu örter.
        self.setStyleSheet(f'QMainWindow {{ background: #0B1F3A; }}')

        # İkon
        _ico = _ic.load('contralogoo.ico')
        if _ico.isNull():
            _ico = _ic.load('contralogoo.png')
        if not _ico.isNull():
            self.setWindowIcon(QIcon(_ico))

        # Ekran boyutu — yüksekliğin %95'i (xml-fatura standalone ile aynı davranış)
        from PySide6.QtWidgets import QApplication
        screen = QApplication.primaryScreen().availableGeometry()
        h = int(screen.height() * 0.95)
        w = min(1200, screen.width() - 80)
        x = screen.x() + (screen.width()  - w) // 2
        y = screen.y() + (screen.height() - h) // 2
        self.setGeometry(x, y, w, h)

    # ── UI ────────────────────────────────────────────────────────────────────

    def _setup_ui(self):
        registry = self._router.registry()

        # Sidebar — adapter'lardan gerçek 3-state bilgisi
        self._sidebar = Sidebar(
            modules       = registry,
            module_states = self._compute_module_states(),
        )
        self._sidebar.module_selected.connect(self._on_module_selected)
        self._sidebar.activation_requested.connect(self._on_activation_requested)
        self._sidebar.update_clicked.connect(self._on_update_clicked)

        # Sağ alan: sadece stacked widget
        right_area = QWidget()
        right_area.setStyleSheet('background: #F2F4F7;')
        v_lay = QVBoxLayout(right_area)
        v_lay.setContentsMargins(0, 0, 0, 0)
        v_lay.setSpacing(0)
        v_lay.addWidget(self._stacked, 1)

        # Merkezi alan
        container = QWidget()
        container.setStyleSheet('background: #F2F4F7;')
        h_lay = QHBoxLayout(container)
        h_lay.setContentsMargins(0, 0, 0, 0)
        h_lay.setSpacing(0)

        h_lay.addWidget(self._sidebar)
        h_lay.addWidget(right_area, 1)

        self.setCentralWidget(container)

    # ── Güncelleme Banner ─────────────────────────────────────────────────────

    def _show_update_banner(self):
        if not self._pending_update:
            return
        version         = self._pending_update.get('version', '?')
        updated_modules = self._pending_update.get('updated_modules', [])
        self._sidebar.set_app_update(version)
        if updated_modules:
            self._sidebar.mark_modules_updated(updated_modules)

    def _show_whats_new(self, last: dict):
        """Güncelleme tamamlandıktan sonra açılan 'Neler Yeni' dialogu."""
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QScrollArea
        version         = last.get('version', '?')
        notes           = last.get('notes', '')
        changelog       = last.get('changelog', [])
        updated_modules = last.get('updated_modules', [])

        # Modül badge'leri güncelle
        if updated_modules:
            self._sidebar.mark_modules_updated(updated_modules)

        dlg = QDialog(self)
        dlg.setWindowTitle(f'ContraCORE {version} — Güncelleme Tamamlandı')
        dlg.setMinimumWidth(460)
        dlg.setModal(True)
        dlg.setStyleSheet('QDialog { background: #0B1F3A; }')

        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(28, 24, 28, 20)
        lay.setSpacing(14)

        # Başlık
        title = QLabel(f'✓  ContraCORE {version} yüklendi')
        title.setFont(QFont('Segoe UI', 13, QFont.Bold))
        title.setStyleSheet('color: #C9A46A; background: transparent;')
        lay.addWidget(title)

        # Açıklama notu
        if notes:
            lbl = QLabel(notes)
            lbl.setFont(QFont('Segoe UI', 9))
            lbl.setStyleSheet('color: #A0AEC0; background: transparent;')
            lbl.setWordWrap(True)
            lay.addWidget(lbl)

        # Changelog listesi
        if changelog:
            cl_title = QLabel('Bu sürümde:')
            cl_title.setFont(QFont('Segoe UI', 9, QFont.Bold))
            cl_title.setStyleSheet('color: #CBD5E0; background: transparent;')
            lay.addWidget(cl_title)

            scroll = QScrollArea()
            scroll.setMaximumHeight(200)
            scroll.setWidgetResizable(True)
            scroll.setStyleSheet('''
                QScrollArea { border: 1px solid #1E3A5F; border-radius: 6px; background: #0F2A4A; }
                QScrollBar:vertical { width: 6px; background: #0B1F3A; }
                QScrollBar::handle:vertical { background: #2D4A6A; border-radius: 3px; }
            ''')
            inner = QWidget()
            inner.setStyleSheet('background: #0F2A4A;')
            vl = QVBoxLayout(inner)
            vl.setContentsMargins(12, 10, 12, 10)
            vl.setSpacing(6)
            for item in changelog:
                row = QLabel(f'·  {item}')
                row.setFont(QFont('Segoe UI', 9))
                row.setStyleSheet('color: #E2E8F0; background: transparent;')
                row.setWordWrap(True)
                vl.addWidget(row)
            vl.addStretch()
            scroll.setWidget(inner)
            lay.addWidget(scroll)

        # Güncellenen modüller
        if updated_modules:
            mod_names = {'xml-fatura': 'XML Fatura', 'compare-191': 'Compare 191'}
            names = [mod_names.get(m, m) for m in updated_modules]
            mod_lbl = QLabel('Güncellenen modüller:  ' + ',  '.join(names))
            mod_lbl.setFont(QFont('Segoe UI', 8))
            mod_lbl.setStyleSheet('color: #718096; background: transparent;')
            lay.addWidget(mod_lbl)

        # Kapat butonu
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        ok_btn = QPushButton('Tamam')
        ok_btn.setFixedSize(100, 34)
        ok_btn.setCursor(Qt.PointingHandCursor)
        ok_btn.setFont(QFont('Segoe UI', 9, QFont.Bold))
        ok_btn.setStyleSheet('''
            QPushButton {
                background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
                    stop:0 #C9A46A, stop:1 #A0783A);
                color: #0B1F3A; border: none; border-radius: 6px;
            }
            QPushButton:hover { background: #DDB87A; }
        ''')
        ok_btn.clicked.connect(dlg.accept)
        btn_row.addWidget(ok_btn)
        lay.addLayout(btn_row)

        dlg.exec()

    def _on_update_clicked(self):
        """Güncelle butonuna basıldığında Launcher'ı --do-update ile başlatır ve çıkar."""
        import subprocess as _sp
        launcher = os.path.join(os.path.dirname(sys.executable), 'ContraCORELauncher.exe')
        if not os.path.isfile(launcher):
            QMessageBox.warning(self, 'Hata',
                'ContraCORELauncher.exe bulunamadı.\n'
                'Lütfen ContraCORELauncher.exe üzerinden programı başlatın.')
            return
        _sp.Popen([launcher, '--do-update', '--pid', str(os.getpid())],
                  creationflags=_sp.DETACHED_PROCESS,
                  cwd=os.path.dirname(launcher))
        from PySide6.QtWidgets import QApplication
        QApplication.quit()

    # ── Modül Yükleme ─────────────────────────────────────────────────────────

    def _on_module_selected(self, module_id: str):
        """Sidebar'dan modül seçildiğinde çağrılır."""
        if module_id == self._active_module:
            return

        # Önceki modülü deactivate et
        self._call_lifecycle(self._active_module, 'on_module_deactivated')

        # Yüklü değilse lazy-load
        if module_id not in self._stack_index:
            self._load_into_stack(module_id)

        idx = self._stack_index.get(module_id)
        if idx is not None:
            self._stacked.setCurrentIndex(idx)
            self._active_module = module_id
            self._activate_module_license(module_id)
            # Yeni modülü activate et
            self._call_lifecycle(module_id, 'on_module_activated')

    def _load_into_stack(self, module_id: str):
        """Modülü router'dan alır, stack'e ekler."""
        from PySide6.QtWidgets import QSizePolicy
        widget = self._router.load(module_id, parent=self)

        if widget is None:
            return

        # Embedded widget'ın QStackedWidget alanını tamamen doldurmasını garantile
        widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        idx = self._stacked.addWidget(widget)
        self._stack_index[module_id] = idx

    def _open_default_module(self):
        """Program açılışında ilk aktif modülü yükler."""
        registry = self._router.registry()
        if not registry:
            return

        first_id = registry[0]['id']
        self._sidebar.set_active(first_id)
        self._load_into_stack(first_id)

        idx = self._stack_index.get(first_id)
        if idx is not None:
            self._stacked.setCurrentIndex(idx)
            self._active_module = first_id
            self._activate_module_license(first_id)
            self._call_lifecycle(first_id, 'on_module_activated')

        # Trial ilk yüklemede başlamış olabilir — sidebar'ı taze durumla güncelle
        self._sidebar.update_module_states(self._compute_module_states())

    def _compute_module_states(self) -> 'dict[str, dict]':
        """
        Her modül için adapter'dan gerçek lisans durumunu okur.
        GUI yüklenmez — sadece license.py çalıştırılır (hafif).

        Returns:
            { module_id: {'state': 'licensed'|'trial'|'locked', 'tooltip': str} }
        """
        result   = {}
        registry = self._router.registry()

        for entry in registry:
            mid     = entry['id']
            adapter = entry.get('_adapter')

            if adapter is None:
                result[mid] = {'state': 'locked', 'tooltip': 'Modül yüklenemedi'}
                continue

            try:
                status = adapter.get_license_status()
            except Exception:
                result[mid] = {'state': 'locked', 'tooltip': ''}
                continue

            if status.get('valid'):
                expire    = status.get('expire')
                days_left = None
                tooltip   = 'Lisanslı'
                if expire:
                    days_left = max(0, (expire - _dt.now()).days)
                    try:
                        tooltip += f"  —  {expire.strftime('%d.%m.%Y')}'e kadar"
                    except Exception:
                        pass
                result[mid] = {
                    'state': 'licensed', 'tooltip': tooltip,
                    'expire': expire, 'days_left': days_left,
                    'trial_days': None, 'has_update': False,
                }

            elif status.get('trial_active'):
                ts         = status.get('trial_status')
                trial_days = ts[0] if ts else None
                tooltip    = 'Deneme sürümü aktif'
                if ts:
                    tooltip += f'  —  {ts[0]} gün kaldı'
                result[mid] = {
                    'state': 'trial', 'tooltip': tooltip,
                    'expire': None, 'days_left': None,
                    'trial_days': trial_days, 'has_update': False,
                }

            else:
                result[mid] = {
                    'state': 'locked', 'tooltip': 'Lisans gerekli',
                    'expire': None, 'days_left': None,
                    'trial_days': None, 'has_update': False,
                }

        return result

    def _call_lifecycle(self, module_id: str | None, method: str):
        """
        Modülün host window'unda lifecycle hook'unu çağırır.
        Hook yoksa sessizce geçer — mevcut modüllerin davranışı bozulmaz.
        """
        if module_id is None:
            return
        idx = self._stack_index.get(module_id)
        if idx is None:
            return
        widget = self._stacked.widget(idx)
        host   = getattr(widget, '_cc_host_window', None)
        if host is None:
            return
        fn = getattr(host, method, None)
        if callable(fn):
            try:
                fn()
            except Exception:
                pass

    def _activate_module_license(self, module_id: str):
        """
        Aktif modülün sys.modules context'ini (license, gui, activation)
        doğru modüle yönlendirir. Her iki modülde aynı isimli dosyalar
        adapter'daki unique key mekanizması ile ayrı tutulur.
        """
        adapter_key = f'cc_adapter_{module_id.replace("-", "_")}'
        adapter = sys.modules.get(adapter_key)
        if adapter is not None and hasattr(adapter, 'activate_module_context'):
            adapter.activate_module_context()
        else:
            # Fallback: sadece license context'ini güncelle
            lic_key = f'cc_license_{module_id.replace("-", "_")}'
            lic_mod = sys.modules.get(lic_key)
            if lic_mod is not None:
                sys.modules['license'] = lic_mod

    # ── Unified Lisans Aktivasyonu ────────────────────────────────────────────

    def _on_activation_requested(self, module_id: str):
        """
        Sidebar'dan activation_requested sinyali geldiğinde çağrılır.
        module_id boşsa genel lisans yöneticisi açılır.

        İlk kullanım senaryosu (trial başlatılmamış, lisans yok):
          Aktivasyon dialogu açmak yerine modülü normal yükleme akışından
          geçiriyoruz. Adapter'ın get_embedded_widget() kendi içinde trial'ı
          otomatik başlatır ve modülü açar. Sidebar 3-state güncellenir.

        Trial bitmişse veya genel lisans yönetimi isteniyorsa:
          Standart LicenseManagerDialog açılır.
        """
        if module_id:
            from core.license import manager as _mgr, trial as _trial
            _valid, _, _ = _mgr.check_module_license(module_id)
            if not _valid and not _trial.is_trial_started(module_id):
                # Trial başlatılmamış (veya AppData silinmiş) — reload ile fresh yükle.
                # _on_module_selected kullanılamaz: stack'teki placeholder'ı gösterir.
                # reload_module önbelleği temizler, get_embedded_widget trial'ı başlatır.
                self.reload_module(module_id)
                self._sidebar.update_module_states(self._compute_module_states())
                self._sidebar.set_active(module_id)
                self._activate_module_license(module_id)
                self._call_lifecycle(module_id, 'on_module_activated')
                return

        from core.license.activation_dialog import LicenseManagerDialog

        registry = self._router.registry()
        dlg = LicenseManagerDialog(
            module_registry = registry,
            focused_module  = module_id,
            parent          = self,
        )
        dlg.module_activated.connect(self._on_license_activated)
        dlg.exec()

    def _on_license_activated(self, module_id: str):
        """
        Unified activation dialog bir modülü aktive ettiğinde çağrılır.
        Sidebar 3-state görünümünü günceller, modülü reload eder.
        """
        # Sidebar'ı adapter'lardan taze durum bilgisiyle güncelle
        self._sidebar.update_module_states(self._compute_module_states())

        # Yeni aktive edilen modülü yeniden yükle ve aç
        self.reload_module(module_id)
        self._sidebar.set_active(module_id)
        self._active_module = module_id
        self._activate_module_license(module_id)
        self._call_lifecycle(module_id, 'on_module_activated')

    # ── İlk Gösterim ─────────────────────────────────────────────────────────

    def showEvent(self, event):
        """
        Pencere gösterildikten sonra embedded widget'ın geometry'sini tazeler.

        QStackedWidget + QMainWindow.centralWidget() embed kombinasyonunda
        ilk render geometry henüz hesaplanmadan tetiklenebilir.
        0 ms → bir sonraki event loop turu (platform paint öncesi).
        50 ms → platform paint tamamlandıktan sonra ikinci doğrulama.
        """
        super().showEvent(event)
        QTimer.singleShot(0,  self._initial_layout_refresh)
        QTimer.singleShot(50, self._initial_layout_refresh)

    def _initial_layout_refresh(self):
        from PySide6.QtWidgets import QSizePolicy
        current = self._stacked.currentWidget()
        if current is not None:
            current.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            current.updateGeometry()
            # Stacked widget boyutuna eşitle — mevcut geometry yanlışsa düzelt
            if current.size() != self._stacked.size():
                current.resize(self._stacked.size())
        self._stacked.updateGeometry()
        self.centralWidget().updateGeometry()
        self.update()

    # ── Kapatma / Cleanup ─────────────────────────────────────────────────────

    def closeEvent(self, event):
        """
        Shell kapanırken gömülü modüllerin thread'lerini graceful olarak durdurur.
        Her modül için önce stop isteği gönderilir, 3 saniye beklenir;
        hâlâ çalışıyorsa terminate edilir.
        """
        for i in range(self._stacked.count()):
            widget = self._stacked.widget(i)
            host   = getattr(widget, '_cc_host_window', None)
            if host is None:
                continue
            self._stop_host_threads(host)
        event.accept()

    @staticmethod
    def _stop_host_threads(host):
        """
        Bir host window'un bilinen thread'lerini durdurur.
        Her modülün attribute isimleri farklı olabileceğinden getattr ile sorgulanır.

        xml-fatura  : stop_flag (threading.Event), worker, fc_a/fc_s/fc_c._counter, _upd_checker
        compare-191 : _stop_flag (threading.Event), worker, _duzelt_worker
        """
        # ── Stop sinyali — her iki modülün event isimlerini dene ──────────────
        # xml-fatura: stop_flag  |  compare-191: _stop_flag
        for flag_attr in ('stop_flag', '_stop_flag'):
            flag = getattr(host, flag_attr, None)
            if flag is not None:
                try:
                    flag.set()
                except Exception:
                    pass

        # ── Ana worker (her iki modülde 'worker' adıyla) ──────────────────────
        worker = getattr(host, 'worker', None)
        if worker and worker.isRunning():
            worker.quit()
            if not worker.wait(3000):    # 3 sn graceful, sonra terminate
                worker.terminate()

        # ── Düzeltme worker'ı (compare-191 — '_duzelt_worker') ───────────────
        duzelt = getattr(host, '_duzelt_worker', None)
        if duzelt and duzelt.isRunning():
            duzelt.quit()
            if not duzelt.wait(2000):
                duzelt.terminate()

        # ── Klasör sayım thread'leri (xml-fatura — FolderCard._counter) ───────
        for fc_attr in ('fc_a', 'fc_s', 'fc_c'):
            fc      = getattr(host, fc_attr, None)
            counter = getattr(fc, '_counter', None) if fc else None
            if counter and counter.isRunning():
                counter.quit()
                counter.wait(1000)

        # ── Güncelleme kontrol thread'i (xml-fatura — '_upd_checker') ─────────
        checker = getattr(host, '_upd_checker', None)
        if checker and checker.isRunning():
            checker.quit()
            checker.wait(1000)

    # ── Yeniden Yükleme (aktivasyon sonrası) ──────────────────────────────────

    def reload_module(self, module_id: str):
        """
        Aktivasyon veya lisans güncellemesi sonrası modülü yeniden yükler.
        Dışarıdan (adapter veya aktivasyon dialogu) çağrılabilir.
        """
        if module_id in self._stack_index:
            old_idx = self._stack_index.pop(module_id)
            old_w   = self._stacked.widget(old_idx)
            self._stacked.removeWidget(old_w)
            if old_w:
                old_w.deleteLater()
            # removeWidget sonrası QStackedWidget tüm index'leri shift eder;
            # kalan modüllerin _stack_index kayıtlarını güncelle
            self._reindex_after_remove(old_idx)

        self._router.invalidate(module_id)
        self._load_into_stack(module_id)

        idx = self._stack_index.get(module_id)
        if idx is not None:
            self._stacked.setCurrentIndex(idx)
            self._active_module = module_id

    def _reindex_after_remove(self, removed_idx: int):
        """removeWidget sonrası shifted olan index'leri düzeltir."""
        for mid, idx in list(self._stack_index.items()):
            if idx > removed_idx:
                self._stack_index[mid] = idx - 1
