# -*- coding: utf-8 -*-
"""
Playwright otomasyon step handler'ları.
Her public metod bir Step'e karşılık gelir ve bir sonraki Step döner.
"""
import asyncio
import logging
import os
import random
import tempfile
from pathlib import Path
from typing import Callable, Awaitable

from playwright.async_api import Page, BrowserContext
from playwright.async_api import TimeoutError as PwTimeout

from . import karsit_db as db
from .karsit_session import BrowserLifecycleManager
from .karsit_constants import (
    GIB_LOGIN_URL, EYMM_BASE_URL, TIMEOUT_PAGE, TIMEOUT_ELEMENT,
    TIMEOUT_UPLOAD, TEMP_EXCEL_DIR,
)
from .karsit_parser import faturalari_cek, fatura_aylarini_al, adim5_excel_uret
from .karsit_selectors import SELECTORS, SelectorResilienceError
from .karsit_workflow import Step, WorkflowEngine, InvalidTransitionError
from .karsit_validator import normalize_telefon
from .karsit_debug import (
    capture_context, log_step_start, log_step_success, log_step_error,
    dump_failure, pause_for_inspect, DEBUG,
)

log = logging.getLogger(__name__)

# ── Callback türleri ──────────────────────────────────────────────────────────
LogCb       = Callable[[str, str], None]   # (mesaj, renk_hex)
ProgressCb  = Callable[[int, int, str], None]  # (current, total, firma)
CaptchaCb   = Callable[[bytes], Awaitable[str]]  # img_bytes → kod string


# ── Yardımcı: gerçekçi timing ─────────────────────────────────────────────────

async def _jitter(lo: float, hi: float):
    await asyncio.sleep(random.uniform(lo, hi))


async def _human_click(loc):
    await loc.scroll_into_view_if_needed()
    await loc.click()
    await _jitter(0.05, 0.12)


async def _human_fill(loc, value: str):
    await loc.click()
    await loc.fill(value)
    await _jitter(0.05, 0.12)


async def _ry(page: Page, field_id: str, value: str):
    """Hızlı React input yazıcı — fill() + dispatch events.
    Disabled/readonly ise skip eder."""
    if not value:
        return
    # Disabled kontrolü
    state = await page.evaluate(f"""
        () => {{
            var el = document.getElementById('{field_id}');
            if (!el) return 'missing';
            if (el.disabled) return 'disabled:' + el.value;
            if (el.readOnly) return 'readonly:' + el.value;
            return 'ok';
        }}
    """)
    if state and state.startswith("disabled:"):
        existing = state[len("disabled:"):]
        digits_val = ''.join(c for c in str(value) if c.isdigit())
        digits_ex  = ''.join(c for c in existing if c.isdigit())
        if digits_val and digits_val == digits_ex:
            log.debug("_ry: %s disabled, doğru değer var — skip.", field_id)
            return
        log.warning("_ry: %s disabled, yazılamıyor (mevcut=%r, istenen=%r)", field_id, existing, value)
        return
    # Hızlı yol: JS setter — char-by-char typing yok, anlık
    result = await page.evaluate(f"""
        () => {{
            var el = document.getElementById('{field_id}');
            if (!el) return 'missing';
            var setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
            setter.call(el, {repr(str(value))});
            el.dispatchEvent(new Event('input',  {{bubbles:true}}));
            el.dispatchEvent(new Event('change', {{bubbles:true}}));
            el.dispatchEvent(new Event('blur',   {{bubbles:true}}));
            return el.value;
        }}
    """)
    if result == 'missing' or result is None:
        log.warning("_ry: %s bulunamadı", field_id)
        return
    # Değer yazılmadıysa (masked/protected field) klavye fallback
    written = ''.join(c for c in str(result) if c.isdigit())
    expected = ''.join(c for c in str(value) if c.isdigit())
    if expected and written != expected:
        log.debug("_ry: %s setter çalışmadı, klavye fallback", field_id)
        loc = page.locator(f"#{field_id}")
        try:
            await loc.click(timeout=3_000)
            await loc.press("Control+a")
            await loc.press("Delete")
            await loc.type(str(value), delay=5)
            await loc.dispatch_event("input")
            await loc.dispatch_event("change")
            await loc.dispatch_event("blur")
        except PwTimeout:
            log.warning("_ry: %s klavye fallback da başarısız", field_id)


async def _js_click_ileri(page: Page) -> bool:
    """
    'İleri' / 'İLERİ' butonunu JavaScript ile bulup tıklar.
    GIB portal büyük harf 'İLERİ' kullanıyor — hem küçük hem büyük kontrol edilir.
    """
    result = await page.evaluate("""
        () => {
            var butonlar = document.querySelectorAll('button');
            for (var b of butonlar) {
                var txt = (b.innerText || b.textContent || '').trim();
                if ((txt.indexOf('leri') > -1 || txt.indexOf('LERİ') > -1) && txt.length < 20) {
                    b.click();
                    return true;
                }
            }
            return false;
        }
    """)
    return bool(result)


async def _js_click_olustur(page: Page) -> bool:
    """
    'Oluştur' / 'Karşıt İnceleme Tutanağı Oluştur' butonunu JS ile bulup tıklar.
    Eski çalışan main.py'nin olustur_el bloğundan birebir.
    """
    result = await page.evaluate("""
        () => {
            var butonlar = document.querySelectorAll('button');
            for (var b of butonlar) {
                var txt = (b.innerText || b.textContent || '').trim();
                if (txt.indexOf('tur') > -1 && txt.indexOf('nceleme') > -1) {
                    b.click();
                    return true;
                }
            }
            var walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
            var node;
            while (node = walker.nextNode()) {
                var txt = node.textContent.trim();
                if (txt.indexOf('Olu') > -1 && txt.indexOf('tur') > -1 && txt.indexOf('nceleme') > -1) {
                    node.parentElement.click();
                    return true;
                }
            }
            return false;
        }
    """)
    return bool(result)


