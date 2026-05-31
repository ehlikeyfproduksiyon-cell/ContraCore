# -*- coding: utf-8 -*-
"""
QThread + asyncio bridge.
GUI thread'de yaşar, asyncio event loop'u ayrı thread'de çalıştırır.
Tüm GUI iletişimi Signal/Slot üzerinden yapılır.
"""
import asyncio
import logging
import uuid

from PySide6.QtCore import QThread, Signal

from playwright.async_api import async_playwright

from . import karsit_db as db
from .karsit_session  import BrowserLifecycleManager, cleanup_zombie_browsers
from .karsit_engine   import KarsitEngine
from .karsit_workflow import WorkflowEngine
from .karsit_captcha  import ocr_solve, THRESHOLD

log = logging.getLogger(__name__)


class KarsitWorker(QThread):
    # ── Signals ───────────────────────────────────────────────────────────────
    sig_log            = Signal(str, str)    # (mesaj, renk_hex)
    sig_progress       = Signal(int, int, str)  # (current, total, firma)
    sig_captcha        = Signal(bytes, str)  # (PNG bytes, token)
    sig_finished       = Signal(bool, str)   # (success, özet)
    sig_recovery       = Signal(list)        # orphan job listesi
    sig_browser_state  = Signal(bool)        # True=görünür, False=gizli

    def __init__(self, batch_id: str, kullanici: str, sifre: str,
                 ymm_telefon: str, mukellef_telefon: str = "",
                 browser_visible: bool = False, parent=None):
        super().__init__(parent)
        self._batch_id         = batch_id
        self._kullanici        = kullanici
        self._sifre            = sifre
        self._ymm_telefon      = ymm_telefon
        self._mukellef_telefon = mukellef_telefon
        self._browser_visible  = browser_visible   # başlangıç görünürlüğü
        self._stop_ev:    asyncio.Event | None = None
        self._pause_ev:   asyncio.Event | None = None
        self._loop:       asyncio.AbstractEventLoop | None = None
        self._page = None                          # CDP toggle için referans

        self._captcha_fut:   asyncio.Future | None = None
        self._captcha_token: str | None            = None

    # ── Kontrol API'si (GUI thread'den çağrılır) ──────────────────────────────

    def request_stop(self):
        if self._loop and self._stop_ev:
            self._loop.call_soon_threadsafe(self._stop_ev.set)

    def request_pause(self):
        if self._loop and self._pause_ev:
            self._loop.call_soon_threadsafe(self._pause_ev.set)

    def request_resume(self):
        if self._loop and self._pause_ev:
            self._loop.call_soon_threadsafe(self._pause_ev.clear)

    def request_toggle_browser(self):
        """GUI thread'den çağrılır: tarayıcıyı göster/gizle."""
        if self._loop:
            self._loop.call_soon_threadsafe(
                lambda: asyncio.ensure_future(self._apply_browser_toggle())
            )

    async def _apply_browser_toggle(self):
        self._browser_visible = not self._browser_visible
        if self._page:
            from .karsit_session import show_browser, hide_browser
            if self._browser_visible:
                await show_browser(self._page)
            else:
                await hide_browser(self._page)
        self.sig_browser_state.emit(self._browser_visible)

    def submit_captcha(self, kod: str, token: str):
        """
        GUI dialog'dan CAPTCHA kodu geldiğinde çağrılır.
        token eşleşmezse (stale) sessizce görmezden gelir.
        """
        if self._captcha_token != token:
            log.debug("submit_captcha: stale token, ignore")
            return
        if self._captcha_fut and not self._captcha_fut.done():
            self._captcha_fut.get_loop().call_soon_threadsafe(
                self._captcha_fut.set_result, kod
            )

    # ── QThread entry point ───────────────────────────────────────────────────

    def run(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self._loop     = loop
        # Event'lar bu loop'a bağlı olmalı — GUI thread'den erişim call_soon_threadsafe ile
        self._stop_ev  = asyncio.Event()
        self._pause_ev = asyncio.Event()
        try:
            loop.run_until_complete(self._async_main())
        except Exception as e:
            log.exception("Worker async_main hata: %s", e)
            self.sig_finished.emit(False, str(e))
        finally:
            self._loop = None
            loop.close()

    # ── Async ana akış ────────────────────────────────────────────────────────

    async def _async_main(self):
        cleanup_zombie_browsers()

        report = db.startup_recovery()
        if report:
            self.sig_recovery.emit(report)

        if not db.integrity_check():
            self.sig_finished.emit(False, "Veritabanı bütünlük hatası!")
            return

        try:
            async with async_playwright() as pw:
                async with BrowserLifecycleManager(pw) as bm:
                    page = await bm.get_page()
                    self._page = page

                    # Başlangıç görünürlüğünü uygula
                    from .karsit_session import show_browser, hide_browser
                    if self._browser_visible:
                        await show_browser(page)
                    else:
                        await hide_browser(page)
                    self.sig_browser_state.emit(self._browser_visible)

                    wf = WorkflowEngine()
                    engine = KarsitEngine(
                        page        = page,
                        wf          = wf,
                        log_cb      = self._emit_log,
                        captcha_cb  = self._captcha_cb,
                        stop_event  = self._stop_ev,
                        pause_event = self._pause_ev,
                        ymm_telefon      = self._ymm_telefon,
                        mukellef_telefon = self._mukellef_telefon,
                    )

                    await engine.run_batch(
                        batch_id    = self._batch_id,
                        kullanici   = self._kullanici,
                        sifre       = self._sifre,
                        progress_cb = self._emit_progress,
                        bm          = bm,
                    )

            self.sig_finished.emit(True, "Tüm karşıtlar tamamlandı.")
        except asyncio.CancelledError:
            self.sig_finished.emit(False, "Kullanıcı tarafından durduruldu.")
        except Exception as e:
            log.exception("Batch hatası: %s", e)
            self.sig_finished.emit(False, str(e))

    # ── Callback'ler (worker thread'de çalışır) ───────────────────────────────

    def _emit_log(self, msg: str, color: str):
        self.sig_log.emit(msg, color)

    def _emit_progress(self, current: int, total: int, firma: str):
        self.sig_progress.emit(current, total, firma)

    async def _captcha_cb(self, img_bytes: bytes) -> str:
        """
        Engine'den çağrılır.
        1. OCR bir kez dene — aynı bytes deterministik, birden fazla deneme gereksiz.
        2. Confidence yeterliyse dön — GUI'ye dokunulmaz.
        3. Yetersizse modal dialog aç; kullanıcıyı bekle.

        Dönen boş string → engine yeniler ve yeni img_bytes ile tekrar çağırır.
        """
        kod, conf = ocr_solve(img_bytes)
        self._emit_log(f"OCR sonuç: [{kod}] güven={conf:.2f} (eşik={THRESHOLD})", "#94A3B8")
        if conf >= THRESHOLD and kod:
            self._emit_log(f"OCR otomatik gönderdi: [{kod}]", "#22C55E")
            return kod
        self._emit_log("OCR güven düşük — manuel giriş bekleniyor", "#F97316")
        return await self._ask_user(img_bytes)

    async def _ask_user(self, img_bytes: bytes) -> str:
        """
        Yeni bir token üret, GUI'ye signal gönder, cevabı bekle.
        Timeout veya cancel → '' döner (engine yeniler).
        """
        # Önceki bekleyen future'ı iptal et (race condition koruması)
        if self._captcha_fut and not self._captcha_fut.done():
            self._captcha_fut.get_loop().call_soon_threadsafe(
                self._captcha_fut.set_result, ''
            )

        loop = asyncio.get_event_loop()
        token = uuid.uuid4().hex
        self._captcha_token = token
        self._captcha_fut   = loop.create_future()

        self.sig_captcha.emit(img_bytes, token)
        log.info("CAPTCHA: kullanıcı bekleniyor (token=%s…)", token[:8])

        try:
            kod = await asyncio.wait_for(self._captcha_fut, timeout=120)
            return kod or ''
        except asyncio.TimeoutError:
            log.warning("CAPTCHA 120s'de girilmedi — boş döndürülüyor")
            return ''
        finally:
            self._captcha_fut   = None
            self._captcha_token = None
