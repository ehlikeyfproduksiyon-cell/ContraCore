# -*- coding: utf-8 -*-
"""
Playwright persistent browser context + session yönetimi.
Browser off-screen başlar; Human Takeover ile ekrana taşınır.
"""
import asyncio
import logging
from datetime import datetime

from playwright.async_api import async_playwright, BrowserContext, Page, Playwright

from .karsit_constants import (
    SESSION_DIR, GIB_LOGIN_URL, GIB_PORTAL_URL,
    BROWSER_OFFSCREEN_X, BROWSER_OFFSCREEN_Y,
    BROWSER_VISIBLE_X, BROWSER_VISIBLE_Y, BROWSER_WIDTH, BROWSER_HEIGHT,
    RECYCLE_AFTER_JOBS, RECYCLE_AFTER_MINUTES, HEALTH_CHECK_EVERY_JOBS,
    TIMEOUT_PAGE,
)

log = logging.getLogger(__name__)

_LAUNCH_ARGS = [
    f"--window-position={BROWSER_VISIBLE_X},{BROWSER_VISIBLE_Y}",   # görünür aç
    f"--window-size={BROWSER_WIDTH},{BROWSER_HEIGHT}",
    "--disable-blink-features=AutomationControlled",
    "--no-first-run",
    "--no-default-browser-check",
]


async def validate_session(page: Page) -> bool:
    """GIB portalına gidip hâlâ giriş yapılmış mı kontrol eder."""
    try:
        await page.goto(GIB_PORTAL_URL, wait_until="domcontentloaded", timeout=TIMEOUT_PAGE)
        await asyncio.sleep(1.5)
        url = page.url
        return "login" not in url and "giris" not in url
    except Exception as e:
        log.warning("Session validation hatası: %s", e)
        return False


async def _stealth(page: Page):
    """Minimal stealth — Playwright'ın kendi önerisi."""
    await page.add_init_script(
        "Object.defineProperty(navigator, 'webdriver', { get: () => undefined });"
    )


def _clear_profile_locks():
    """Chrome profil kilit dosyalarını temizle — 'mevcut oturumda açılıyor' hatasını önler."""
    for lock_file in ("SingletonLock", "SingletonCookie", "SingletonSocket"):
        p = SESSION_DIR / lock_file
        try:
            if p.exists():
                p.unlink()
                log.info("Profil kilidi temizlendi: %s", lock_file)
        except Exception as e:
            log.debug("Kilit dosyası silinemedi %s: %s", lock_file, e)


async def open_context(pw: Playwright) -> BrowserContext:
    """Persistent context aç — her zaman headless=False, görünürlük CDP ile kontrol edilir."""
    SESSION_DIR.mkdir(parents=True, exist_ok=True)
    _clear_profile_locks()
    ctx = await pw.chromium.launch_persistent_context(
        user_data_dir=str(SESSION_DIR),
        headless=False,
        args=_LAUNCH_ARGS,
        no_viewport=True,
    )
    # Tüm yeni sayfalara stealth uygula
    ctx.on("page", lambda p: asyncio.ensure_future(_stealth(p)))
    # Mevcut sayfalar
    for p in ctx.pages:
        await _stealth(p)
    return ctx


async def get_active_page(ctx: BrowserContext) -> Page:
    """Aktif sayfa döner. eYMM sekmesi varsa onu tercih eder; yoksa son sekmeyi döner."""
    pages = ctx.pages
    if not pages:
        page = await ctx.new_page()
        await _stealth(page)
        return page
    # eYMM sekmesini tercih et
    eymm = next((p for p in pages if "eymm.gib.gov.tr" in p.url), None)
    if eymm:
        return eymm
    # Son açık sekme (en son aktif olan)
    return pages[-1]


# ── CDP window bounds (Human Takeover) ───────────────────────────────────────

async def _get_window_id(page: Page) -> int:
    client = await page.context.new_cdp_session(page)
    result = await client.send("Browser.getWindowForTarget")
    await client.detach()
    return result["windowId"]


