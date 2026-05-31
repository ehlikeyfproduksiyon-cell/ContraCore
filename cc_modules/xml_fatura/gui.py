#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
XML Fatura Otomasyonu v1.6
Developed by Serkan ŞAHİN © 2026
"""
import sys, os, json, threading, time
from datetime import datetime

from PySide6.QtWidgets import *
from PySide6.QtCore    import *
from PySide6.QtGui     import *

from core import _icons as _ic

_APPDATA_DIR = os.path.join(os.environ.get('APPDATA', os.path.expanduser('~')), 'ContraCore', 'xml-fatura')
os.makedirs(_APPDATA_DIR, exist_ok=True)
RECENT_FILE  = os.path.join(_APPDATA_DIR, 'recent_folders.json')
PREFS_FILE   = os.path.join(_APPDATA_DIR, 'preferences.json')

def ip(name):
    return _ic.load(name)

def load_recent():
    try:
        with open(RECENT_FILE, encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {'alis': [], 'satis': [], 'cikti': []}

def save_recent(data):
    try:
        with open(RECENT_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False)
    except Exception:
        pass

def load_prefs():
    try:
        with open(PREFS_FILE, encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}

def save_prefs(data):
    try:
        with open(PREFS_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

def add_recent(tag, path):
    d = load_recent()
    lst = d.get(tag, [])
    if path in lst:
        lst.remove(path)
    lst.insert(0, path)
    d[tag] = lst[:5]
    save_recent(d)

# ── Güncelleme Sabitleri ─────────────────────────────────────────────────────
VERSION_CURRENT = "1.6"
VERSION_URL = "https://raw.githubusercontent.com/ehlikeyfproduksiyon-cell/xml-fatura-otomasyonu/main/version.txt"
EXE_URL     = "https://github.com/ehlikeyfproduksiyon-cell/xml-fatura-otomasyonu/releases/latest/download/XML_Fatura_Otomasyonu.exe"

# ── Renk Paleti ──────────────────────────────────────────────────────────────
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
BLUE_BG = '#EFF6FF'
ORG_BG  = '#FFF7ED'
GRN_BG  = '#F0FDF4'
RED_BG  = '#FFF1F2'
LOG_BG  = '#0F172A'

# ── Güncelleme Kontrolü Thread ───────────────────────────────────────────────
class UpdateChecker(QThread):
    update_available = Signal(str)   # yeni versiyon string'i
    check_failed     = Signal(str)   # hata mesajı (debug)

    def run(self):
        import urllib.request, ssl
        try:
            import time as _time
            ctx = ssl._create_unverified_context()
            _url = VERSION_URL + '?t=' + str(int(_time.time()))
            req = urllib.request.Request(
                _url,
                headers={'User-Agent': f'XMLFaturaOtomasyonu/{VERSION_CURRENT}'}
            )
            with urllib.request.urlopen(req, timeout=5, context=ctx) as r:
                latest = r.read().decode('utf-8').strip()
            if latest and self._is_newer(latest):
                self.update_available.emit(latest)
        except Exception as e:
            self.check_failed.emit(str(e))

    @staticmethod
    def _is_newer(ver: str) -> bool:
        try:
            def _parts(v):
                return [int(x) for x in v.strip().split('.')]
            return _parts(ver) > _parts(VERSION_CURRENT)
        except Exception:
            return False


# ── Worker ────────────────────────────────────────────────────────────────────
class Sig(QObject):
    log            = Signal(str, str)
    progress       = Signal(float)
    stats          = Signal(int, int, int, int, int, int)  # ad, at, sd, st, h, muk
    status         = Signal(str)
    current        = Signal(str)
    eta            = Signal(float, str, str)
    done           = Signal(int, int, int, int, int, int, int)  # a, s, h, at, st, new_count, muk
    totals         = Signal(float, float, float, float)         # alis_matrah, alis_toplam, satis_matrah, satis_toplam
    error_file     = Signal(str, str)   # fname, error_msg
    duplicate_file = Signal(str, str)   # fname, inv_id

class Worker(QThread):
    def __init__(self, alis, satis, cikti, stop_flag, pause_flag,
                 alis_start=0, satis_start=0, months_split=False,
                 recursive=False, max_files=None):
        super().__init__()
        self.sig          = Sig()
        self.alis         = alis
        self.satis        = satis
        self.cikti        = cikti
        self.stop_flag    = stop_flag
        self.pause_flag   = pause_flag
        self.alis_start   = alis_start
        self.satis_start  = satis_start
        self.months_split = months_split
        self.recursive    = recursive
        self.max_files    = max_files

    def run(self):
        try:
            from cc_modules.xml_fatura.main import process_all
            process_all(
                alis_folder=self.alis,
                satis_folder=self.satis,
                cikti_folder=self.cikti,
                stop_flag=self.stop_flag,
                pause_flag=self.pause_flag,
                cb_log=self.sig.log.emit,
                cb_progress=self.sig.progress.emit,
                cb_stats=self.sig.stats.emit,
                cb_status=self.sig.status.emit,
                cb_current=self.sig.current.emit,
                cb_eta=self.sig.eta.emit,
                cb_done=self.sig.done.emit,
                cb_totals=self.sig.totals.emit,
                cb_error_file=self.sig.error_file.emit,
                cb_duplicate_file=self.sig.duplicate_file.emit,
                alis_start=self.alis_start,
                satis_start=self.satis_start,
                months_split=self.months_split,
                recursive=self.recursive,
                max_files=self.max_files,
            )
        except ImportError as e:
            self.sig.log.emit(f'❌ main.py yüklenemedi: {e}', 'err')
            self.sig.done.emit(0, 0, 1, 0, 0, 0, 0)
        except Exception as e:
            import traceback
            self.sig.log.emit(f'❌ Hata: {e}', 'err')
            self.sig.log.emit(traceback.format_exc(), 'err')
            self.sig.done.emit(0, 0, 1, 0, 0, 0, 0)

# DownloadDialog ve _DownloadThread kaldırıldı — Updater.exe üstlendi


# ── Profil Popup ──────────────────────────────────────────────────────────────
class ProfilePopup(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent, Qt.Popup | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedWidth(290)
        self._just_closed = False

        outer = QVBoxLayout(self)
        outer.setContentsMargins(6, 6, 6, 6)

        card = QFrame()
        card.setStyleSheet('''
            QFrame {
                background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
                    stop:0 #162D4E, stop:1 #0B1F3A);
                border-radius: 16px;
                border: 1px solid #C9A46A;
            }
        ''')

        # Kart glow efekti
        glow = QGraphicsDropShadowEffect()
        glow.setBlurRadius(28)
        glow.setColor(QColor('#C9A46A44'))
        glow.setOffset(0, 4)
        card.setGraphicsEffect(glow)

        cl = QVBoxLayout(card)
        cl.setContentsMargins(0, 0, 0, 16)
        cl.setSpacing(0)

        # ── Gradient başlık şeridi ──────────────────────────────────────────
        header = QFrame()
        header.setFixedHeight(64)
        header.setStyleSheet('''
            QFrame {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 #1E3660, stop:1 #0B1F3A);
                border-radius: 16px;
                border-bottom-left-radius: 0px;
                border-bottom-right-radius: 0px;
                border: none;
            }
        ''')
        hl = QHBoxLayout(header)
        hl.setContentsMargins(16, 10, 16, 10)
        hl.setSpacing(12)

        # Avatar
        av_lbl = QLabel()
        av_lbl.setFixedSize(42, 42)
        av_lbl.setStyleSheet('background:transparent;border:none;')
        av_pix = QPixmap(ip('profile.png'))
        if not av_pix.isNull():
            canvas = QPixmap(42, 42)
            canvas.fill(Qt.transparent)
            pc = QPainter(canvas)
            pc.setRenderHint(QPainter.Antialiasing)
            sc = av_pix.scaled(38, 38, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            path = QPainterPath()
            path.addEllipse(2.0, 2.0, 38.0, 38.0)
            pc.setClipPath(path)
            pc.drawPixmap(2, 2, sc)
            pc.setClipping(False)
            pc.setPen(QPen(QColor(GOLD), 2))
            pc.setBrush(Qt.NoBrush)
            pc.drawEllipse(QRectF(1, 1, 40, 40))
            pc.end()
            av_lbl.setPixmap(canvas)
        else:
            av_lbl.setText('👤')
        hl.addWidget(av_lbl)

        name_col = QVBoxLayout()
        name_col.setSpacing(1)
        name_lbl = QLabel('Serkan ŞAHİN')
        name_lbl.setStyleSheet(
            'font-size:13px;font-weight:700;color:#FFFFFF;background:transparent;border:none;'
        )
        role_lbl = QLabel('Yazılım Geliştirici')
        role_lbl.setStyleSheet(
            f'font-size:10px;color:{GOLD};background:transparent;border:none;'
        )
        name_col.addWidget(name_lbl)
        name_col.addWidget(role_lbl)
        hl.addLayout(name_col)
        hl.addStretch()
        cl.addWidget(header)

        # ── Ayraç çizgi ────────────────────────────────────────────────────
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setFixedHeight(1)
        sep.setStyleSheet('background:#C9A46A44;border:none;max-height:1px;')
        cl.addWidget(sep)
        cl.addSpacing(12)

        # ── İletişim satırları ──────────────────────────────────────────────
        for ico, label, val in [
            ('📱', 'WhatsApp', '0531 087 93 39'),
            ('✉️', 'Mail',     'serkan.opsiyonymm@gmail.com'),
        ]:
            row_frame = QFrame()
            row_frame.setStyleSheet('''
                QFrame {
                    background: rgba(255,255,255,0.04);
                    border-radius: 8px;
                    border: 1px solid rgba(201,164,106,0.15);
                }
                QFrame:hover {
                    background: rgba(201,164,106,0.10);
                    border: 1px solid rgba(201,164,106,0.35);
                }
            ''')
            row_lay = QHBoxLayout(row_frame)
            row_lay.setContentsMargins(12, 8, 12, 8)
            row_lay.setSpacing(10)

            ico_lbl = QLabel(ico)
            ico_lbl.setFixedWidth(20)
            ico_lbl.setStyleSheet('background:transparent;border:none;font-size:14px;')

            info_col = QVBoxLayout()
            info_col.setSpacing(0)
            lbl_top = QLabel(label)
            lbl_top.setStyleSheet(
                f'font-size:9px;font-weight:600;color:{GOLD};background:transparent;border:none;'
            )
            lbl_val = QLabel(val)
            lbl_val.setStyleSheet(
                'font-size:11px;color:#E2E8F0;background:transparent;border:none;'
            )
            lbl_val.setTextInteractionFlags(Qt.TextSelectableByMouse)
            info_col.addWidget(lbl_top)
            info_col.addWidget(lbl_val)

            row_lay.addWidget(ico_lbl)
            row_lay.addLayout(info_col)
            row_lay.addStretch()

            cl.addWidget(row_frame)
            cl.addSpacing(6)

        outer.addWidget(card)

    def hideEvent(self, event):
        super().hideEvent(event)
        self._just_closed = True
        QTimer.singleShot(200, self._reset_just_closed)

    def _reset_just_closed(self):
        self._just_closed = False

    def show_at(self, widget):
        p = widget.mapToGlobal(QPoint(0, widget.height() + 4))
        x = p.x() - self.width() + widget.width()
        screen = QApplication.screenAt(p) or QApplication.primaryScreen()
        sg = screen.availableGeometry()
        x = max(sg.left(), min(x,    sg.right()  - self.width()))
        y = max(sg.top(),  min(p.y(), sg.bottom() - self.height()))
        self.move(x, y)
        self.show()

# ── Son Kullanılan Popup ───────────────────────────────────────────────────────
class RecentPopup(QFrame):
    picked = Signal(str)

    def __init__(self, tag, parent=None):
        super().__init__(parent, Qt.Popup | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.tag  = tag
        self.setFixedWidth(320)
        self._lay = QVBoxLayout(self)
        self._lay.setContentsMargins(0, 0, 0, 0)

    def show_at(self, widget):
        self._refresh()
        self.adjustSize()
        p = widget.mapToGlobal(QPoint(0, widget.height() + 4))
        screen = QApplication.screenAt(p) or QApplication.primaryScreen()
        sg = screen.availableGeometry()
        x = max(sg.left(), min(p.x(), sg.right()  - self.width()))
        y = max(sg.top(),  min(p.y(), sg.bottom() - self.height()))
        self.move(x, y)
        self.show()

    def _refresh(self):
        while self._lay.count():
            item = self._lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        card = QFrame()
        card.setStyleSheet(
            f'QFrame{{background:{CARD};border-radius:12px;border:1px solid {BORDER};}}'
        )
        cl = QVBoxLayout(card)
        cl.setContentsMargins(12, 12, 12, 12)
        cl.setSpacing(4)

        ttl = QLabel('Son Kullanılan Klasörler')
        ttl.setStyleSheet(
            f'font-size:11px;font-weight:700;color:{TEXT};background:transparent;border:none;'
        )
        cl.addWidget(ttl)

        paths = load_recent().get(self.tag, [])
        if not paths:
            l = QLabel('Henüz klasör seçilmedi.')
            l.setStyleSheet(
                f'font-size:11px;color:{TEXT3};background:transparent;border:none;'
            )
            cl.addWidget(l)
        else:
            for p in paths:
                b = QPushButton(f'  {os.path.basename(p)}')
                b.setToolTip(p)
                b.setCursor(Qt.PointingHandCursor)
                b.setStyleSheet(f'''
                    QPushButton {{
                        background: #F9FAFB; border: 1px solid {BORDER};
                        border-radius: 8px; color: {TEXT2}; font-size: 11px;
                        padding: 6px 10px; text-align: left;
                    }}
                    QPushButton:hover {{
                        background: {BLUE_BG}; border-color: {NAVY}; color: {TEXT};
                    }}
                ''')
                b.clicked.connect(lambda _, x=p: self._pick(x))
                cl.addWidget(b)

        self._lay.addWidget(card)

    def _pick(self, path):
        self.picked.emit(path)
        self.close()

# ── XML Sayım Thread'i ────────────────────────────────────────────────────────
class XmlCountThread(QThread):
    counted = Signal(int, int, int)  # xml, html, pdf

    def __init__(self, path, recursive):
        super().__init__()
        self.path      = path
        self.recursive = recursive

    def run(self):
        import zipfile as _zf
        xml_c = html_c = pdf_c = 0
        try:
            walk = os.walk(self.path) if self.recursive \
                   else [(self.path, [], os.listdir(self.path))]
            for dirpath, _, files in walk:
                for fn in files:
                    fp = os.path.join(dirpath, fn)
                    low = fn.lower()
                    if low.endswith('.xml'):
                        xml_c += 1
                    elif low.endswith('.html'):
                        html_c += 1
                    elif low.endswith('.pdf'):
                        pdf_c += 1
                    elif low.endswith('.zip'):
                        try:
                            with _zf.ZipFile(fp) as zf:
                                xml_c += sum(1 for n in zf.namelist()
                                             if n.lower().endswith('.xml'))
                        except Exception:
                            pass
        except Exception:
            pass
        self.counted.emit(xml_c, html_c, pdf_c)

# ── Klasör Kartı ──────────────────────────────────────────────────────────────
class FolderCard(QFrame):
    changed = Signal(str, str)

    def __init__(self, tag, label, ico_file, ico_bg, count_enabled=True):
        super().__init__()
        self.tag           = tag
        self._path         = ''
        self._recursive    = False
        self._counter      = None
        self._count_enabled = count_enabled
        self.setAcceptDrops(True)
        self._recent = RecentPopup(tag)
        self._recent.picked.connect(self.set_path)
        self._set_normal_style()
        self.setFixedHeight(76)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 0, 14, 0)
        lay.setSpacing(14)

        # İkon kutusu
        self.ico_box = QLabel()
        self.ico_box.setFixedSize(48, 48)
        self.ico_box.setAlignment(Qt.AlignCenter)
        self.ico_box.setStyleSheet(
            f'background:{ico_bg};border-radius:10px;font-size:22px;border:none;'
        )
        pix = QPixmap(ip(ico_file))
        if not pix.isNull():
            self.ico_box.setPixmap(
                pix.scaled(28, 28, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            )
        else:
            self.ico_box.setText('📁')
        lay.addWidget(self.ico_box)

        # Metin bloğu
        ml = QVBoxLayout()
        ml.setSpacing(2)
        self.lbl_name = QLabel(label)
        self.lbl_name.setStyleSheet(
            f'font-size:11px;font-weight:700;color:{TEXT};'
            f'background:transparent;border:none;letter-spacing:0.3px;'
        )
        self.lbl_path = QLabel('Klasör seçilmedi...')
        self.lbl_path.setStyleSheet(
            f'font-size:11px;color:{TEXT3};background:transparent;border:none;'
        )
        self.lbl_ok = QLabel('')
        self.lbl_ok.setStyleSheet(
            f'font-size:11px;color:{GREEN};font-weight:600;'
            f'background:transparent;border:none;'
        )
        ml.addWidget(self.lbl_name)
        ml.addWidget(self.lbl_path)
        ml.addWidget(self.lbl_ok)
        lay.addLayout(ml, 1)

        # Butonlar
        bl = QHBoxLayout()
        bl.setSpacing(6)

        self.btn_sel = QPushButton('  Seç')
        self.btn_sel.setFixedSize(80, 36)
        self.btn_sel.setCursor(Qt.PointingHandCursor)
        self.btn_sel.setStyleSheet(f'''
            QPushButton {{
                background: {NAVY}; color: #FFF;
                border-radius: 9px; border: none;
                font-size: 11px; font-weight: 600;
            }}
            QPushButton:hover {{ background: {NAVY2}; }}
        ''')

        self.btn_clr = QPushButton()
        self.btn_clr.setFixedSize(32, 36)
        self.btn_clr.setCursor(Qt.PointingHandCursor)
        self.btn_clr.setStyleSheet(f'''
            QPushButton {{
                background: #F3F4F6;
                border-radius: 9px; border: 1px solid {BORDER};
            }}
            QPushButton:hover {{
                background: #FFE4E4; border-color: {RED};
            }}
        ''')
        _pix_x = QPixmap(ip('x.png'))
        if not _pix_x.isNull():
            self.btn_clr.setIcon(QIcon(_pix_x.scaled(16, 16, Qt.KeepAspectRatio, Qt.SmoothTransformation)))
        else:
            self.btn_clr.setText('✕')

        self.btn_rec = QPushButton()
        self.btn_rec.setFixedSize(32, 36)
        self.btn_rec.setCursor(Qt.PointingHandCursor)
        self.btn_rec.setStyleSheet(f'''
            QPushButton {{
                background: #F3F4F6;
                border-radius: 9px; border: 1px solid {BORDER};
            }}
            QPushButton:hover {{
                background: {BLUE_BG}; border-color: {NAVY};
            }}
        ''')
        _pix_clk = QPixmap(ip('clock.png'))
        if not _pix_clk.isNull():
            self.btn_rec.setIcon(QIcon(_pix_clk.scaled(16, 16, Qt.KeepAspectRatio, Qt.SmoothTransformation)))
        else:
            self.btn_rec.setText('🕒')

        bl.addWidget(self.btn_sel)
        bl.addWidget(self.btn_rec)
        bl.addWidget(self.btn_clr)
        lay.addLayout(bl)

        self.btn_sel.clicked.connect(self._browse)
        self.btn_clr.clicked.connect(self.clear)
        self.btn_rec.clicked.connect(lambda: self._recent.show_at(self.btn_rec))

    def _set_normal_style(self):
        self.setStyleSheet(
            f'QFrame{{background:{CARD};border-radius:14px;border:1px solid {BORDER};}}'
        )

    def _browse(self):
        d = QFileDialog.getExistingDirectory(self, 'Klasör Seçin')
        if d:
            self.set_path(d)

    def set_path(self, path):
        self._path = path
        short = path if len(path) <= 50 else '…' + path[-48:]
        self.lbl_path.setText(short)
        self.lbl_path.setStyleSheet(
            f'font-size:11px;color:{TEXT2};background:transparent;border:none;'
        )
        self.lbl_ok.setText('✅  Klasör seçildi')
        add_recent(self.tag, path)
        self.changed.emit(self.tag, path)
        if self._count_enabled:
            self._start_count()

    def set_recursive(self, val: bool):
        self._recursive = val
        if self._path and self._count_enabled:
            self._start_count()

    def _start_count(self):
        if not self._path:
            return
        # Önceki sayımı iptal et
        if self._counter and self._counter.isRunning():
            self._counter.quit()
        self.lbl_ok.setText('✅  Klasör seçildi  |  🔄 taranıyor...')
        self._counter = XmlCountThread(self._path, self._recursive)
        self._counter.counted.connect(self._on_counted)
        self._counter.start()

    def _on_counted(self, xml_c, html_c, pdf_c):
        if not self._path:
            return
        parts = []
        if xml_c:  parts.append(f'{xml_c} XML')
        if html_c: parts.append(f'{html_c} HTML')
        if pdf_c:  parts.append(f'{pdf_c} PDF')
        detail = ' - '.join(parts) if parts else '0 dosya'
        self.lbl_ok.setText(f'✅  Klasör Seçildi  |  {detail}')

    def clear(self):
        self._path = ''
        if self._counter and self._counter.isRunning():
            self._counter.quit()
        self.lbl_path.setText('Klasör seçilmedi...')
        self.lbl_path.setStyleSheet(
            f'font-size:11px;color:{TEXT3};background:transparent;border:none;'
        )
        self.lbl_ok.setText('')
        self.changed.emit(self.tag, '')

    def get_path(self):
        return self._path

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()
            self.setStyleSheet(
                f'QFrame{{background:#F0FDF4;border-radius:14px;border:2px solid {GREEN};}}'
            )

    def dragLeaveEvent(self, e):
        self._set_normal_style()

    def dropEvent(self, e):
        self._set_normal_style()
        for url in e.mimeData().urls():
            p = url.toLocalFile()
            if os.path.isdir(p):
                self.set_path(p)
                break

# ── İstatistik Kartı ──────────────────────────────────────────────────────────
class StatCard(QFrame):
    def __init__(self, title, emoji, ico_bg, num_color, sub='Dosya işlendi'):
        super().__init__()
        self.setStyleSheet(
            f'QFrame{{background:{CARD};border-radius:14px;border:1px solid {BORDER};}}'
        )
        self._done      = 0
        self._anim      = 0.0
        self._total     = 0
        self._num_color = num_color
        self._timer     = QTimer(self)
        self._timer.timeout.connect(self._tick)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(14)

        ico = QLabel(emoji)
        ico.setFixedSize(50, 50)
        ico.setAlignment(Qt.AlignCenter)
        ico.setStyleSheet(
            f'background:{ico_bg};border-radius:12px;font-size:24px;border:none;'
        )
        lay.addWidget(ico)

        tl = QVBoxLayout()
        tl.setSpacing(2)

        t = QLabel(title)
        t.setStyleSheet(
            f'font-size:10px;font-weight:700;color:{TEXT2};'
            f'background:transparent;border:none;letter-spacing:0.8px;'
        )
        self.lbl_num = QLabel('0 / 0')
        self.lbl_num.setStyleSheet(
            f'font-size:17px;font-weight:800;color:{num_color};'
            f'background:transparent;border:none;'
        )
        self.lbl_num.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.lbl_num.setMinimumWidth(0)
        s = QLabel(sub)
        s.setStyleSheet(
            f'font-size:10px;color:{TEXT3};background:transparent;border:none;'
        )
        tl.addWidget(t)
        tl.addWidget(self.lbl_num)
        tl.addWidget(s)
        lay.addLayout(tl, 1)

    def update(self, done, total):
        self._done  = done
        self._total = total
        if not self._timer.isActive():
            self._timer.start(20)

    def _tick(self):
        diff = self._done - self._anim
        if abs(diff) < 0.5:
            self._anim = self._done
            self._timer.stop()
        else:
            self._anim += diff * 0.25
        self.lbl_num.setText(f'{int(self._anim)} / {self._total}')

    def reset(self):
        self._done = self._anim = self._total = 0
        self.lbl_num.setText('0 / 0')
        self._timer.stop()

# ── Donut Grafik (sadece deneme modu) ─────────────────────────────────────────
class DonutWidget(QWidget):
    def __init__(self, used=0, total=5000, parent=None):
        super().__init__(parent)
        self._used  = used
        self._total = total
        self.setFixedSize(72, 72)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)

    def set_values(self, used, total):
        self._used  = used
        self._total = total
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(9, 9, 54, 54)
        pct  = min(1.0, self._used / max(1, self._total))

        pen_bg = QPen(QColor('#E5E7EB'), 9)
        pen_bg.setCapStyle(Qt.FlatCap)
        p.setPen(pen_bg)
        p.setBrush(Qt.NoBrush)
        p.drawArc(rect, 0, 360 * 16)

        if pct > 0:
            pen_fg = QPen(QColor('#D97706'), 9)
            pen_fg.setCapStyle(Qt.RoundCap)
            p.setPen(pen_fg)
            p.drawArc(rect, 90 * 16, -int(pct * 360 * 16))

        p.setPen(QColor('#0B1F3A'))
        p.setFont(QFont('Segoe UI', 9, QFont.Bold))
        p.drawText(QRectF(9, 16, 54, 18), Qt.AlignCenter, f'%{int(pct * 100)}')
        p.setPen(QColor('#6B7280'))
        p.setFont(QFont('Segoe UI', 6))
        p.drawText(QRectF(9, 34, 54, 14), Qt.AlignCenter, 'Kullanıldı')
        p.end()

# ── Ana Pencere ────────────────────────────────────────────────────────────────
class MainWindow(QMainWindow):
    def __init__(self, expire_date=None, trial_status=None):
        super().__init__()
        self.expire_date    = expire_date
        self._trial_status  = trial_status  # (kalan_gun, islenen, kalan) veya None
        self.stop_flag      = threading.Event()
        self.pause_flag     = threading.Event()
        self.worker         = None
        self.is_paused      = False
        self._t0            = None
        self._running       = False
        # Resume desteği
        self._resume_alis   = 0
        self._resume_satis  = 0
        self._cur_alis      = 0
        self._cur_satis     = 0
        # Hatalı ve mükerrer dosya listeleri
        self._error_files     = []   # [(fname, err_msg), ...]
        self._duplicate_files = []   # [(fname, inv_id), ...]
        self._last_totals     = (0.0, 0.0, 0.0, 0.0)  # alis_matrah, alis_toplam, satis_matrah, satis_toplam
        self.donut_widget   = None
        self._profile_popup = ProfilePopup(self)
        self._spin_frames   = ['◐', '◓', '◑', '◒']
        self._spin_idx      = 0
        self._spin_timer    = QTimer(self)
        self._spin_timer.setInterval(120)
        self._spin_timer.timeout.connect(self._spin_tick)
        # ContraCore lifecycle state
        self._cc_paused          = False
        self._cc_log_buffer      = []
        self._cc_spin_was_active = False

        # Pencere başlık
        exp = expire_date.strftime('%d.%m.%Y') if expire_date else ''
        self.setWindowTitle(
            f'XML Fatura Otomasyonu — Lisans: {exp}' if exp else 'XML Fatura Otomasyonu'
        )

        screen = QApplication.primaryScreen().availableGeometry()
        w = 980
        h = int(screen.height() * 0.95)
        x = screen.x() + (screen.width()  - w) // 2
        y = screen.y() + (screen.height() - h) // 2
        self.setMinimumSize(850, 600)
        self.setGeometry(x, y, w, h)

        # Sistem tepsi ikonu
        self._tray = QSystemTrayIcon(self)
        self._tray.setIcon(QIcon(ip('logo.png')))
        self._tray.show()

        self._build()
        self._latest_version = None
        self._start_update_check()

    # ── Kart çerçevesi ────────────────────────────────────────────────────────
    def _card(self):
        f = QFrame()
        f.setStyleSheet(
            f'QFrame{{background:{CARD};border-radius:16px;border:1px solid {BORDER};}}'
        )
        return f

    # ── Ana Layout ────────────────────────────────────────────────────────────
    def _build(self):
        content = QWidget()
        content.setStyleSheet(f'background:{BG};')

        root = QVBoxLayout(content)
        root.setContentsMargins(14, 14, 14, 10)
        root.setSpacing(10)

        root.addWidget(self._header())
        root.addWidget(self._update_banner())
        root.addWidget(self._trial_banner())
        root.addWidget(self._folders())
        root.addWidget(self._buttons())
        root.addWidget(self._stats())
        self._init_state_widgets()
        root.addWidget(self._log(), 1)
        root.addWidget(self._footer())

        screen_h = QApplication.primaryScreen().availableGeometry().height()
        if screen_h < 768:
            scroll = QScrollArea()
            scroll.setWidget(content)
            scroll.setWidgetResizable(True)
            scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            scroll.setStyleSheet(
                f'QScrollArea{{border:none;background:{BG};}}'
            )
            self._root_widget = scroll
            self.setCentralWidget(scroll)
        else:
            self._root_widget = content
            self.setCentralWidget(content)

        from core import theme as _theme
        _theme.register(self._apply_theme)

    # ── Güncelleme Banner ─────────────────────────────────────────────────────
    def _update_banner(self):
        self.banner_update = QFrame()
        self.banner_update.setVisible(False)
        self.banner_update.setFixedHeight(42)
        self.banner_update.setCursor(Qt.PointingHandCursor)
        self.banner_update.setStyleSheet(
            f'QFrame{{background:{GOLD};border-radius:10px;border:none;}}'
        )
        self.banner_update.mousePressEvent = lambda e: self._show_update_dialog()

        lay = QHBoxLayout(self.banner_update)
        lay.setContentsMargins(18, 0, 18, 0)
        lay.setSpacing(10)

        self.lbl_banner_text = QLabel('')
        self.lbl_banner_text.setStyleSheet(
            'font-size:12px;font-weight:700;color:#FFFFFF;background:transparent;border:none;'
        )
        lay.addWidget(self.lbl_banner_text)
        lay.addStretch(1)

        btn_banner = QPushButton('Şimdi Güncelle')
        btn_banner.setFixedHeight(28)
        btn_banner.setCursor(Qt.PointingHandCursor)
        btn_banner.setStyleSheet(
            'QPushButton{background:#FFFFFF;color:#0B1F3A;border:none;'
            'border-radius:6px;font-size:11px;font-weight:700;padding:0 12px;}'
            'QPushButton:hover{background:#F3F4F6;}'
        )
        btn_banner.clicked.connect(self._show_update_dialog)
        lay.addWidget(btn_banner)

        # Eğer önceki oturumda güncelleme bulunduysa hemen göster
        if getattr(self, '_latest_version', None):
            self.lbl_banner_text.setText(
                f'🔄  v{self._latest_version} güncellemesi mevcut!'
            )
            self.banner_update.setVisible(True)

        return self.banner_update

    def _trial_banner(self):
        """
        Deneme modunda üstte sabit bir bilgi şeridi gösterir.
        Lisanslı kullanımda gizlidir.
        """
        self.banner_trial = QFrame()
        self.banner_trial.setFixedHeight(38)
        self.banner_trial.setStyleSheet(
            'QFrame{background:#7C3AED;border-radius:10px;border:none;}'
        )

        lay = QHBoxLayout(self.banner_trial)
        lay.setContentsMargins(18, 0, 18, 0)
        lay.setSpacing(12)

        ico = QLabel('⏳')
        ico.setStyleSheet('background:transparent;border:none;font-size:14px;')
        lay.addWidget(ico)

        self.lbl_trial = QLabel()
        self.lbl_trial.setStyleSheet(
            'font-size:12px;font-weight:700;color:#FFFFFF;background:transparent;border:none;'
        )
        lay.addWidget(self.lbl_trial)
        lay.addStretch(1)

        tip = QLabel('Lisans almak için geliştiriciye ulaşın')
        tip.setStyleSheet(
            'font-size:10px;color:#DDD6FE;background:transparent;border:none;'
        )
        lay.addWidget(tip)

        if self._trial_status:
            kalan_gun, islenen, kalan = self._trial_status
            from license import TRIAL_MAX_FILES as _TMAX
            self.lbl_trial.setText(
                f'Deneme Sürümü  —  {kalan_gun} gün kaldı  |  '
                f'{islenen} / {_TMAX} dosya kullanıldı'
            )
            self.banner_trial.setVisible(True)
        else:
            self.banner_trial.setVisible(False)

        return self.banner_trial

    # ── Header ────────────────────────────────────────────────────────────────
    def _header(self):
        import os as _os
        f = self._card()
        lay = QHBoxLayout(f)
        lay.setContentsMargins(18, 12, 18, 12)
        lay.setSpacing(16)

        # ── SOL: ContraCore logo + başlık ─────────────────────────────────
        left = QHBoxLayout()
        left.setSpacing(12)

        self._lbl_logo = QLabel()
        self._lbl_logo.setStyleSheet('background:transparent;border:none;')
        self._logo_h = 76
        self._update_logo()
        left.addWidget(self._lbl_logo)

        # "ContraCORE" + alt başlık
        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        title_col.setContentsMargins(0, 0, 0, 0)

        title_row = QHBoxLayout()
        title_row.setSpacing(0)
        title_row.setContentsMargins(0, 0, 0, 0)

        from PySide6.QtGui import QPainterPath as _QPP, QLinearGradient as _QLG, QBrush as _QB, QFontMetrics as _QFM

        def _cc_pix(sz):
            """'Contra' navy gradient + 'CORE' gold gradient — tek pixmap."""
            font = QFont('Coolvetica', sz, QFont.Bold)
            fm   = _QFM(font)
            cw   = fm.horizontalAdvance('Contra')
            ow   = fm.horizontalAdvance('CORE')
            h    = fm.height() + 4
            pix  = QPixmap(cw + ow + 4, h)
            pix.fill(Qt.transparent)
            p    = QPainter(pix)
            p.setRenderHint(QPainter.Antialiasing)
            # Contra — navy gradient
            pa1 = _QPP(); pa1.addText(2, fm.ascent() + 2, font, 'Contra')
            g1 = _QLG(0, 2, 0, h - 2)
            g1.setColorAt(0, QColor('#0a1e43')); g1.setColorAt(1, QColor('#081631'))
            p.setBrush(_QB(g1)); p.setPen(Qt.NoPen); p.drawPath(pa1)
            # CORE — gold gradient
            pa2 = _QPP(); pa2.addText(2 + cw, fm.ascent() + 2, font, 'CORE')
            g2 = _QLG(0, 2, 0, h - 2)
            g2.setColorAt(0, QColor('#c8a45b')); g2.setColorAt(1, QColor('#96732d'))
            p.setBrush(_QB(g2)); p.drawPath(pa2)
            p.end()
            return pix

        self._cc_lbl = QLabel()
        self._cc_lbl.setStyleSheet('background:transparent;border:none;')
        self._cc_lbl.setPixmap(_cc_pix(24))
        title_row.addWidget(self._cc_lbl)
        title_row.addStretch()

        title_col.addLayout(title_row)

        sub_lbl = QLabel('XML Fatura Otomasyonu')
        sub_lbl.setFont(QFont('Segoe UI', 14, QFont.Bold))
        sub_lbl.setStyleSheet(
            f'color:{TEXT}; background:transparent;border:none;letter-spacing:0.3px;'
        )
        title_col.addWidget(sub_lbl)
        left.addLayout(title_col)

        lay.addLayout(left)
        lay.addStretch(1)

        # ── SAĞ: Profil ───────────────────────────────────────────────────
        prof = QFrame()
        prof.setStyleSheet('''
            QFrame {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 #1E3660, stop:1 #162D4E);
                border-radius: 32px;
                border: 1.5px solid #C9A46A;
            }
            QFrame:hover {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 #253F6A, stop:1 #1E3660);
                border-color: #E4C285;
            }
        ''')
        _prof_glow = QGraphicsDropShadowEffect()
        _prof_glow.setBlurRadius(18)
        _prof_glow.setColor(QColor('#C9A46A55'))
        _prof_glow.setOffset(0, 2)
        prof.setGraphicsEffect(_prof_glow)

        pl = QHBoxLayout(prof)
        pl.setContentsMargins(14, 7, 14, 7)
        pl.setSpacing(10)

        p_img = QLabel()
        p_img.setFixedSize(46, 46)
        p_img.setStyleSheet('background:transparent;border:none;')
        px2 = QPixmap(ip('profile.png'))
        if not px2.isNull():
            canvas = QPixmap(46, 46)
            canvas.fill(Qt.transparent)
            pc = QPainter(canvas)
            pc.setRenderHint(QPainter.Antialiasing)
            scaled = px2.scaled(QSize(40, 40), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            clip = QPainterPath()
            clip.addEllipse(3.0, 3.0, 40.0, 40.0)
            pc.setClipPath(clip)
            pc.drawPixmap(3, 3, scaled)
            pc.setClipping(False)
            pc.setPen(QPen(QColor(GOLD), 2))
            pc.setBrush(Qt.NoBrush)
            pc.drawEllipse(QRectF(1, 1, 44, 44))
            from datetime import datetime as _dt2
            _now2 = _dt2.now()
            _online = (_now2.weekday() <= 5) and (9 <= _now2.hour < 17)
            _dot_color = GREEN if _online else RED
            pc.setPen(QPen(QColor('#FFFFFF'), 1.5))
            pc.setBrush(QColor(_dot_color))
            pc.drawEllipse(33, 33, 11, 11)
            pc.end()
            p_img.setPixmap(canvas)
        else:
            p_img.setText('👤')
        pl.addWidget(p_img)

        pt = QVBoxLayout()
        pt.setSpacing(1)
        pt.setContentsMargins(0, 0, 0, 0)
        n = QLabel('Serkan ŞAHİN')
        n.setStyleSheet(
            'font-size:12px;font-weight:700;color:#FFFFFF;background:transparent;border:none;'
        )
        r = QLabel('Geliştirici İletişim')
        r.setStyleSheet(
            f'font-size:10px;color:{GOLD};background:transparent;border:none;'
        )
        pt.addWidget(n)
        pt.addWidget(r)
        pl.addLayout(pt)

        arr = QLabel('▾')
        arr.setStyleSheet(
            'font-size:11px;color:#C9A46A;background:transparent;border:none;'
        )
        pl.addWidget(arr)

        prof.setCursor(Qt.PointingHandCursor)
        def _toggle_prof(e):
            if self._profile_popup._just_closed:
                return
            if self._profile_popup.isVisible():
                self._profile_popup.close()
            else:
                self._profile_popup.show_at(prof)
        prof.mousePressEvent = _toggle_prof
        lay.addWidget(prof)

        from core import theme as _theme
        self.btn_theme = _theme.make_toggle_button()
        self.btn_theme.clicked.connect(lambda: _theme.toggle())
        lay.addWidget(self.btn_theme)

        return f

    def _update_logo(self):
        import os as _os
        from core import theme as _t
        _LOGO_DIR = _os.path.join(_os.path.dirname(__file__), '..', '..', 'Logom', 'big_logo')
        fname = 'ContraCoreBeyaz.png' if _t.is_dark() else 'ContraCore.png'
        pix = QPixmap(_os.path.join(_LOGO_DIR, fname))
        if pix.isNull():
            pix = QPixmap(_os.path.join(_LOGO_DIR, 'ContraCore.png'))
        if not pix.isNull() and hasattr(self, '_lbl_logo'):
            h = self._logo_h
            w = int(pix.width() * h / pix.height())
            self._lbl_logo.setPixmap(pix.scaled(w, h, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        if hasattr(self, '_cc_lbl'):
            from PySide6.QtGui import QPainterPath as _QPP, QLinearGradient as _QLG, QBrush as _QB, QFontMetrics as _QFM
            def _cc_pix(sz):
                font = QFont('Coolvetica', sz, QFont.Bold)
                fm = _QFM(font)
                cw = fm.horizontalAdvance('Contra'); ow = fm.horizontalAdvance('CORE')
                h2 = fm.height() + 4
                p2 = QPixmap(cw + ow + 4, h2); p2.fill(Qt.transparent)
                pr = QPainter(p2); pr.setRenderHint(QPainter.Antialiasing)
                pa1 = _QPP(); pa1.addText(2, fm.ascent() + 2, font, 'Contra')
                g1 = _QLG(0, 2, 0, h2 - 2)
                if _t.is_dark():
                    g1.setColorAt(0, QColor('#FFFFFF')); g1.setColorAt(1, QColor('#E2E8F0'))
                else:
                    g1.setColorAt(0, QColor('#0a1e43')); g1.setColorAt(1, QColor('#081631'))
                pr.setBrush(_QB(g1)); pr.setPen(Qt.NoPen); pr.drawPath(pa1)
                pa2 = _QPP(); pa2.addText(2 + cw, fm.ascent() + 2, font, 'CORE')
                g2 = _QLG(0, 2, 0, h2 - 2)
                g2.setColorAt(0, QColor('#c8a45b')); g2.setColorAt(1, QColor('#96732d'))
                pr.setBrush(_QB(g2)); pr.drawPath(pa2); pr.end()
                return p2
            self._cc_lbl.setPixmap(_cc_pix(24))

    def _apply_theme(self):
        from core import theme as _theme
        if hasattr(self, 'btn_theme'):
            self.btn_theme.setText('☀️' if _theme.is_dark() else '🌙')
        self._update_logo()
        root = getattr(self, '_root_widget', None) or self.centralWidget()
        _theme.apply_to_widget(root)
        for attr in ('chk_recursive', 'chk_months', 'chk_open_folder', 'chk_open_excel'):
            btn = getattr(self, attr, None)
            if btn:
                self._toggle_btn_style(btn, btn.isChecked(), NAVY)

    # ── Klasörler ─────────────────────────────────────────────────────────────
    def _folders(self):
        f = self._card()
        lay = QVBoxLayout(f)
        lay.setContentsMargins(14, 14, 14, 14)
        lay.setSpacing(8)

        # Üst başlık + Tümünü Temizle
        top = QHBoxLayout()
        sec = QLabel('📁  KLASÖR SEÇİMİ')
        sec.setStyleSheet(
            f'font-size:14px;font-weight:700;color:{TEXT};'
            f'background:transparent;border:none;letter-spacing:0.5px;'
        )
        top.addWidget(sec)
        top.addStretch()

        btn_all = QPushButton('🗑  Tümünü Temizle')
        btn_all.setCursor(Qt.PointingHandCursor)
        btn_all.setStyleSheet(f'''
            QPushButton {{
                background: #F3F4F6; color: {TEXT2};
                border: 1px solid {BORDER}; border-radius: 8px;
                font-size: 11px; padding: 5px 12px;
            }}
            QPushButton:hover {{
                background: #FFE4E4; border-color: {RED}; color: {RED};
            }}
        ''')
        btn_all.clicked.connect(
            lambda: [fc.clear() for fc in (self.fc_a, self.fc_s, self.fc_c)]
        )
        top.addWidget(btn_all)
        lay.addLayout(top)

        self.fc_a = FolderCard('alis',  'ALIŞ (GELEN) FATURA KLASÖRÜ',  'inbox.png',  BLUE_BG)
        self.fc_s = FolderCard('satis', 'SATIŞ (GİDEN) FATURA KLASÖRÜ', 'outbox.png', ORG_BG)
        self.fc_c = FolderCard('cikti', 'EXCEL ÇIKTI KLASÖRÜ',           'excel.png',  GRN_BG, count_enabled=False)
        for fc in (self.fc_a, self.fc_s, self.fc_c):
            lay.addWidget(fc)

        # Alt klasör toggle + aylara ayır — aynı satırda
        prefs = load_prefs()
        opt_row = QHBoxLayout()

        self.chk_recursive = QPushButton('🗂  Alt klasörleri de tara')
        self.chk_recursive.setCheckable(True)
        self.chk_recursive.setChecked(prefs.get('recursive', False))
        self.chk_recursive.setCursor(Qt.PointingHandCursor)
        self.chk_recursive.setFixedHeight(30)
        self._apply_recursive_style()
        self.chk_recursive.toggled.connect(self._on_recursive_toggled)
        opt_row.addWidget(self.chk_recursive)

        opt_row.addStretch()

        self.chk_months = QPushButton('📅  Aylara Göre Ayır')
        self.chk_months.setCheckable(True)
        self.chk_months.setChecked(prefs.get('months_split', False))
        self.chk_months.setCursor(Qt.PointingHandCursor)
        self.chk_months.setFixedHeight(30)
        self.chk_months.toggled.connect(self._on_months_toggled)
        self._apply_months_style()
        opt_row.addWidget(self.chk_months)

        self.chk_open_folder = QPushButton('📂  Bitince Klasörü Aç')
        self.chk_open_folder.setCheckable(True)
        self.chk_open_folder.setChecked(prefs.get('open_folder_on_done', False))
        self.chk_open_folder.setCursor(Qt.PointingHandCursor)
        self.chk_open_folder.setFixedHeight(30)
        self.chk_open_folder.toggled.connect(self._on_open_folder_toggled)
        self._apply_open_folder_style()
        opt_row.addWidget(self.chk_open_folder)

        self.chk_open_excel = QPushButton('  Bitince Excel\'i Aç')
        self.chk_open_excel.setCheckable(True)
        self.chk_open_excel.setChecked(prefs.get('open_excel_on_done', False))
        self.chk_open_excel.setCursor(Qt.PointingHandCursor)
        self.chk_open_excel.setFixedHeight(30)
        _pix_xl = QPixmap(ip('excel.png'))
        if not _pix_xl.isNull():
            self.chk_open_excel.setIcon(
                QIcon(_pix_xl.scaled(16, 16, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            )
        self.chk_open_excel.toggled.connect(self._on_open_excel_toggled)
        self._apply_open_excel_style()
        opt_row.addWidget(self.chk_open_excel)
        lay.addLayout(opt_row)

        hint = QLabel('💡  Klasörü kartın üzerine sürükleyip bırakabilirsiniz')
        hint.setStyleSheet(
            f'font-size:10px;color:{TEXT3};background:transparent;border:none;'
        )
        lay.addWidget(hint)
        return f

    # ── Butonlar ──────────────────────────────────────────────────────────────
    def _buttons(self):
        f = QFrame()
        f.setStyleSheet('background:transparent;border:none;')
        lay = QHBoxLayout(f)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)

        self.btn_start = QPushButton('▶   BAŞLAT\nİşlemleri başlat')
        self.btn_start.setFixedHeight(64)
        self.btn_start.setCursor(Qt.PointingHandCursor)
        self._style_start_idle()

        self.btn_stop = QPushButton('■   DURDUR\nİşlemleri durdur')
        self.btn_stop.setFixedHeight(64)
        self.btn_stop.setCursor(Qt.PointingHandCursor)
        self.btn_stop.setEnabled(False)
        self.btn_stop.setStyleSheet(f'''
            QPushButton {{
                background: {RED}; color: #FFF;
                border-radius: 14px; border: none;
                font-size: 14px; font-weight: 800;
            }}
            QPushButton:hover {{ background: {RED2}; }}
            QPushButton:disabled {{
                background: #FEE2E2; color: #FCA5A5;
            }}
        ''')

        self.btn_start.clicked.connect(self._on_start_click)
        self.btn_stop.clicked.connect(self._stop)

        lay.addWidget(self.btn_start)
        lay.addWidget(self.btn_stop)
        return f

    def _toggle_btn_style(self, btn, checked, color_on, color_off=None):
        from core import theme as _t
        if _t.is_dark():
            bg      = 'rgba(201,164,106,0.25)' if checked else _t.DARK_CARD
            fg      = '#E4C285' if checked else _t.DARK_TEXT2
            border  = '#C9A46A' if checked else _t.DARK_BORDER
        else:
            c_off   = color_off or TEXT2
            bg      = 'rgba(11,31,58,0.1)' if checked else '#F3F4F6'
            fg      = NAVY if checked else c_off
            border  = NAVY if checked else BORDER
        btn.setStyleSheet(f'''
            QPushButton {{
                background: {bg}; color: {fg};
                border: 1.5px solid {border};
                border-radius: 8px; font-size:11px; font-weight:600;
                padding: 0 12px;
            }}
            QPushButton:hover {{
                background: rgba(201,164,106,0.2); border-color:#C9A46A;
            }}
        ''')

    def _apply_recursive_style(self):
        self._toggle_btn_style(self.chk_recursive, self.chk_recursive.isChecked(), NAVY)

    def _apply_months_style(self):
        self._toggle_btn_style(self.chk_months, self.chk_months.isChecked(), NAVY)

    def _on_recursive_toggled(self, checked):
        self._apply_recursive_style()
        for fc in (self.fc_a, self.fc_s, self.fc_c):
            fc.set_recursive(checked)
        prefs = load_prefs()
        prefs['recursive'] = checked
        save_prefs(prefs)

    def _on_months_toggled(self, checked):
        self._apply_months_style()
        prefs = load_prefs()
        prefs['months_split'] = checked
        save_prefs(prefs)

    def _apply_open_folder_style(self):
        self._toggle_btn_style(self.chk_open_folder, self.chk_open_folder.isChecked(), NAVY)

    def _on_open_folder_toggled(self, checked):
        self._apply_open_folder_style()
        prefs = load_prefs()
        prefs['open_folder_on_done'] = checked
        save_prefs(prefs)

    def _apply_open_excel_style(self):
        self._toggle_btn_style(self.chk_open_excel, self.chk_open_excel.isChecked(), NAVY)

    def _on_open_excel_toggled(self, checked):
        self._apply_open_excel_style()
        prefs = load_prefs()
        prefs['open_excel_on_done'] = checked
        save_prefs(prefs)

    def _style_start_idle(self):
        self.btn_start.setStyleSheet(f'''
            QPushButton {{
                background: {GREEN}; color: #FFF;
                border-radius: 14px; border: none;
                font-size: 14px; font-weight: 800;
            }}
            QPushButton:hover {{ background: {GREEN2}; }}
            QPushButton:disabled {{
                background: #D1FAE5; color: #86EFAC;
            }}
        ''')

    def _style_start_pause(self):
        self.btn_start.setStyleSheet(f'''
            QPushButton {{
                background: #F59E0B; color: #FFF;
                border-radius: 14px; border: none;
                font-size: 14px; font-weight: 800;
            }}
            QPushButton:hover {{ background: #D97706; }}
        ''')

    def _style_start_resume(self):
        self.btn_start.setStyleSheet(f'''
            QPushButton {{
                background: #2563EB; color: #FFF;
                border-radius: 14px; border: none;
                font-size: 14px; font-weight: 800;
            }}
            QPushButton:hover {{ background: #1D4ED8; }}
        ''')

    # ── İstatistikler ─────────────────────────────────────────────────────────
    def _stats(self):
        wrapper = QFrame()
        wrapper.setStyleSheet('background:transparent;border:none;')
        wlay = QVBoxLayout(wrapper)
        wlay.setContentsMargins(0, 0, 0, 0)
        wlay.setSpacing(6)

        cards = QFrame()
        cards.setStyleSheet('background:transparent;border:none;')
        lay = QHBoxLayout(cards)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)

        MUK_BG  = '#F5F3FF'
        MUK_CLR = '#7C3AED'

        self.sc_a = StatCard('ALIŞ',     '📥', BLUE_BG, '#1D4ED8')
        self.sc_s = StatCard('SATIŞ',    '📤', ORG_BG,  '#C2410C')
        self.sc_h = StatCard('HATA',     '⚠️', RED_BG,  RED,     'Hatalı dosya')
        self.sc_m = StatCard('MÜKERRER', '🔁', MUK_BG,  MUK_CLR, 'Tekrarlanan fatura')
        lay.addWidget(self.sc_a)
        lay.addWidget(self.sc_s)

        # HATA kartı + altında hata indirme butonu
        hata_col = QVBoxLayout()
        hata_col.setSpacing(4)
        hata_col.addWidget(self.sc_h)
        self.btn_err_dl = QPushButton('⬇  Hatalı Dosyaları İndir')
        self.btn_err_dl.setCursor(Qt.PointingHandCursor)
        self.btn_err_dl.setVisible(False)
        self.btn_err_dl.setStyleSheet(f'''
            QPushButton {{
                background: {RED_BG}; color: {RED};
                border: 1px solid {RED}; border-radius: 9px;
                font-size: 10px; font-weight: 600; padding: 5px 10px;
            }}
            QPushButton:hover {{ background: #FFE4E4; }}
        ''')
        self.btn_err_dl.clicked.connect(self._save_errors)
        hata_col.addWidget(self.btn_err_dl)
        lay.addLayout(hata_col)

        # MÜKERRER kartı + altında mükerrer indirme butonu
        muk_col = QVBoxLayout()
        muk_col.setSpacing(4)
        muk_col.addWidget(self.sc_m)
        self.btn_dup_dl = QPushButton('⬇  Mükerrer Faturaları İndir')
        self.btn_dup_dl.setCursor(Qt.PointingHandCursor)
        self.btn_dup_dl.setVisible(False)
        self.btn_dup_dl.setStyleSheet(f'''
            QPushButton {{
                background: {MUK_BG}; color: {MUK_CLR};
                border: 1px solid {MUK_CLR}; border-radius: 9px;
                font-size: 10px; font-weight: 600; padding: 5px 10px;
            }}
            QPushButton:hover {{ background: #EDE9FE; }}
        ''')
        self.btn_dup_dl.clicked.connect(self._save_duplicates)
        muk_col.addWidget(self.btn_dup_dl)
        lay.addLayout(muk_col)
        wlay.addWidget(cards)

        return wrapper

    # ── Progress ──────────────────────────────────────────────────────────────
    def _init_state_widgets(self):
        self.lbl_spinner = QLabel('')
        self.lbl_spinner.setStyleSheet(
            f'font-size:13px;color:{GREEN};background:transparent;border:none;'
        )
        self.lbl_pct = QLabel('')
        self.lbl_pct.setStyleSheet(
            f'font-size:10px;font-weight:700;color:{GREEN};background:transparent;border:none;'
        )
        self.pbar = QProgressBar()
        self.pbar.setRange(0, 1000)
        self.pbar.setValue(0)
        self.pbar.setFixedHeight(3)
        self.pbar.setTextVisible(False)
        self.pbar.setStyleSheet(f'''
            QProgressBar {{
                background:#1E293B; border-radius:0; border:none;
            }}
            QProgressBar::chunk {{
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 {GREEN}, stop:1 #16A34A);
                border-radius:0;
            }}
        ''')
        self.lbl_status  = QLabel('Hazır')
        self.lbl_eta_spd = QLabel('')
        self.lbl_current = QLabel('')

    # ── Log ───────────────────────────────────────────────────────────────────
    def _log(self):
        f = QFrame()
        f.setStyleSheet(
            f'QFrame{{background:{LOG_BG};border-radius:16px;border:none;}}'
        )
        lay = QVBoxLayout(f)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        hdr = QFrame()
        hdr.setStyleSheet(
            f'QFrame{{background:{LOG_BG};border-radius:0;border:none;'
            f'border-bottom:1px solid rgba(201,164,106,0.25);}}'
        )
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(16, 10, 12, 10)

        dot = QLabel('≡')
        dot.setStyleSheet(
            f'color:{GOLD};font-size:14px;font-weight:900;background:transparent;border:none;'
        )
        ttl = QLabel('İŞLEM GÜNLÜĞÜ')
        ttl.setStyleSheet(
            f'font-size:11px;font-weight:700;color:{GOLD};'
            f'letter-spacing:1px;background:transparent;border:none;'
        )
        btn_cls = QPushButton('🗑  Temizle')
        btn_cls.setCursor(Qt.PointingHandCursor)
        btn_cls.setStyleSheet(f'''
            QPushButton {{
                background: rgba(239,68,68,0.15); color: #EF4444;
                border: 1px solid rgba(239,68,68,0.3);
                border-radius: 8px; font-size: 10px; padding: 4px 10px;
            }}
            QPushButton:hover {{ background: rgba(239,68,68,0.3); }}
        ''')
        btn_cls.clicked.connect(lambda: self.log_box.clear())

        btn_rpt = QPushButton('📥  Raporu İndir')
        btn_rpt.setCursor(Qt.PointingHandCursor)
        btn_rpt.setStyleSheet(f'''
            QPushButton {{
                background: rgba(201,164,106,0.15); color: {GOLD};
                border: 1px solid rgba(201,164,106,0.4);
                border-radius: 8px; font-size: 10px; padding: 4px 10px;
            }}
            QPushButton:hover {{ background: rgba(201,164,106,0.3); }}
        ''')
        btn_rpt.clicked.connect(self._save_report)

        hl.addWidget(dot)
        hl.addSpacing(6)
        hl.addWidget(self.lbl_spinner)
        hl.addWidget(ttl, 1)
        hl.addWidget(self.lbl_pct)
        hl.addSpacing(6)
        hl.addWidget(btn_rpt)
        hl.addSpacing(6)
        hl.addWidget(btn_cls)
        lay.addWidget(hdr)
        lay.addWidget(self.pbar)

        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setStyleSheet(f'''
            QTextEdit {{
                background: {LOG_BG}; color: #CBD5E1;
                border: none; font-family: Consolas, monospace;
                font-size: 10px; padding: 10px;
            }}
            QScrollBar:vertical {{
                background: {LOG_BG}; width: 5px;
            }}
            QScrollBar::handle:vertical {{
                background: #334155; border-radius: 2px;
            }}
        ''')
        lay.addWidget(self.log_box)
        return f

    # ── Footer ────────────────────────────────────────────────────────────────
    def _footer(self):
        f = QFrame()
        f.setStyleSheet('background:transparent;border:none;')
        lay = QHBoxLayout(f)
        lay.setContentsMargins(4, 0, 4, 0)

        self.lbl_sys = QLabel('● Sistem Hazır')
        self.lbl_sys.setStyleSheet(
            f'font-size:10px;color:{GREEN};background:transparent;border:none;'
        )
        self.lbl_meta = QLabel('')
        self.lbl_meta.setStyleSheet(
            f'font-size:10px;color:{TEXT3};background:transparent;border:none;'
        )
        lay.addWidget(self.lbl_sys)
        lay.addStretch()
        lay.addWidget(self.lbl_meta)

        # Son işlem özetini preferences'tan yükle
        last = load_prefs().get('last_summary')
        if last:
            self.lbl_meta.setText(
                f'Son işlem: {last.get("date","")}  |  '
                f'Alış: {last.get("alis",0)}  Satış: {last.get("satis",0)}  '
                f'Hata: {last.get("hata",0)}  |  Süre: {last.get("sure","")}'
            )
        return f

    # ── Spinner ───────────────────────────────────────────────────────────────
    def _spin_tick(self):
        self.lbl_spinner.setText(self._spin_frames[self._spin_idx % len(self._spin_frames)])
        self._spin_idx += 1

    # ── Buton tıklama yönetimi ────────────────────────────────────────────────
    def _on_start_click(self):
        if not self._running:
            self._start()
        else:
            self._toggle_pause()

    def _stop(self):
        # Mevcut konumu kaydet — BAŞLAT'a basınca oradan devam edilir
        self._resume_alis  = self._cur_alis
        self._resume_satis = self._cur_satis
        self.stop_flag.set()
        self.pause_flag.clear()
        self.is_paused  = False
        self._running   = False
        self.btn_start.setText('▶   DEVAM ET\nKaldığı yerden devam')
        self._style_start_resume()
        self.btn_stop.setEnabled(False)
        self._spin_timer.stop()
        self.lbl_spinner.setText('')
        self.lbl_sys.setText('● Durduruldu — DEVAM ET ile kaldığı yerden devam')
        self.lbl_sys.setStyleSheet(
            f'font-size:10px;color:#FB923C;background:transparent;border:none;'
        )
        self._log_append(
            f'⏹  Durduruldu  (Alış: {self._cur_alis}, Satış: {self._cur_satis} işlendi).  '
            f'DEVAM ET ile kaldığı yerden devam edebilirsiniz.', 'warn'
        )

    def _toggle_pause(self):
        if not self.is_paused:
            self.pause_flag.set()
            self.is_paused = True
            self.btn_start.setText('▶   DEVAM ET\nİşlemi sürdür')
            self._style_start_resume()
            self._spin_timer.stop()
            self.lbl_spinner.setText('')
            self.lbl_sys.setText('● Duraklatıldı')
            self.lbl_sys.setStyleSheet(
                f'font-size:10px;color:#FB923C;background:transparent;border:none;'
            )
            self._log_append('⏸  Duraklatıldı.', 'warn')
        else:
            self.pause_flag.clear()
            self.is_paused = False
            self.btn_start.setText('⏸   DURAKLAT\nİşlemi duraklat')
            self._style_start_pause()
            self._spin_timer.start()
            self.lbl_sys.setText('● İşlem Devam Ediyor...')
            self.lbl_sys.setStyleSheet(
                f'font-size:10px;color:{GOLD};background:transparent;border:none;'
            )
            self._log_append('▶  Devam ediliyor...', 'ok')

    # ── İşlem başlat ──────────────────────────────────────────────────────────
    def _start(self):
        alis  = self.fc_a.get_path()
        satis = self.fc_s.get_path()
        cikti = self.fc_c.get_path()

        if not alis and not satis:
            QMessageBox.warning(self, 'Uyarı', 'En az bir fatura klasörü seçin!')
            return
        if not cikti:
            cikti = os.path.join(os.path.expanduser('~'), 'Desktop')
            self.fc_c.set_path(cikti)
            self._log_append(f'📂  Çıktı klasörü otomatik seçildi: Masaüstü', 'info')

        # PDF uyarısı — seçili klasörlerde PDF varsa bildir
        _pdf_found = False
        for _folder in [alis, satis]:
            if _folder and os.path.isdir(_folder):
                for _fn in os.listdir(_folder):
                    if _fn.lower().endswith('.pdf'):
                        _pdf_found = True
                        break
            if _pdf_found:
                break
        if _pdf_found and not load_prefs().get('pdf_warning_skip', False):
            self._show_pdf_warning_dialog()

        self.stop_flag.clear()
        self.pause_flag.clear()
        self.is_paused = False
        self._running  = True
        self._t0       = time.time()

        self.btn_start.setText('⏸   DURAKLAT\nİşlemi duraklat')
        self._style_start_pause()
        self.btn_stop.setEnabled(True)

        resuming = (self._resume_alis > 0 or self._resume_satis > 0)
        if not resuming:
            # Taze başlangıç — her şeyi sıfırla
            self._error_files     = []
            self._duplicate_files = []
            self._last_totals     = (0.0, 0.0, 0.0, 0.0)
            self.btn_err_dl.setVisible(False)
            self.btn_dup_dl.setVisible(False)
            self.sc_m.reset()
            self.pbar.setValue(0)
            self.lbl_pct.setText('0%')
            self._last_logged_pct = -1
            self.sc_a.reset()
            self.sc_s.reset()
            self.sc_h.reset()
            self.log_box.clear()
            self._log_append('═' * 50, 'head')
            self._log_append('  XML FATURA OTOMASYONU — BAŞLADI', 'head')
            self._log_append(f'  {datetime.now().strftime("%d.%m.%Y  %H:%M:%S")}', 'info')
            self._log_append('═' * 50, 'head')
        else:
            self._log_append('▶  Kaldığı yerden devam ediliyor...', 'warn')

        self._spin_idx = 0
        self._spin_timer.start()

        self.lbl_sys.setText('● İşlem Devam Ediyor...')
        self.lbl_sys.setStyleSheet(
            f'font-size:10px;color:{GOLD};background:transparent;border:none;'
        )

        # Deneme sürümü dosya limiti kontrolü
        max_files_trial = None
        self._trial_quota = None  # cache for _on_stats — computed once here
        if self._trial_status:
            from license import get_trial_status
            aktif, kalan_gun, islenen, kalan = get_trial_status()
            if not aktif:
                QMessageBox.warning(self, 'Deneme Süresi Doldu',
                    'Deneme süreniz doldu. Lütfen lisans satın alın.')
                self._reset_ui_idle()
                return
            if kalan > 0:
                # Tahmini toplam dosya sayısı
                import os as _os
                from cc_modules.xml_fatura.main import _collect_files
                rec = self.chk_recursive.isChecked()
                est = (len(_collect_files(alis, recursive=rec))
                       + len(_collect_files(satis, recursive=rec)))
                if est > kalan:
                    ret = QMessageBox.question(
                        self, 'Deneme Limiti',
                        f'Deneme limitiniz <b>{kalan} dosya</b> kaldı, '
                        f'bu işlemde <b>{est} dosya</b> var.<br><br>'
                        f'Sadece ilk <b>{kalan} dosya</b> işlenecek. '
                        f'Devam etmek istiyor musunuz?',
                        QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes
                    )
                    if ret != QMessageBox.Yes:
                        self._reset_ui_idle()
                        return
                max_files_trial = kalan
            self._trial_quota = islenen + kalan  # cache quota for _on_stats

        self.worker = Worker(
            alis, satis, cikti,
            self.stop_flag, self.pause_flag,
            alis_start=self._resume_alis,
            satis_start=self._resume_satis,
            months_split=self.chk_months.isChecked(),
            recursive=self.chk_recursive.isChecked(),
            max_files=max_files_trial,
        )
        self.worker.sig.log.connect(self._on_log)
        self.worker.sig.progress.connect(self._on_prog)
        self.worker.sig.stats.connect(self._on_stats)
        self.worker.sig.status.connect(self.lbl_status.setText)
        self.worker.sig.current.connect(self._on_current)
        self.worker.sig.eta.connect(self._on_eta)
        self.worker.sig.done.connect(self._on_done)
        self.worker.sig.totals.connect(self._on_totals)
        self.worker.sig.error_file.connect(self._on_error_file)
        self.worker.sig.duplicate_file.connect(self._on_duplicate_file)
        self.worker.start()
        # Resume indekslerini temizle — tamamlanınca veya yeni başlatmada açılır
        self._resume_alis  = 0
        self._resume_satis = 0

    # ── Callback Slotlar ──────────────────────────────────────────────────────
    @Slot(float)
    def _on_prog(self, v):
        self.pbar.setValue(int(v * 1000))
        pct = int(v * 100)
        self.lbl_pct.setText(f'{pct}%')
        # Her 10%'de bir milestone log satırı
        if not hasattr(self, '_last_logged_pct'):
            self._last_logged_pct = -1
        milestone = (pct // 10) * 10
        if milestone > self._last_logged_pct and pct >= milestone and milestone > 0:
            self._last_logged_pct = milestone
            self._log_append(f'  ▸  İlerleme: %{milestone}', 'info')

    @Slot(int, int, int, int, int, int)
    def _on_stats(self, ad, at, sd, st, h, muk):
        self._cur_alis  = ad
        self._cur_satis = sd
        if self._trial_status:
            _quota = self._trial_quota or 1  # cached at _start() — no storage reads per signal
            self.sc_a.update(ad, _quota)
            self.sc_s.update(sd, _quota)
            self.sc_h.update(h,  _quota)
            self.sc_m.update(muk, _quota)
            if self.donut_widget is not None:
                self.donut_widget.set_values(ad + sd, _quota)
        else:
            self.sc_a.update(ad, at)
            self.sc_s.update(sd, st)
            self.sc_h.update(h, at + st)
            self.sc_m.update(muk, at + st)

    @Slot(str)
    def _on_current(self, fn):
        s = fn if len(fn) <= 56 else '…' + fn[-54:]
        self.lbl_current.setText(f'↳  {s}')

    @Slot(float, str, str)
    def _on_eta(self, speed, dur, tstr):
        self.lbl_eta_spd.setText(f'⚡ {speed:.0f} dosya/dk  |  ⏱ {dur}  |  🏁 {tstr}')

    # ── Otomatik Güncelleme ───────────────────────────────────────────────────
    def _start_update_check(self):
        self._upd_checker = UpdateChecker()
        self._upd_checker.update_available.connect(self._on_update_available)
        self._upd_checker.check_failed.connect(self._on_update_failed)
        self._upd_checker.start()

    @Slot(str)
    def _on_update_available(self, version):
        self._latest_version = version
        if hasattr(self, 'banner_update'):
            self.lbl_banner_text.setText(f'🔄  v{version} güncellemesi mevcut!')
            self.banner_update.setVisible(True)
        # Program açılışında bir kez otomatik popup göster
        QTimer.singleShot(800, self._show_update_dialog)

    @Slot(str)
    def _on_update_failed(self, err):
        # Sessizce logla — kullanıcıya gösterme ama konsol/log'da görünsün
        import sys
        print(f'[UpdateChecker] Hata: {err}', file=sys.stderr)

    def _show_pdf_warning_dialog(self):
        dlg = QDialog(self)
        dlg.setWindowTitle('PDF Dosyası Tespit Edildi')
        dlg.setFixedSize(420, 230)
        dlg.setStyleSheet(f'QDialog{{background:{CARD};}}')
        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(28, 24, 28, 20)
        lay.setSpacing(10)

        ico = QLabel('⚠️')
        ico.setAlignment(Qt.AlignCenter)
        ico.setStyleSheet('font-size:34px;background:transparent;border:none;')
        lay.addWidget(ico)

        ttl = QLabel('PDF Fatura Uyarısı')
        ttl.setAlignment(Qt.AlignCenter)
        ttl.setStyleSheet(
            f'font-size:14px;font-weight:800;color:{NAVY};background:transparent;border:none;'
        )
        lay.addWidget(ttl)

        sub = QLabel(
            'Seçili klasörde PDF fatura dosyaları tespit edildi.\n'
            'PDF faturaların okunması bazı durumlarda eksik veya\n'
            'hatalı sonuç verebilir. İşlem bittikten sonra lütfen\n'
            'PDF kaynaklı satırları Excel\'de kontrol ediniz.'
        )
        sub.setAlignment(Qt.AlignCenter)
        sub.setStyleSheet(
            f'font-size:11px;color:{TEXT2};background:transparent;border:none;'
        )
        lay.addWidget(sub)

        chk_skip = QCheckBox('Bir daha gösterme')
        chk_skip.setStyleSheet(
            f'font-size:10px;color:{TEXT2};background:transparent;border:none;'
        )
        chk_skip.setChecked(False)
        lay.addWidget(chk_skip, 0, Qt.AlignCenter)

        btn_ok = QPushButton('  Anladım, Devam Et')
        btn_ok.setFixedHeight(38)
        btn_ok.setCursor(Qt.PointingHandCursor)
        btn_ok.setStyleSheet(f'''
            QPushButton{{background:{GOLD};color:#FFF;
                border:none;border-radius:9px;
                font-size:12px;font-weight:700;}}
            QPushButton:hover{{background:#b8933d;}}
        ''')
        btn_ok.clicked.connect(dlg.accept)
        lay.addWidget(btn_ok)

        dlg.exec()
        if chk_skip.isChecked():
            p = load_prefs()
            p['pdf_warning_skip'] = True
            save_prefs(p)

    def _show_update_dialog(self):
        if not self._latest_version:
            return
        dlg = QDialog(self)
        dlg.setWindowTitle('Güncelleme Mevcut')
        dlg.setFixedSize(400, 210)
        dlg.setStyleSheet(f'QDialog{{background:{CARD};}}')
        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(28, 24, 28, 20)
        lay.setSpacing(12)

        ico = QLabel('🔄')
        ico.setAlignment(Qt.AlignCenter)
        ico.setStyleSheet('font-size:34px;background:transparent;border:none;')
        lay.addWidget(ico)

        ttl = QLabel(f'v{self._latest_version} Güncellemesi Mevcut')
        ttl.setAlignment(Qt.AlignCenter)
        ttl.setStyleSheet(
            f'font-size:14px;font-weight:800;color:{NAVY};background:transparent;border:none;'
        )
        lay.addWidget(ttl)

        sub = QLabel(
            f'v{self._latest_version} sürümü hazır. Şimdi güncellensin mi?\n'
            f'Program kapanıp yeniden açılacak.'
        )
        sub.setAlignment(Qt.AlignCenter)
        sub.setStyleSheet(
            f'font-size:11px;color:{TEXT2};background:transparent;border:none;'
        )
        lay.addWidget(sub)

        btn_row = QHBoxLayout()
        btn_later = QPushButton('Daha Sonra')
        btn_later.setFixedHeight(38)
        btn_later.setCursor(Qt.PointingHandCursor)
        btn_later.setStyleSheet(f'''
            QPushButton{{background:#F3F4F6;color:{TEXT2};
                border:1px solid {BORDER};border-radius:9px;
                font-size:12px;font-weight:600;}}
            QPushButton:hover{{background:#E5E7EB;}}
        ''')
        btn_later.clicked.connect(dlg.reject)

        btn_go = QPushButton('  Güncelle')
        btn_go.setFixedHeight(38)
        btn_go.setCursor(Qt.PointingHandCursor)
        btn_go.setStyleSheet(f'''
            QPushButton{{background:{GREEN};color:#FFF;
                border:none;border-radius:9px;
                font-size:12px;font-weight:700;}}
            QPushButton:hover{{background:{GREEN2};}}
        ''')
        btn_go.clicked.connect(dlg.accept)

        btn_row.addWidget(btn_later)
        btn_row.addWidget(btn_go)
        lay.addLayout(btn_row)

        if dlg.exec() == QDialog.Accepted:
            self._do_update()

    def _do_update(self):
        import subprocess

        if not getattr(sys, 'frozen', False):
            QMessageBox.information(self, 'Güncelleme', 'Geliştirici modu — Updater.exe atlandı.')
            return

        # Updater.exe ana EXE ile aynı klasörde
        current_exe  = sys.executable
        updater_exe  = os.path.join(os.path.dirname(current_exe), 'Updater.exe')

        if not os.path.exists(updater_exe):
            QMessageBox.warning(
                self, 'Güncelleme Hatası',
                'Updater.exe bulunamadı. Lütfen programı yeniden kurun.'
            )
            return

        try:
            subprocess.Popen(
                [updater_exe, current_exe, str(os.getpid())],
                creationflags=subprocess.DETACHED_PROCESS
            )
            QApplication.quit()
        except Exception as e:
            QMessageBox.warning(self, 'Güncelleme Hatası', str(e))

    def _open_activation(self):
        from activation import ActivationWindow
        win = ActivationWindow(parent=self)
        win.exec()
        if win.activated:
            from license import check_license
            valid, msg, expire = check_license()
            if valid:
                self.expire_date   = expire
                self._trial_status = None
                self._build()   # header'ı yenile

    def _reset_ui_idle(self):
        """İşlem başlamadan önce UI'yi idle durumuna sıfırla."""
        self._running  = False
        self.is_paused = False
        self.btn_start.setText('▶   BAŞLAT\nİşlemleri başlat')
        self._style_start_idle()
        self.btn_stop.setEnabled(False)
        self._spin_timer.stop()
        self.lbl_spinner.setText('')

    @Slot(float, float, float, float)
    def _on_totals(self, am, at2, sm, st2):
        self._last_totals = (am, at2, sm, st2)

    @Slot(int, int, int, int, int, int, int)
    def _on_done(self, a, s, h, at, st, new_count, muk):
        elapsed  = time.time() - (self._t0 or time.time())
        m, sec   = divmod(int(elapsed), 60)
        self._running  = False
        self.is_paused = False
        # Tamamlandı — resume konumlarını temizle
        self._resume_alis  = 0
        self._resume_satis = 0
        self._cur_alis     = 0
        self._cur_satis    = 0

        # Deneme kullanımını güncelle
        if self._trial_status and new_count > 0:
            from license import add_trial_usage, get_trial_status, TRIAL_MAX_FILES as _TMAX
            add_trial_usage(new_count)
            _, kalan_gun, islened2, _ = get_trial_status()
            if hasattr(self, 'lbl_trial'):
                self.lbl_trial.setText(
                    f'⏳  Deneme: {kalan_gun} gün  |  {islened2}/{_TMAX} dosya'
                )
            if self.donut_widget is not None:
                self.donut_widget.set_values(islened2, _TMAX)

        self.btn_start.setText('▶   BAŞLAT\nİşlemleri başlat')
        self._style_start_idle()
        self.btn_stop.setEnabled(False)

        self._spin_timer.stop()
        self.lbl_spinner.setText('')

        self.pbar.setValue(1000)
        self.lbl_pct.setText('100%')
        self.lbl_current.setText('')
        self.lbl_eta_spd.setText(f'⏱ Toplam süre: {m:02d}dk {sec:02d}sn')

        self._log_append('═' * 50, 'head')
        self._log_append('  İŞLEM TAMAMLANDI  ✓', 'head')
        self._log_append('═' * 50, 'head')

        self.lbl_sys.setText('● Tamamlandı')
        self.lbl_sys.setStyleSheet(
            f'font-size:10px;color:{GREEN};background:transparent;border:none;'
        )
        now = datetime.now().strftime('%d.%m.%Y %H:%M')
        sure_str = f'{m:02d}dk {sec:02d}sn'
        self.lbl_meta.setText(
            f'Son işlem: {now}  |  Alış: {a}  Satış: {s}  Hata: {h}  |  Süre: {sure_str}'
        )
        # Son işlemi preferences'a kaydet
        _p = load_prefs()
        _p['last_summary'] = {'date': now, 'alis': a, 'satis': s, 'hata': h, 'sure': sure_str}
        save_prefs(_p)

        # Hatalı ve mükerrer dosya butonları
        if self._error_files:
            self.btn_err_dl.setVisible(True)
        if self._duplicate_files:
            self.btn_dup_dl.setVisible(True)

        # Windows bildirimi
        msg  = f'{a + s} XML işlendi.' if h == 0 else f'{a + s} işlendi, {h} hata.'
        icon = QSystemTrayIcon.Information if h == 0 else QSystemTrayIcon.Warning
        self._tray.showMessage(
            '✅ Tamamlandı' if h == 0 else '⚠️ Uyarı',
            msg, icon, 4000
        )

        # ── Tamamlanma popup'u ───────────────────────────────────────────────
        dlg = QDialog(self)
        dlg.setWindowTitle('İşlem Tamamlandı')
        dlg.setFixedWidth(380)
        dlg.setStyleSheet(f'background:{CARD};')
        dlg_lay = QVBoxLayout(dlg)
        dlg_lay.setContentsMargins(28, 24, 28, 20)
        dlg_lay.setSpacing(12)

        ico_lbl = QLabel('✅' if h == 0 else '⚠️')
        ico_lbl.setAlignment(Qt.AlignCenter)
        ico_lbl.setStyleSheet('font-size:42px;background:transparent;border:none;')
        dlg_lay.addWidget(ico_lbl)

        ttl_lbl = QLabel('İŞLEM TAMAMLANDI')
        ttl_lbl.setAlignment(Qt.AlignCenter)
        ttl_lbl.setStyleSheet(
            f'font-size:15px;font-weight:800;color:{NAVY};background:transparent;border:none;'
        )
        dlg_lay.addWidget(ttl_lbl)

        sep = QFrame(); sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet(f'background:{BORDER};border:none;max-height:1px;')
        dlg_lay.addWidget(sep)

        _am, _at2, _sm, _st2 = self._last_totals

        def _tl(v):
            return f'{v:,.2f} ₺'.replace(',', '.')

        def _add_row(label, value, color=None):
            row = QHBoxLayout()
            lbl_k = QLabel(label)
            lbl_k.setStyleSheet(
                f'font-size:11px;color:{TEXT2};background:transparent;border:none;'
            )
            vc = color or TEXT
            lbl_v = QLabel(value)
            lbl_v.setStyleSheet(
                f'font-size:11px;font-weight:700;color:{vc};background:transparent;border:none;'
            )
            row.addWidget(lbl_k)
            row.addStretch()
            row.addWidget(lbl_v)
            dlg_lay.addLayout(row)

        for label, value in [
            ('Alış faturaları',   f'{a} dosya'),
            ('Satış faturaları',  f'{s} dosya'),
            ('Hatalı dosya',      f'{h} dosya'),
            ('Mükerrer fatura',   f'{muk} dosya'),
            ('Toplam süre',       f'{m:02d}dk {sec:02d}sn'),
            ('Tamamlanma saati',  now),
        ]:
            _add_row(label, value)

        # Tutar özeti — yalnızca veri varsa göster
        if _am > 0 or _sm > 0:
            sep_t = QFrame(); sep_t.setFrameShape(QFrame.HLine)
            sep_t.setStyleSheet(f'background:{BORDER};border:none;max-height:1px;')
            dlg_lay.addWidget(sep_t)
            if _am > 0:
                _alis_kdv = round(_at2 - _am, 2)
                _add_row('Alış Matrah',   _tl(_am))
                _add_row('Alış KDV',      _tl(_alis_kdv))
                _add_row('Alış Toplam',   _tl(_at2), GREEN2)
            if _sm > 0:
                _satis_kdv = round(_st2 - _sm, 2)
                _add_row('Satış Matrah',  _tl(_sm))
                _add_row('Satış KDV',     _tl(_satis_kdv))
                _add_row('Satış Toplam',  _tl(_st2), '#1D4ED8')

        _cikti = self.fc_c.get_path()

        def _find_latest_xl(pattern):
            import glob as _glob
            if not _cikti:
                return ''
            hits = _glob.glob(os.path.join(_cikti, pattern))
            return max(hits, key=os.path.getmtime) if hits else ''

        _xl_alis_path  = _find_latest_xl('Indirilecek_KDV_Listesi_*.xlsx')
        _xl_satis_path = _find_latest_xl('Satis_Fatura_Listesi_*.xlsx')
        _show_alis_btn  = a > 0 and bool(_xl_alis_path)
        _show_satis_btn = s > 0 and bool(_xl_satis_path)

        if _show_alis_btn or _show_satis_btn:
            sep_xl = QFrame(); sep_xl.setFrameShape(QFrame.HLine)
            sep_xl.setStyleSheet(f'background:{BORDER};border:none;max-height:1px;')
            dlg_lay.addWidget(sep_xl)

            xl_lbl = QLabel('Excel Dosyaları')
            xl_lbl.setAlignment(Qt.AlignCenter)
            xl_lbl.setStyleSheet(
                f'font-size:10px;color:{TEXT3};background:transparent;border:none;'
            )
            dlg_lay.addWidget(xl_lbl)

            _pix_xl_p = QPixmap(ip('excel.png'))
            _xl_ico_p = QIcon(_pix_xl_p.scaled(15, 15, Qt.KeepAspectRatio, Qt.SmoothTransformation)) \
                        if not _pix_xl_p.isNull() else QIcon()
            _xl_btn_st = f'''
                QPushButton {{
                    background:#F0FDF4; color:#15803D;
                    border:1.5px solid #86EFAC; border-radius:9px;
                    font-size:11px; font-weight:700; padding:0 10px;
                }}
                QPushButton:hover {{ background:#DCFCE7; border-color:#4ADE80; }}
            '''
            xl_row = QHBoxLayout()
            xl_row.setSpacing(8)

            if _show_alis_btn:
                btn_xl_a = QPushButton('  Alış Excel\'i Aç')
                btn_xl_a.setFixedHeight(36)
                btn_xl_a.setCursor(Qt.PointingHandCursor)
                btn_xl_a.setIcon(_xl_ico_p)
                btn_xl_a.setIconSize(QSize(16, 16))
                btn_xl_a.setStyleSheet(_xl_btn_st)
                btn_xl_a.clicked.connect(lambda: os.startfile(_xl_alis_path))
                xl_row.addWidget(btn_xl_a)

            if _show_satis_btn:
                btn_xl_s = QPushButton('  Satış Excel\'i Aç')
                btn_xl_s.setFixedHeight(36)
                btn_xl_s.setCursor(Qt.PointingHandCursor)
                btn_xl_s.setIcon(_xl_ico_p)
                btn_xl_s.setIconSize(QSize(16, 16))
                btn_xl_s.setStyleSheet(_xl_btn_st)
                btn_xl_s.clicked.connect(lambda: os.startfile(_xl_satis_path))
                xl_row.addWidget(btn_xl_s)

            dlg_lay.addLayout(xl_row)

        if _cikti and os.path.isdir(_cikti):
            sep_f = QFrame(); sep_f.setFrameShape(QFrame.HLine)
            sep_f.setStyleSheet(f'background:{BORDER};border:none;max-height:1px;')
            dlg_lay.addWidget(sep_f)

            _pix_folder = QPixmap(ip('folder.png'))
            btn_folder = QPushButton('  Çıktı Klasörünü Aç')
            btn_folder.setFixedHeight(36)
            btn_folder.setCursor(Qt.PointingHandCursor)
            if not _pix_folder.isNull():
                btn_folder.setIcon(QIcon(_pix_folder.scaled(16, 16, Qt.KeepAspectRatio, Qt.SmoothTransformation)))
                btn_folder.setIconSize(QSize(16, 16))
            btn_folder.setStyleSheet(f'''
                QPushButton {{
                    background:#EFF6FF; color:#1D4ED8;
                    border:1.5px solid #93C5FD; border-radius:9px;
                    font-size:11px; font-weight:700; padding:0 10px;
                }}
                QPushButton:hover {{ background:#DBEAFE; border-color:#60A5FA; }}
            ''')
            btn_folder.clicked.connect(lambda: os.startfile(_cikti))
            dlg_lay.addWidget(btn_folder)

        btn_ok = QPushButton('Tamam')
        btn_ok.setFixedHeight(40)
        btn_ok.setCursor(Qt.PointingHandCursor)
        btn_ok.setStyleSheet(f'''
            QPushButton {{
                background:{GREEN};color:#FFF;border-radius:10px;
                border:none;font-size:13px;font-weight:700;
            }}
            QPushButton:hover {{ background:{GREEN2}; }}
        ''')
        btn_ok.clicked.connect(dlg.accept)
        dlg_lay.addWidget(btn_ok)
        dlg.exec()

        _prefs_done = load_prefs()
        if _cikti and os.path.isdir(_cikti) and _prefs_done.get('open_folder_on_done', False):
            os.startfile(_cikti)
        if _cikti and _prefs_done.get('open_excel_on_done', False):
            if a > 0 and os.path.exists(_xl_alis_path):
                os.startfile(_xl_alis_path)
            if s > 0 and os.path.exists(_xl_satis_path):
                os.startfile(_xl_satis_path)

    LOG_CLR = {
        'ok':   '#4DCC78',
        'err':  '#FF5C5C',
        'warn': '#FFB84D',
        'info': '#7EB3D8',
        'head': '#C9A84C',
    }

    @Slot(str, str)
    def _on_log(self, msg, tag='info'):
        self._log_append(msg, tag)

    @Slot(str, str)
    def _on_error_file(self, fname, err):
        self._error_files.append((fname, err))

    def _save_errors(self):
        if not self._error_files:
            return
        desktop = os.path.join(os.path.expanduser('~'), 'Desktop')
        os.makedirs(desktop, exist_ok=True)
        path = os.path.join(desktop, 'hatali_dosyalar.txt')
        try:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(f'Hatalı Fatura Listesi — {datetime.now().strftime("%d.%m.%Y %H:%M")}\n')
                f.write('=' * 60 + '\n')
                for i, (fname, err) in enumerate(self._error_files, 1):
                    f.write(f'{i:3}. {os.path.basename(fname)}\n     Hata: {err}\n')
            self._log_append('✅  Masaüstüne kaydedildi: hatali_dosyalar.txt', 'ok')
            self._show_save_popup('Hatalı Dosyalar Kaydedildi',
                                  f'{len(self._error_files)} hatalı dosya listesi\nmasaüstüne kaydedildi.',
                                  path, RED)
        except Exception as e:
            self._log_append(f'❌  Kayıt hatası: {e}', 'err')

    def _save_duplicates(self):
        if not self._duplicate_files:
            return
        desktop = os.path.join(os.path.expanduser('~'), 'Desktop')
        os.makedirs(desktop, exist_ok=True)
        path = os.path.join(desktop, 'mukerrer_faturalar.txt')
        try:
            # Her inv_id'yi bir kez yaz (ilk görülen)
            seen_ids = set()
            unique_dupes = []
            for fname, inv_id in self._duplicate_files:
                if inv_id not in seen_ids:
                    seen_ids.add(inv_id)
                    unique_dupes.append((fname, inv_id))

            with open(path, 'w', encoding='utf-8') as f:
                f.write(f'Mükerrer Fatura Listesi — {datetime.now().strftime("%d.%m.%Y %H:%M")}\n')
                f.write('=' * 60 + '\n\n')
                for i, (fname, inv_id) in enumerate(unique_dupes, 1):
                    f.write(f'{i:3}. Fatura No: {inv_id}\n')
                    f.write(f'     Dosya   : {os.path.basename(fname)}\n\n')
            self._log_append('✅  Masaüstüne kaydedildi: mukerrer_faturalar.txt', 'ok')
            self._show_save_popup('Mükerrer Faturalar Kaydedildi',
                                  f'{len(self._duplicate_files)} mükerrer fatura\nmasaüstüne kaydedildi.',
                                  path, '#7C3AED')
        except Exception as e:
            self._log_append(f'❌  Kayıt hatası: {e}', 'err')

    def _show_save_popup(self, title, message, filepath, accent_color):
        dlg = QDialog(self)
        dlg.setWindowTitle(title)
        dlg.setFixedWidth(360)
        dlg.setStyleSheet(f'background:{CARD};')
        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(24, 20, 24, 18)
        lay.setSpacing(10)

        ico = QLabel('✅')
        ico.setAlignment(Qt.AlignCenter)
        ico.setStyleSheet('font-size:36px;background:transparent;border:none;')
        lay.addWidget(ico)

        ttl = QLabel(title)
        ttl.setAlignment(Qt.AlignCenter)
        ttl.setStyleSheet(
            f'font-size:13px;font-weight:800;color:{NAVY};background:transparent;border:none;'
        )
        lay.addWidget(ttl)

        msg = QLabel(message)
        msg.setAlignment(Qt.AlignCenter)
        msg.setStyleSheet(
            f'font-size:11px;color:{TEXT2};background:transparent;border:none;'
        )
        lay.addWidget(msg)

        sep = QFrame(); sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet(f'background:{BORDER};border:none;max-height:1px;')
        lay.addWidget(sep)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        btn_ok = QPushButton('Tamam')
        btn_ok.setFixedHeight(36)
        btn_ok.setCursor(Qt.PointingHandCursor)
        btn_ok.setStyleSheet(f'''
            QPushButton {{background:#F3F4F6;color:{TEXT};border:1px solid {BORDER};
                border-radius:9px;font-size:11px;font-weight:600;}}
            QPushButton:hover {{background:#E5E7EB;}}
        ''')
        btn_ok.clicked.connect(dlg.accept)

        btn_open = QPushButton('  Dosyayı Aç')
        btn_open.setFixedHeight(36)
        btn_open.setCursor(Qt.PointingHandCursor)
        btn_open.setStyleSheet(f'''
            QPushButton {{background:{accent_color};color:#FFF;border:none;
                border-radius:9px;font-size:11px;font-weight:700;padding:0 12px;}}
            QPushButton:hover {{opacity:0.9;}}
        ''')
        btn_open.clicked.connect(lambda: os.startfile(filepath))

        btn_row.addWidget(btn_ok)
        btn_row.addWidget(btn_open)
        lay.addLayout(btn_row)
        dlg.exec()

    @Slot(str, str)
    def _on_duplicate_file(self, fname, inv_id):
        self._duplicate_files.append((fname, inv_id))

    def _save_report(self):
        content = self.log_box.toPlainText().strip()
        if not content:
            QMessageBox.information(self, 'Bilgi', 'İşlem günlüğü boş.')
            return
        default = f'Rapor_{datetime.now().strftime("%Y%m%d_%H%M%S")}.txt'
        path, _ = QFileDialog.getSaveFileName(
            self, 'Raporu Kaydet',
            os.path.join(self.fc_c.get_path() or '', default),
            'Metin Dosyası (*.txt)'
        )
        if not path:
            return
        with open(path, 'w', encoding='utf-8') as f:
            f.write(f'XML Fatura Otomasyonu — İşlem Raporu\n')
            f.write(f'{datetime.now().strftime("%d.%m.%Y %H:%M")}\n')
            f.write('=' * 60 + '\n\n')
            f.write(content)
        self._log_append(f'✓ Rapor kaydedildi: {path}', 'ok')

    def _log_append(self, msg, tag='info'):
        c    = self.LOG_CLR.get(tag, '#CBD5E1')
        ts   = datetime.now().strftime('%H:%M:%S')
        html = (
            f'<span style="color:#475569;">[{ts}]</span>'
            f'&nbsp;&nbsp;<span style="color:{c};">{msg}</span>'
        )
        if getattr(self, '_cc_paused', False):
            self._cc_log_buffer.append(html)
            return
        self.log_box.append(html)
        self.log_box.ensureCursorVisible()

    # ── ContraCore lifecycle hooks ────────────────────────────────────────────

    def on_module_activated(self):
        """Shell tarafından modül görünür hale geldiğinde çağrılır."""
        self._cc_paused = False
        for html in self._cc_log_buffer:
            self.log_box.append(html)
        if self._cc_log_buffer:
            self.log_box.ensureCursorVisible()
        self._cc_log_buffer.clear()
        if self._cc_spin_was_active and not self._spin_timer.isActive():
            self._spin_timer.start()

    def on_module_deactivated(self):
        """Shell tarafından modül gizlendiğinde çağrılır."""
        self._cc_paused         = True
        self._cc_spin_was_active = self._spin_timer.isActive()
        if self._spin_timer.isActive():
            self._spin_timer.stop()