# ── React input yazıcı (JS native value setter) ───────────────────────────────

async def _react_fill(page: Page, field_id: str, value: str, masked: bool = False) -> bool:
    """
    React controlled input'a değer yazar.
    masked=True → telefon gibi IMask alanlar için send_keys yaklaşımı kullan.
    """
    if not value:
        return True
    for attempt in range(3):
        # Overlay (MuiBackdrop) kapanana + alan DOM'da hazır olana kadar bekle
        writability_test = "" if masked else """
                    var old = el.value;
                    el.value = '___test___';
                    var ok = el.value === '___test___';
                    el.value = old;
                    if (!ok) return false;"""
        try:
            await page.wait_for_function(f"""
                () => {{
                    var el = document.getElementById('{field_id}');
                    if (!el) return false;
                    if (el.disabled || el.readOnly) return false;
                    var overlay = document.querySelector('.MuiBackdrop-root');
                    if (overlay && window.getComputedStyle(overlay).opacity !== '0') return false;{writability_test}
                    return true;
                }}
            """, timeout=8_000)
        except PwTimeout:
            log.warning("_react_fill: %s hazır değil (deneme %d)", field_id, attempt + 1)
            await asyncio.sleep(1)
            continue

        if masked:
            # Maskelenmiş alan: mevcut değeri sil + klavye ile yaz
            loc = page.locator(f"#{field_id}")
            await loc.click()
            await loc.press("Control+a")
            await loc.press("Delete")
            await loc.type(str(value), delay=20)
            await loc.press("Tab")
            await asyncio.sleep(0.1)
            result = await page.evaluate(f"document.getElementById('{field_id}')?.value")
        else:
            result = await page.evaluate(f"""
                () => {{
                    var el = document.getElementById('{field_id}');
                    if (!el) return null;
                    var setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
                    setter.call(el, {repr(str(value))});
                    el.dispatchEvent(new Event('input',  {{bubbles: true}}));
                    el.dispatchEvent(new Event('change', {{bubbles: true}}));
                    el.dispatchEvent(new Event('blur',   {{bubbles: true}}));
                    return el.value;
                }}
            """)

        if result is not None:
            # Maskelenmiş alanlar formatı değiştirir — rakam karşılaştırması yap
            r_digits = ''.join(c for c in str(result) if c.isdigit())
            v_digits = ''.join(c for c in str(value)  if c.isdigit())
            if v_digits and v_digits in r_digits:
                return True
            if str(value) in str(result):
                return True
        await asyncio.sleep(0.7)

    log.error("_react_fill: %s yazılamadı!", field_id)
    return False


async def _wait_backdrop(page: Page, timeout: int = 15_000):
    """MuiBackdrop overlay'i kapanana kadar bekle."""
    try:
        await page.wait_for_function("""
            () => {
                var b = document.querySelector('.MuiBackdrop-root');
                if (!b) return true;
                var s = window.getComputedStyle(b);
                return s.opacity === '0' || s.visibility === 'hidden';
            }
        """, timeout=timeout)
    except PwTimeout:
        pass
    await _jitter(0.05, 0.1)


async def _step_ileri(page: Page, timeout: int = 15_000):
    """'İleri' butonunu JS ile tıkla — Türkçe encoding sorununu aşar."""
    # Önce butonun DOM'a girmesini bekle — hem 'İleri' hem 'İLERİ' (GIB büyük harf kullanıyor)
    try:
        await page.wait_for_function("""
            () => {
                var bs = document.querySelectorAll('button');
                for (var b of bs) {
                    var t = (b.innerText || b.textContent || '').trim();
                    if ((t.indexOf('leri') > -1 || t.indexOf('LERİ') > -1) && t.length < 20) return true;
                }
                return false;
            }
        """, timeout=timeout)
    except PwTimeout:
        pass  # Zaten yoksa evaluate false döner ve hata fırlatılır

    clicked = await page.evaluate("""
        () => {
            var bs = document.querySelectorAll('button');
            for (var b of bs) {
                var t = (b.innerText || b.textContent || '').trim();
                if ((t.indexOf('leri') > -1 || t.indexOf('LERİ') > -1) && t.length < 20) {
                    b.click();
                    return true;
                }
            }
            return false;
        }
    """)
    if not clicked:
        # Debug: mevcut butonları listele
        btn_list = await page.evaluate("""
            () => {
                var bs = document.querySelectorAll('button');
                var out = [];
                for (var b of bs) {
                    var t = (b.innerText || b.textContent || '').trim().slice(0, 50);
                    out.push(t || ('[id=' + b.id + ']'));
                }
                return out;
            }
        """)
        log.error("İleri butonu bulunamadı. Sayfadaki butonlar: %s", btn_list)
        raise RuntimeError(f"İleri butonu bulunamadı. Butonlar: {btn_list}")
    await _wait_backdrop(page)


async def _check_adim2_error(page: Page) -> list[str]:
    """Adım 2 hata dairesi veya Mui-error alanlarını döner."""
    return await page.evaluate("""
        () => {
            var circles = document.querySelectorAll('circle[fill="#EF4242"], circle[fill="#ef4242"]');
            if (circles.length > 0) {
                var ps = document.querySelectorAll('p.Mui-error');
                var ids = [];
                for (var p of ps) {
                    var t = p.textContent || '';
                    if (t.indexOf('zorunlu') > -1 || t.indexOf('Zorunlu') > -1) {
                        var id = p.id ? p.id.replace('-helper-text','') : '';
                        if (id) ids.push(id);
                    }
                }
                return ids.length ? ids : ['__step2_error__'];
            }
            return [];
        }
    """)


# ══════════════════════════════════════════════════════════
#  KarsitEngine
# ══════════════════════════════════════════════════════════