async def show_browser(page: Page):
    """Browser'ı ekrana taşır."""
    try:
        client = await page.context.new_cdp_session(page)
        wid = await _get_window_id(page)
        await client.send("Browser.setWindowBounds", {
            "windowId": wid,
            "bounds": {
                "left": BROWSER_VISIBLE_X, "top": BROWSER_VISIBLE_Y,
                "width": BROWSER_WIDTH, "height": BROWSER_HEIGHT,
                "windowState": "normal",
            }
        })
        await client.detach()
    except Exception as e:
        log.warning("show_browser CDP hatası: %s", e)


async def hide_browser(page: Page):
    """Browser'ı ekran dışına taşır."""
    try:
        client = await page.context.new_cdp_session(page)
        wid = await _get_window_id(page)
        await client.send("Browser.setWindowBounds", {
            "windowId": wid,
            "bounds": {
                "left": BROWSER_OFFSCREEN_X, "top": BROWSER_OFFSCREEN_Y,
                "windowState": "normal",
            }
        })
        await client.detach()
    except Exception as e:
        log.warning("hide_browser CDP hatası: %s", e)


# ── BrowserLifecycleManager ───────────────────────────────────────────────────

class BrowserLifecycleManager:
    """
    Playwright context'i yönetir.
    - Her N job'da veya M dakikada context recycle eder (session korunur).
    - Health check yapar, yanıt vermiyorsa recycle eder.
    """

    def __init__(self, pw: Playwright):
        self._pw = pw
        self._ctx: BrowserContext | None = None
        self._job_count = 0
        self._born_at: datetime | None = None
        self._was_recycled = False

    async def __aenter__(self):
        self._ctx = await open_context(self._pw)
        self._born_at = datetime.now()
        log.info("Browser context açıldı.")
        return self

    async def get_page(self) -> Page:
        if self._needs_recycle():
            await self._recycle()
        elif self._needs_health_check():
            await self._health_check()
        return await get_active_page(self._ctx)

    def increment(self):
        self._job_count += 1

    def _needs_recycle(self) -> bool:
        if self._job_count >= RECYCLE_AFTER_JOBS:
            return True
        elapsed = (datetime.now() - self._born_at).total_seconds() / 60
        return elapsed >= RECYCLE_AFTER_MINUTES

    def _needs_health_check(self) -> bool:
        return self._job_count > 0 and self._job_count % HEALTH_CHECK_EVERY_JOBS == 0

    def take_recycled(self) -> bool:
        """Recycle bayrağını sıfırlayarak döner. True → bir önceki get_page() recycle yaptı."""
        r = self._was_recycled
        self._was_recycled = False
        return r

    async def _recycle(self):
        log.info("Browser context recycle ediliyor (%d job)...", self._job_count)
        try:
            await self._ctx.close()
        except Exception:
            pass
        self._ctx = await open_context(self._pw)
        self._born_at = datetime.now()
        self._job_count = 0
        self._was_recycled = True
        log.info("Browser context yeniden açıldı.")

    async def _health_check(self):
        try:
            page = await get_active_page(self._ctx)
            await page.evaluate("() => document.readyState", timeout=5_000)
        except Exception:
            log.warning("Health check başarısız — recycle ediliyor.")
            await self._recycle()

    async def __aexit__(self, *_):
        if self._ctx:
            try:
                await self._ctx.close()
            except Exception:
                pass
            log.info("Browser context kapatıldı.")


# ── Zombie cleanup (startup'ta çalıştır) ─────────────────────────────────────

def cleanup_zombie_browsers():
    try:
        import psutil
        profile_path = str(SESSION_DIR)
        for proc in psutil.process_iter(["pid", "name", "cmdline"]):
            try:
                name = proc.info["name"] or ""
                if name.lower() in ("chrome.exe", "chromium.exe"):
                    cmdline = " ".join(proc.info["cmdline"] or [])
                    if profile_path in cmdline:
                        proc.kill()
                        log.info("Zombie browser temizlendi: PID %d", proc.pid)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
    except ImportError:
        log.debug("psutil yüklü değil — zombie cleanup atlandı.")