# ── Giriş ─────────────────────────────────────────────────────────────────────
def main():
    app = QApplication(sys.argv)
    try:
        app.setAttribute(Qt.AA_EnableHighDpiScaling, True)
        app.setAttribute(Qt.AA_UseHighDpiPixmaps,    True)
    except AttributeError:
        pass  # Qt6'da bu attribute'lar varsayılan olarak aktif
    app.setFont(QFont('Segoe UI', 10))

    from license import check_license, get_trial_status
    valid, msg, expire = check_license()

    trial_status = None

    if not valid:
        # Lisans yok — trial var mı kontrol et
        aktif, kalan_gun, islenen, kalan = get_trial_status()
        if aktif:
            # Deneme devam ediyor — direkt aç
            trial_status = (kalan_gun, islenen, kalan)
        else:
            # Deneme bitmişse veya hiç başlanmamışsa aktivasyon ekranı
            trial_expired = not aktif and islenen > 0  # sadece deneme kullanmış ama bitmiş
            from activation import ActivationWindow
            win = ActivationWindow(
                expired=trial_expired or ('doldu' in msg.lower()),
                expire_msg=msg if trial_expired else ''
            )
            win.show()
            app.exec()
            if win.activated:
                valid, msg, expire = check_license()
                if not valid:
                    sys.exit(0)
            elif win.trial_started:
                aktif2, kalan_gun2, islenen2, kalan2 = get_trial_status()
                trial_status = (kalan_gun2, islenen2, kalan2)
            else:
                sys.exit(0)
    else:
        # Geçerli lisans — trial_status yok
        pass

    w = MainWindow(expire_date=expire if valid else None, trial_status=trial_status)
    _ico = ip('xml.ico')
    ico = _ico if not _ico.isNull() else ip('logo.png')
    w.setWindowIcon(QIcon(ico))
    w.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()