class KarsitEngine:
    def __init__(
        self,
        page: Page,
        wf: WorkflowEngine,
        log_cb: LogCb,
        captcha_cb: CaptchaCb,
        stop_event: asyncio.Event,
        pause_event: asyncio.Event,
        ymm_telefon: str,
        mukellef_telefon: str = "",
    ):
        self._page              = page
        self._wf                = wf
        self._log               = log_cb
        self._captcha_cb        = captcha_cb
        self._stop              = stop_event
        self._pause             = pause_event
        self._ymm_telefon       = normalize_telefon(ymm_telefon)
        self._mukellef_telefon  = normalize_telefon(mukellef_telefon) if mukellef_telefon else ""

    def _info(self, msg: str):
        log.info(msg)
        self._log(msg, "#A0AEC0")

    def _ok(self, msg: str):
        log.info(msg)
        self._log(msg, "#68D391")

    def _warn(self, msg: str):
        log.warning(msg)
        self._log(msg, "#F6E05E")

    def _err(self, msg: str):
        log.error(msg)
        self._log(msg, "#FC8181")

    async def _check_control(self):
        """Pause / Stop kontrolü — her kritik adımda çağrılır."""
        while self._pause.is_set():
            await asyncio.sleep(0.3)
        if self._stop.is_set():
            raise asyncio.CancelledError("Kullanıcı durdurdu")

    # ── Adım: session check ───────────────────────────────────────────────────

    async def step_session_check(self, job_id: int) -> Step:
        self._info("Oturum kontrol ediliyor...")
        # PENDING → SESSION_CHECK geçişi (ilk iş için)
        job = db.get_job(job_id)
        if Step(job["current_step"]) == Step.PENDING:
            self._wf.transition(job_id, Step.SESSION_CHECK)
        from .karsit_session import validate_session
        valid = await validate_session(self._page)
        if valid:
            self._ok("Oturum geçerli — portal'a yönlendiriliyor.")
            self._wf.transition(job_id, Step.PORTAL_NAV)
            return Step.PORTAL_NAV
        else:
            self._info("Oturum yok — giriş yapılacak.")
            self._wf.transition(job_id, Step.LOGIN)
            return Step.LOGIN

    # ── Adım: login ───────────────────────────────────────────────────────────

    async def step_login(self, job_id: int, kullanici: str, sifre: str) -> Step:
        self._info("GIB giriş sayfası açılıyor...")
        await self._page.goto(GIB_LOGIN_URL, wait_until="domcontentloaded", timeout=TIMEOUT_PAGE)

        # Kullanıcı kodu
        inp_kul = await SELECTORS["inp_kullanici"].locate(self._page)
        await _human_fill(inp_kul, kullanici)

        # Şifre
        inp_sif = await SELECTORS["inp_sifre"].locate(self._page)
        await _human_fill(inp_sif, sifre)

        # CAPTCHA — fotoğrafı al, callback'e ilet
        return await self._handle_login_captcha(job_id, kullanici, sifre)

    async def _handle_login_captcha(self, job_id: int, kullanici: str, sifre: str) -> Step:
        self._wf.transition(job_id, Step.CAPTCHA)
        for attempt in range(4):
            captcha_img = self._page.locator("img[alt='captchaImg']")
            try:
                img_bytes = await captcha_img.screenshot(timeout=8_000)
            except Exception:
                img_bytes = b""

            kod = await self._captcha_cb(img_bytes)
            if not kod:
                self._warn("CAPTCHA boş — yenileniyor...")
                await self._yenile_captcha()
                continue

            inp_cap = await SELECTORS["inp_captcha"].locate(self._page)
            await _human_fill(inp_cap, kod)

            btn = await SELECTORS["btn_giris_yap"].locate(self._page)
            await _human_click(btn)
            # Login sayfasından çıkana kadar bekle (redirect tamamlansın)
            try:
                await self._page.wait_for_url(
                    lambda url: "login" not in url and "giris" not in url,
                    timeout=10_000
                )
                self._ok("Giriş başarılı.")
                self._wf.transition(job_id, Step.PORTAL_NAV, reason="login_success")
                return Step.PORTAL_NAV
            except PwTimeout:
                cur_url = self._page.url
                self._info(f"  Giriş sonrası URL: {cur_url}")

            # Hata mesajı var mı?
            self._warn(f"CAPTCHA yanlış veya giriş başarısız (deneme {attempt+1})")
            await self._yenile_captcha()

        raise RuntimeError("CAPTCHA 4 denemede de başarısız — oturum açılamadı.")

    async def _yenile_captcha(self):
        try:
            btn = await SELECTORS["btn_captcha_yenile"].locate(self._page, timeout_each=2_000)
            await btn.click()
            await _jitter(0.8, 1.2)
        except Exception:
            pass

    # ── Navigation helpers (DB write yok — recycle recovery'de de kullanılır) ──

    async def _do_portal_nav(self):
        try:
            btn = await SELECTORS["btn_hepsini_gor"].locate(self._page, timeout_each=8_000)
            await _human_click(btn)
            await _jitter(0.5, 1.0)
        except SelectorResilienceError:
            pass

        # YMM kartını bul ve JS click — eski main.py birebir (native click GIB hata veriyor)
        # expect_page ÖNCE başlatılmalı — ONAYLA sonrası yeni sekme açılır
        xpaths = [
            "//img[contains(@src,'eymm')]/ancestor::div[@data-testid='box-component'][1]",
            "//p[contains(text(),'Yeminli Mali')]",
            "//img[contains(@src,'eymm')]/..",
            "//img[@alt='ymm']/..",
        ]

        try:
            async with self._page.context.expect_page(timeout=20_000) as page_info:
                # Kartı bul ve JS click — eski main.py'deki arguments[0].click() karşılığı
                clicked = False
                for xpath in xpaths:
                    try:
                        el = self._page.locator(f"xpath={xpath}").first
                        await el.wait_for(state="attached", timeout=3_000)
                        await el.evaluate("el => el.click()")
                        clicked = True
                        self._info(f"YMM kartı tıklandı: {xpath[:50]}")
                        break
                    except Exception:
                        continue
                if not clicked:
                    raise RuntimeError("YMM kartı bulunamadı")

                await _jitter(0.5, 1.0)

                # Onay popup — JS click (eski main.py gibi)
                try:
                    btn_ok = await SELECTORS["btn_onayla_popup"].locate(self._page, timeout_each=8_000)
                    await btn_ok.evaluate("el => el.click()")
                    self._info("Onay popup tıklandı.")
                except SelectorResilienceError:
                    self._info("Onay popup çıkmadı — devam.")

            new_page = await page_info.value
            await new_page.wait_for_load_state("domcontentloaded", timeout=15_000)
            self._page = new_page
            self._info(f"Yeni sekmeye geçildi: {new_page.url}")
        except PwTimeout:
            # Yeni sekme açılmadı — eymm.gib.gov.tr var mı bak
            pages = self._page.context.pages
            eymm_page = next((p for p in pages if "eymm.gib.gov.tr" in p.url), None)
            if eymm_page:
                self._page = eymm_page
                self._info(f"eYMM sekmesi bulundu: {eymm_page.url}")
            elif len(pages) > 1:
                self._page = pages[-1]
                self._info("Mevcut son sekmeye geçildi.")
            else:
                self._info("Yeni sekme açılmadı — aynı sayfada devam.")

    async def _do_eymm_nav(self):
        # Sayfanın tam yüklenmesini bekle
        try:
            await self._page.wait_for_load_state("networkidle", timeout=15_000)
        except PwTimeout:
            pass
        await _jitter(0.2, 0.4)

        # Önce #gibSideMenu + text ile dene (Playwright chained locator)
        menu = None
        try:
            loc = self._page.locator("#gibSideMenu").get_by_text("Karşıt İnceleme Tutanağı").first
            await loc.wait_for(state="visible", timeout=10_000)
            menu = loc
            self._info("Menü bulundu: #gibSideMenu locator")
        except Exception:
            pass

        # Fallback: JavaScript TreeWalker — eski çalışan sistemden birebir
        if menu is None:
            try:
                handle = await self._page.evaluate_handle("""
                    () => {
                        var w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
                        var n;
                        while (n = w.nextNode()) {
                            var t = n.textContent.trim();
                            if (t.indexOf('nceleme Tutan') > -1 && t.length < 50)
                                return n.parentElement;
                        }
                        return null;
                    }
                """)
                el = handle.as_element()
                if el:
                    menu = self._page.locator(":scope").filter(has=self._page.locator("*")).first
                    # JS click doğrudan handle üzerinde
                    await el.evaluate("el => el.click()")
                    self._info("Menü JS TreeWalker ile tıklandı.")
                    await _jitter(1.0, 1.5)
                    return
            except Exception as e:
                self._warn(f"JS TreeWalker başarısız: {e}")

        if menu is None:
            raise SelectorResilienceError("Karşıt İnceleme Tutanağı menüsü bulunamadı")

        await menu.evaluate("el => el.click()")
        await _jitter(0.8, 1.2)

    # ── Adım: portal nav → eYMM ──────────────────────────────────────────────

    async def step_portal_nav(self, job_id: int) -> Step:
        self._info("YMM portalına geçiliyor...")
        await self._check_control()
        await self._do_portal_nav()
        self._wf.transition(job_id, Step.EYMM_NAV)
        return Step.EYMM_NAV

    # ── Adım: eYMM menü ───────────────────────────────────────────────────────

    async def _do_return_to_list(self):
        """
        Her job sonrası listeye dön.
        Zaten liste sayfasındaysak (#addButton görünür) hiçbir şey yapma.
        """
        # Zaten liste sayfasındaysak — hemen çık
        if await self._page.locator('#addButton').is_visible():
            self._info("Listeye döndü — Oluştur butonu hazır.")
            return

        # result sayfasındaki #sorgula = "Karşıt İnceleme Tutanaklarım"
        try:
            btn = self._page.locator('#sorgula')
            await btn.wait_for(state='visible', timeout=8_000)
            await btn.evaluate('el => el.click()')
            await self._page.locator('#addButton').wait_for(state='visible', timeout=12_000)
            self._info("Listeye döndü — sonraki firma hazır.")
        except Exception:
            self._warn("Liste butonu bulunamadı — menüden yeniden navigate ediliyor...")
            await self._do_eymm_nav()

    async def step_eymm_nav(self, job_id: int) -> Step:
        self._info("Karşıt İnceleme Tutanağı menüsü aranıyor...")
        await self._do_eymm_nav()
        self._wf.transition(job_id, Step.FORM_STEP_1)
        return Step.FORM_STEP_1

    # ── Adım: Form Step 1 — tutanak sayısı ───────────────────────────────────

    async def step_form_1(self, job_id: int) -> Step:
        await self._check_control()
        job = db.get_job(job_id)

        # Idempotency: zaten gönderilmiş mi?
        if job["submission_ref"] or job["portal_verified"]:
            self._ok(f"Job {job_id} zaten tamamlanmış: {job['submission_ref']}")
            return Step.COMPLETE

        # submitted_at dolu ama ref yok → crash recovery → portal'ı sorgula
        if job["submitted_at"] and not job["submission_ref"]:
            self._warn("Önceki oturumda gönderim yapılmış olabilir — portal doğrulama.")
            self._wf.transition(job_id, Step.VERIFY_PORTAL, reason="crash_recovery")
            return Step.VERIFY_PORTAL

        firma = job["firma_adi"]
        tutanak_no = job["step_data"] or ""
        if isinstance(tutanak_no, str) and tutanak_no.startswith("{"):
            import json
            tutanak_no = json.loads(tutanak_no).get("tutanak_sayisi", "")

        # Debug: adım başı bağlam
        ctx = await capture_context(self._page, label="FORM_STEP_1_start")
        log_step_start(self._log, "FORM_STEP_1", firma, ctx)

        self._info(f"Adım 1: {firma} — tutanak sayısı giriliyor...")

        # "Oluştur" butonunu JS ile tıkla — eski çalışan sistemden birebir
        await _jitter(0.3, 0.5)
        ok = await _js_click_olustur(self._page)
        if not ok:
            raise RuntimeError("Oluştur butonu bulunamadı")

        # Yükleme overlay'i önce belirir sonra kaybolur — her ikisini de bekle
        await asyncio.sleep(0.5)          # overlay'in belirmesi için kısa bekleme
        await _wait_backdrop(self._page, timeout=20_000)   # overlay kapanana kadar bekle

        # Tutanak sayısı alanını doldur
        if tutanak_no:
            try:
                inp = await SELECTORS["inp_tutanak_sayi"].locate(self._page, timeout_each=8_000)
                await inp.click()
                await inp.press("Control+a")
                await inp.type(str(tutanak_no), delay=30)
                await inp.dispatch_event("input")
                await inp.dispatch_event("change")
                await _jitter(0.1, 0.2)
            except SelectorResilienceError:
                self._warn("Tutanak sayısı alanı bulunamadı — atlanıyor.")

        await _step_ileri(self._page)
        self._wf.transition(job_id, Step.FORM_STEP_2)
        return Step.FORM_STEP_2

    # ── Adım: Form Step 2 — sözleşme + VKN ───────────────────────────────────

    async def step_form_2(self, job_id: int) -> Step:
        await self._check_control()
        job = db.get_job(job_id)
        self._info(f"Adım 2: {job['firma_adi']} — form dolduruluyor...")

        # Adım 2 formunun hazır olmasını bekle — #tel görünmeden yazmaya çalışma
        try:
            await self._page.wait_for_selector("#tel", state="visible", timeout=20_000)
        except PwTimeout:
            # Fallback: backdrop kapanmasını bekle, sonra dene
            await _wait_backdrop(self._page, timeout=15_000)
            await _jitter(1.0, 1.5)

        # step_data'dan genişletilmiş bilgileri al
        import json
        extra = {}
        if job["step_data"] and job["step_data"] != "{}":
            try:
                extra = json.loads(job["step_data"])
            except Exception:
                pass

        tasdik_tur   = (job["karsit_tur"] or "KDV").upper()
        karsit_vkn   = job["vkn"] or ""
        mukellef_vkn = extra.get("mukellef_vkn", "")
        telefon      = self._mukellef_telefon  # GUI'den gelir, Excel'den değil

        kdv_donem_turu = extra.get("kdv_donem_turu", "").upper()  # "" veya "İNDİRİMLİ ORAN"
        kdv_soz_tarih  = extra.get("kdv_soz_tarih", "")
        kdv_soz_no     = extra.get("kdv_soz_no", "")
        kdv_soz_giris  = extra.get("kdv_soz_giris", "")
        kdv_bas        = extra.get("kdv_bas", "")
        kdv_bit        = extra.get("kdv_bit", "")
        kdv_iade       = extra.get("kdv_iade", "")
        tam_bas       = extra.get("tam_bas", "")
        tam_bit       = extra.get("tam_bit", "")
        tam_soz_tarih = extra.get("tam_soz_tarih", "")
        tam_soz_no    = extra.get("tam_soz_no", "")
        tam_soz_giris = extra.get("tam_soz_giris", "")

        # Word dosyasından fatura aylarını hesapla
        word_yolu = job["word_dosya"] or ""
        if not word_yolu or not os.path.exists(word_yolu):
            self._warn(f"  Word dosyası yok: {word_yolu!r} — adım 2 erken fail.")
            raise FileNotFoundError(f"Word dosyası yok: {word_yolu!r}")
        faturalar = faturalari_cek(word_yolu)
        fatura_aylari = fatura_aylarini_al(faturalar)

        # 2a: YMM Telefon
        await _react_fill(self._page, "tel", self._ymm_telefon, masked=True)

        # 2b: KDV dönemleri
        if "KDV" in tasdik_tur or "HER" in tasdik_tur:
            indirmli = "İNDİRİMLİ" in kdv_donem_turu

            if indirmli:
                # SENARYO B: İndirimli Oran — Excel'den direkt, 1 kez
                self._info(f"  KDV İndirimli Oran: {kdv_bas}→{kdv_bit} | iade={kdv_iade}")
                await self._ekle_tikla(0)
                await asyncio.sleep(0.5)
                if mukellef_vkn:
                    await _ry(self._page, "kdvVknTckn", mukellef_vkn)
                await _ry(self._page, "iadeyeEsasOlanBaslangicDonemi", kdv_bas)
                await _ry(self._page, "iadeyeEsasOlanBitisDonemi", kdv_bit)
                await _ry(self._page, "iadeTalepEdilenDonem", kdv_iade)
                await _ry(self._page, "tasdikSozlesmesininTarihi", kdv_soz_tarih)
                await _ry(self._page, "tasdikSozlesmesininNumarasi", kdv_soz_no)
                await _ry(self._page, "tasdikSozlesmesiGirildigiTarih", kdv_soz_giris)
                await self._onayla_tikla()
                self._ok(f"  ✓ KDV İndirimli Oran eklendi.")
            else:
                # SENARYO A: Normal — Word'den benzersiz aylar, her ay için ayrı
                # Fatura ayları AA/YYYY → GIB'in beklediği AA.YYYY formatına çevir
                donems = [d.replace("/", ".") for d in fatura_aylari] if fatura_aylari else ([kdv_bas] if kdv_bas else [])
                self._info(f"  KDV Normal: {len(donems)} dönem | mük_vkn={mukellef_vkn!r}")
                for i, donem in enumerate(donems):
                    await self._check_control()
                    await self._ekle_tikla(0)
                    await asyncio.sleep(0.1)
                    if i == 0 and mukellef_vkn:
                        # VKN sadece ilk dönemde yazılır
                        await _ry(self._page, "kdvVknTckn", mukellef_vkn)
                    await _ry(self._page, "iadeyeEsasOlanBaslangicDonemi", donem)
                    await _ry(self._page, "iadeyeEsasOlanBitisDonemi", donem)  # başlangıç ile aynı
                    iade = kdv_iade if kdv_iade else donem
                    await _ry(self._page, "iadeTalepEdilenDonem", iade)
                    await _ry(self._page, "tasdikSozlesmesininTarihi", kdv_soz_tarih)
                    await _ry(self._page, "tasdikSozlesmesininNumarasi", kdv_soz_no)
                    await _ry(self._page, "tasdikSozlesmesiGirildigiTarih", kdv_soz_giris)
                    await self._onayla_tikla()
                    self._ok(f"  ✓ KDV dönem {donem} ({i+1}/{len(donems)})")

        # 2c: Tam Tasdik
        if ("TAM" in tasdik_tur or "HER" in tasdik_tur) and tam_bas and tam_bit:
            self._info(f"  Tam Tasdik: {tam_bas} → {tam_bit}")
            ekle_idx = 1 if "HER" in tasdik_tur else 0
            await self._ekle_tikla(ekle_idx)
            await _ry(self._page, "tasdikBaslangicDonemi", tam_bas)
            await _ry(self._page, "tasdikBitisDonemi", tam_bit)
            await _ry(self._page, "tasdikSozlesmeTarihi", tam_soz_tarih)
            await _ry(self._page, "tasdikSozlesmeNumarasi", tam_soz_no)
            await _ry(self._page, "tasdikSozlesmesiGirildigiTarih", tam_soz_giris)
            await self._onayla_tikla()
            self._ok("  ✓ Tam Tasdik eklendi.")

        # 2d: Firma telefon
        if telefon:
            await _react_fill(self._page, "mukellefTel", telefon, masked=True)

        # 2e: Karşıt VKN + Sorgula
        self._info(f"  VKN sorgula: {karsit_vkn}")
        await self._page.evaluate("() => window.scrollTo(0, document.body.scrollHeight)")
        # _ry() ile yaz — focus input'ta kalır, sonraki TAB+ENTER çalışır
        await _ry(self._page, "incelemeYapilanVknTckn", karsit_vkn)
        await _jitter(0.2, 0.3)
        # JS setter focus bırakmıyor — önce field'a tıkla, sonra TAB+TAB+ENTER
        await self._page.locator("#incelemeYapilanVknTckn").click(timeout=3_000)
        await self._page.keyboard.press("Tab")
        await _jitter(0.1, 0.2)
        await self._page.keyboard.press("Tab")
        await _jitter(0.1, 0.2)
        await self._page.keyboard.press("Enter")
        # Ad/Soyad alanı dolana kadar bekle
        try:
            await self._page.wait_for_function("""
                () => {
                    var el = document.getElementById('incelemeYapilanAdSoyad');
                    return el && el.value && el.value.length > 2;
                }
            """, timeout=10_000)
        except PwTimeout:
            await _jitter(2.0, 2.5)

        # 2f: Zorunlu alan kontrolü + İleri
        eksikler = await _check_adim2_error(self._page)
        if eksikler and eksikler != ["__step2_error__"]:
            self._warn(f"  Eksik alanlar: {eksikler} — tekrar dolduruluyor...")
            await self._fill_missing(eksikler, karsit_vkn, telefon)

        await _step_ileri(self._page)
        await _jitter(0.2, 0.4)

        # Adım 2 hata dairesi?
        if await _check_adim2_error(self._page):
            self._warn("  Adım 2 hatalı — geri dönüp yeniden dolduruluyor...")
            back_btn = self._page.locator('#back-button')
            if await back_btn.count() > 0:
                await back_btn.click()
            await _jitter(0.8, 1.2)
            eksikler2 = await _check_adim2_error(self._page)
            await self._fill_missing(eksikler2, karsit_vkn, telefon)
            await _step_ileri(self._page)

        # Adım 3 ve 4'ü atla
        for adim in (3, 4):
            await self._check_control()
            self._info(f"  Adım {adim} atlanıyor...")
            await _step_ileri(self._page)

        self._wf.transition(job_id, Step.FORM_STEP_5)
        return Step.FORM_STEP_5

    async def _ekle_tikla(self, index: int = 0):
        """'Ekle' butonunu tıkla, form alanı görünür olana kadar bekle."""
        ekle_btns = await SELECTORS["btn_ekle"].locate_all(self._page)
        if not ekle_btns:
            btn = await SELECTORS["btn_ekle"].locate(self._page)
            await btn.click()
        else:
            idx = min(index, len(ekle_btns) - 1)
            await ekle_btns[idx].click()
        try:
            await self._page.wait_for_function("""
                () => document.getElementById('iadeyeEsasOlanBaslangicDonemi')
                   || document.getElementById('tasdikBaslangicDonemi')
            """, timeout=6_000)
        except PwTimeout:
            await _jitter(0.2, 0.4)

    async def _onayla_tikla(self):
        """Submit butonunu tıkla, form kapanana kadar bekle."""
        btn = await SELECTORS["btn_onayla_form"].locate(self._page)
        await btn.click()
        try:
            await self._page.wait_for_function("""
                () => !document.querySelector('button[type="submit"][data-testid="button-component"]')
            """, timeout=20_000)
        except PwTimeout:
            await _wait_backdrop(self._page)

    async def _fill_missing(self, eksikler: list[str], karsit_vkn: str, telefon: str):
        for alan in eksikler:
            if alan == "tel":
                await _react_fill(self._page, "tel", self._ymm_telefon, masked=True)
            elif alan == "mukellefTel":
                await _react_fill(self._page, "mukellefTel", telefon, masked=True)
            elif alan == "incelemeYapilanVknTckn":
                await _react_fill(self._page, "incelemeYapilanVknTckn", karsit_vkn)
                await self._page.keyboard.press("Tab")
                await self._page.keyboard.press("Tab")
                await self._page.keyboard.press("Enter")
                try:
                    await self._page.wait_for_function("""
                        () => { var el=document.getElementById('incelemeYapilanAdSoyad');
                                return el && el.value && el.value.length > 2; }
                    """, timeout=8_000)
                except PwTimeout:
                    await _jitter(2.0, 2.5)

    # ── Adım: Form Step 5 — Excel yükle ──────────────────────────────────────

    async def step_form_5(self, job_id: int) -> Step:
        await self._check_control()
        job = db.get_job(job_id)
        self._info(f"Adım 5: {job['firma_adi']} — Excel yükleniyor...")

        word_yolu = job["word_dosya"] or ""
        if not word_yolu or not os.path.exists(word_yolu):
            self._warn(f"  Word dosyası bulunamadı: {word_yolu!r} — job başarısız sayılıyor.")
            raise FileNotFoundError(f"Word dosyası yok: {word_yolu!r}")

        faturalar = faturalari_cek(word_yolu)

        tmp = tempfile.NamedTemporaryFile(
            suffix=".xlsx", delete=False,
            dir=str(TEMP_EXCEL_DIR), prefix=f"job{job_id}_"
        )
        tmp.close()
        adim5_excel_uret(faturalar, tmp.name)
        self._info(f"  {len(faturalar)} fatura → {Path(tmp.name).name}")

        try:
            # file input genellikle hidden — visible bekleme yapma, sadece DOM'da olmasını bekle
            inp = self._page.locator("input[type='file']")
            await inp.wait_for(state="attached", timeout=TIMEOUT_UPLOAD)
            await inp.set_input_files(tmp.name)
            # Yükleme sonrası backdrop kapanana kadar bekle, sonra 1s sabit
            await _wait_backdrop(self._page, timeout=10_000)
            await asyncio.sleep(1.0)
        except Exception as e:
            self._err(f"  Excel yükleme hatası: {e}")
            raise
        finally:
            try:
                os.unlink(tmp.name)
            except Exception:
                pass

        # Adım 5 sonrası: 6→7→8→9→10 (her biri İleri) — adım 10 = Kaydet sayfası
        # step 5 yükleme bitti, döngü adım 10'a kadar İleri basar
        # adım 10'daki Kaydet ise step_submit() tarafından tıklanır
        for adim in range(6, 11):
            await self._check_control()
            self._info(f"  Adım {adim} geçiliyor...")
            await _step_ileri(self._page)
            await _jitter(0.1, 0.2)

        self._wf.transition(job_id, Step.FORM_SUBMIT)
        return Step.FORM_SUBMIT

    # ── Adım: Submit ──────────────────────────────────────────────────────────

    async def step_submit(self, job_id: int) -> Step:
        await self._check_control()
        self._info("Adım 10: Kaydediliyor...")

        # FENCE: gönderimden önce submitted_at yaz
        db.set_submitted_at(job_id)

        btn = await SELECTORS["btn_kaydet"].locate(self._page, timeout_each=15_000)
        await btn.click()
        await _wait_backdrop(self._page, timeout=20_000)
        self._ok("Kaydedildi.")

        self._wf.transition(job_id, Step.CONFIRMATION)
        return Step.CONFIRMATION

    # ── Adım: Confirmation ────────────────────────────────────────────────────

    async def step_confirmation(self, job_id: int) -> Step:
        """
        Kaydet sonrası result sayfasındaki #sorgula butonuna tıkla → liste sayfasına dön.
        Job tamamlandı olarak işaretle.
        """
        self._info("Karşıt İnceleme Tutanaklarım → listeye dönülüyor...")
        # result sayfasındaki #sorgula = "Karşıt İnceleme Tutanaklarım" butonu
        try:
            btn = self._page.locator("#sorgula")
            await btn.wait_for(state="visible", timeout=15_000)
            await btn.evaluate("el => el.click()")
            await _jitter(0.3, 0.6)
            self._info("  #sorgula tıklandı — liste bekleniyor...")
        except Exception as e:
            self._warn(f"  #sorgula bulunamadı: {e}")

        # Liste sayfasında #addButton (Oluştur) görünene kadar bekle
        try:
            await self._page.locator("#addButton").wait_for(state="visible", timeout=15_000)
            self._ok("  Liste hazır — sonraki firma için Oluştur görünüyor.")
        except PwTimeout:
            await _wait_backdrop(self._page)

        # Job'u tamamlandı say — referans doğrulaması sonraya bırakılabilir
        db.mark_job_complete(job_id, "submitted")
        self._ok(f"✓ Job {job_id} tamamlandı.")
        return Step.COMPLETE

    # ── Adım: Verify Portal ───────────────────────────────────────────────────

    async def step_verify_portal(self, job_id: int) -> Step:
        """
        Portal listesinde bu job'a ait tutanağı VKN ile arar.
        Bulursa mark_job_complete → COMPLETE.
        Bulamazsa submitted_at sıfırlanır ve FORM_STEP_1'den yeniden başlatılır.
        GIB ref numarası formatı: en az 10 basamak rakam.
        """
        job = db.get_job(job_id)
        vkn   = job["vkn"] or ""
        firma = job["firma_adi"]
        self._info(f"Portal doğrulama: {firma} (VKN={vkn})...")

        # VKN yoksa filtre uygulanamaz — yanlış match riski, fresh retry daha güvenli
        if not vkn:
            self._warn("VKN boş — portal doğrulama güvensiz, submitted_at sıfırlanıyor.")
            db.clear_submitted_at(job_id)
            db.update_job_step(job_id, Step.FORM_STEP_1.value, reason="verify_no_vkn")
            return Step.FORM_STEP_1

        # Liste tablosunun yüklenmesini bekle
        try:
            await self._page.wait_for_function("""
                () => document.querySelectorAll(
                    'table tbody tr, [data-testid="table-row"]'
                ).length > 0
            """, timeout=15_000)
        except PwTimeout:
            self._warn("Liste tablosu yüklenmedi — bulunamadı sayılıyor.")
            db.clear_submitted_at(job_id)
            db.update_job_step(job_id, Step.FORM_STEP_1.value, reason="verify_table_timeout")
            return Step.FORM_STEP_1

        # VKN'ye göre satır ara; GIB ref = en az 10 basamak rakam
        ref = await self._page.evaluate(f"""
            () => {{
                var vkn = {repr(vkn)};
                var rows = document.querySelectorAll(
                    'table tbody tr, [data-testid="table-row"]'
                );
                for (var row of rows) {{
                    if (vkn && (row.textContent || '').indexOf(vkn) === -1) continue;
                    var cells = row.querySelectorAll('td');
                    for (var cell of cells) {{
                        var t = (cell.textContent || '').trim();
                        if (/^\\d{{10,20}}$/.test(t)) return t;
                    }}
                }}
                return null;
            }}
        """)

        if ref:
            db.mark_job_complete(job_id, str(ref))
            self._ok(f"Doğrulandı: ref={ref}")
            return Step.COMPLETE
        else:
            self._warn(f"Portal'da bulunamadı ({firma}) — submitted_at sıfırlanıyor, yeniden başlatılıyor.")
            db.clear_submitted_at(job_id)
            db.update_job_step(job_id, Step.FORM_STEP_1.value, reason="verify_not_found")
            return Step.FORM_STEP_1

    # ── Batch runner ──────────────────────────────────────────────────────────

    async def run_batch(
        self,
        batch_id: str,
        kullanici: str,
        sifre: str,
        progress_cb: ProgressCb,
        bm: "BrowserLifecycleManager | None" = None,
    ):
        jobs = db.get_pending_jobs(batch_id)
        total = len(jobs)

        try:
            _stopped = False

            # Session check (bir kez) — outer try içinde: hata → cleanup_running_jobs çalışır
            first_job = jobs[0] if jobs else None
            if first_job:
                db.mark_job_running(first_job["id"])
                cur = await self.step_session_check(first_job["id"])
                if cur == Step.LOGIN:
                    cur = await self.step_login(first_job["id"], kullanici, sifre)
                if cur == Step.PORTAL_NAV:
                    cur = await self.step_portal_nav(first_job["id"])
                if cur == Step.EYMM_NAV:
                    cur = await self.step_eymm_nav(first_job["id"])
            for i, job_row in enumerate(jobs):
                await self._check_control()
                job_id = job_row["id"]
                firma  = job_row["firma_adi"]
                progress_cb(i + 1, total, firma)

                if i > 0:
                    db.mark_job_running(job_id)
                    # PENDING → FORM_STEP_1: workflow geçişini atla, direkt güncelle
                    db.update_job_step(job_id, Step.FORM_STEP_1.value, reason="batch_next")

                try:
                    step = self._wf.current_step(job_id)
                    if step in (Step.PENDING, Step.SESSION_CHECK, Step.LOGIN,
                                Step.PORTAL_NAV, Step.EYMM_NAV, Step.FORM_STEP_1):
                        step = await self.step_form_1(job_id)
                    if step == Step.FORM_STEP_2:
                        step = await self.step_form_2(job_id)
                    if step == Step.FORM_STEP_5:
                        step = await self.step_form_5(job_id)
                    if step == Step.FORM_SUBMIT:
                        step = await self.step_submit(job_id)
                    if step == Step.CONFIRMATION:
                        step = await self.step_confirmation(job_id)
                    if step == Step.VERIFY_PORTAL:
                        step = await self.step_verify_portal(job_id)
                    if step == Step.COMPLETE:
                        self._ok(f"✓ {firma} tamamlandı.")
                        db.increment_attempt(job_id)
                except asyncio.CancelledError:
                    _stopped = True
                    raise
                except Exception as e:
                    import time as _time
                    cur_step = self._wf.current_step(job_id).value
                    self._err(f"✗ {firma} hata [{cur_step}]: {e}")
                    db.mark_job_failed(job_id, str(e), cur_step)
                    db.log(batch_id=batch_id, job_id=job_id,
                           level="ERROR", step=cur_step, message=str(e))
                    # Debug: screenshot + HTML + DOM dump
                    try:
                        ctx = await capture_context(self._page, label=cur_step)
                        artifact_dir = await dump_failure(self._page, job_id, cur_step)
                        self._warn(f"[DEBUG] Artifacts → {artifact_dir}")
                        log_step_error(self._log, cur_step, firma, e, ctx, 0)
                    except Exception as dbg_e:
                        self._warn(f"[DEBUG] Artifact dump başarısız: {dbg_e}")
                    await pause_for_inspect(self._page, self._log, seconds=30)
                finally:
                    # Her job sonrası (cancel hariç) listeye dön
                    if bm and not _stopped:
                        needs_recycle = bm._needs_recycle()
                        bm.increment()
                        try:
                            if needs_recycle:
                                # Recycle: context yeniden aç, portal + menü navigate et
                                self._page = await bm.get_page()
                                bm.take_recycled()
                                self._info("Browser recycle — portal'a yeniden navigate ediliyor...")
                                await self._do_portal_nav()
                                await self._do_eymm_nav()
                            else:
                                # Normal: self._page değiştirme, zaten liste sayfasındayız
                                await self._do_return_to_list()
                        except Exception as nav_e:
                            self._warn(f"Job sonrası navigation hatası: {nav_e}")
        finally:
            # Batch bitişinde hâlâ 'running' olan job'ları pending'e çek
            # (verify_portal → FORM_STEP_1 gibi durumlarda oluşur)
            db.cleanup_running_jobs(batch_id)

        self._ok(f"Batch tamamlandı: {total} firma.")
