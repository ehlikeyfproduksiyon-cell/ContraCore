# -*- coding: utf-8 -*-
"""
SelectorChain — 5 strateji sırayla denenir, ilk çalışan döner.
Fallback çalışırsa WARNING loglar; otomatik registry değişikliği YAPILMAZ.
Geliştirici log'u okur, bu dosyayı elle günceller.
"""
import logging
from dataclasses import dataclass, field

from playwright.async_api import Page, Locator
from playwright.async_api import TimeoutError as PwTimeout

log = logging.getLogger(__name__)


@dataclass
class S:
    """Tek bir selector stratejisi."""
    method: str   # 'role' | 'text' | 'css' | 'xpath' | 'js'
    value: str
    options: dict = field(default_factory=dict)


class SelectorResilienceError(Exception):
    pass


class SelectorChain:
    def __init__(self, name: str, strategies: list[S]):
        self.name = name
        self.strategies = strategies

    def _build(self, page: Page, s: S) -> Locator:
        if s.method == "role":
            return page.get_by_role(s.value, **s.options)
        if s.method == "text":
            return page.get_by_text(s.value, **s.options)
        if s.method == "css":
            return page.locator(s.value)
        if s.method == "xpath":
            return page.locator(f"xpath={s.value}")
        raise ValueError(f"Bilinmeyen method: {s.method} (js= artık desteklenmiyor, css/xpath kullanın)")

    async def locate(self, page: Page, timeout_each: int = 3_000, use_first: bool = False) -> Locator:
        last_err = None
        for i, s in enumerate(self.strategies):
            try:
                loc = self._build(page, s)
                check = loc.first if use_first else loc
                await check.wait_for(state="visible", timeout=timeout_each)
                if i > 0:
                    log.warning(
                        "Selector '%s': strateji[0] başarısız, "
                        "strateji[%d] (%s='%s') çalıştı. Registry güncellenmeli.",
                        self.name, i, s.method, s.value
                    )
                return check
            except PwTimeout:
                last_err = f"timeout ({s.method}={s.value!r})"
            except Exception as e:
                last_err = str(e)
        raise SelectorResilienceError(
            f"Selector '{self.name}' — {len(self.strategies)} strateji başarısız. Son hata: {last_err}"
        )

    async def locate_all(self, page: Page, timeout_each: int = 3_000) -> list[Locator]:
        """Tüm eşleşmeleri döner (birden fazla eleman için)."""
        for i, s in enumerate(self.strategies):
            try:
                loc = self._build(page, s)
                await loc.first.wait_for(state="visible", timeout=timeout_each)
                count = await loc.count()
                return [loc.nth(j) for j in range(count)]
            except Exception:
                continue
        return []


# ══════════════════════════════════════════════════════════
#  SELECTORS REGISTRY
#  Kaynak: modules/e-ymm/karsit_otomasyon/main.py
#  GIB React SPA — build'den build'e class değişir, ID'ler daha stabil.
# ══════════════════════════════════════════════════════════

SELECTORS: dict[str, SelectorChain] = {

    # ── Login sayfası ───────────────────────────────────────────────────────

    "inp_kullanici": SelectorChain("inp_kullanici", [
        S("role",  "textbox", {"name": "T.C. Kimlik No / Vergi Kimlik"}),
        S("css",   "input[autocomplete='username']"),
        S("xpath", "(//input[@type='text'])[1]"),
    ]),

    "inp_sifre": SelectorChain("inp_sifre", [
        S("css",   "input[type='password']"),
        S("xpath", "//input[@type='password']"),
    ]),

    "inp_captcha": SelectorChain("inp_captcha", [
        S("xpath", "(//input[@type='text'])[last()]"),
        S("css",   "input[placeholder*='aptcha'], input[placeholder*='doğrulama']"),
        S("xpath", "(//input[@type='text'])[2]"),
    ]),

    "img_captcha": SelectorChain("img_captcha", [
        S("css",   "img[alt='captchaImg']"),
        S("xpath", "//img[@alt='captchaImg']"),
        S("css",   "img[src*='captcha']"),
    ]),

    "btn_captcha_yenile": SelectorChain("btn_captcha_yenile", [
        S("css",   "button:has([data-testid='ReplayRoundedIcon'])"),
        S("xpath", "//button[.//*[@data-testid='ReplayRoundedIcon']]"),
        S("css",   "button[aria-label*='enile'], button[title*='enile']"),
    ]),

    "btn_giris_yap": SelectorChain("btn_giris_yap", [
        S("xpath", "//button[normalize-space()='Giriş Yap']"),
        S("xpath", "//button[@type='submit']"),
        S("css",   "button[type='submit']"),
    ]),

    # ── Portal navigasyon ───────────────────────────────────────────────────

    "btn_hepsini_gor": SelectorChain("btn_hepsini_gor", [
        S("xpath", "//*[normalize-space()='Hepsini gör' or normalize-space()='Hepsini Gör' or normalize-space()='Tümünü gör']"),
        S("text",  "Hepsini gör"),
        S("text",  "Tümünü gör"),
    ]),

    "kart_ymm": SelectorChain("kart_ymm", [
        S("xpath", "//img[contains(@src,'eymm')]/ancestor::div[@data-testid='box-component'][1]"),
        S("xpath", "(//img[contains(@src,'eymm')])[1]/.."),
        S("xpath", "//p[contains(text(),'Yeminli Mali')]"),
        S("xpath", "(//img[@alt='ymm'])[1]/.."),
    ]),

    "btn_onayla_popup": SelectorChain("btn_onayla_popup", [
        S("xpath", "//button[normalize-space()='ONAYLA' or normalize-space()='Onayla' or normalize-space()='Evet' or normalize-space()='EVET']"),
        S("role",  "button", {"name": "Onayla"}),
        S("role",  "button", {"name": "Evet"}),
    ]),

    # ── eYMM menü ──────────────────────────────────────────────────────────

    "menu_karsit": SelectorChain("menu_karsit", [
        # #gibSideMenu içindeki tam menü öğesi
        S("css",   "#gibSideMenu a:has-text('Karşıt İnceleme Tutanağı')"),
        S("css",   "#gibSideMenu li:has-text('Karşıt İnceleme Tutanağı')"),
        S("css",   "#gibSideMenu *:has-text('Karşıt İnceleme Tutanağı')"),
        S("xpath", "//*[@id='gibSideMenu']//*[contains(normalize-space(.),'Karşıt İnceleme Tutanağı') and not(*[contains(normalize-space(.),'Karşıt İnceleme Tutanağı')])]"),
        S("xpath", "//*[@id='gibSideMenu']//*[contains(text(),'nceleme Tutan') and string-length(normalize-space(text()))<50]"),
    ]),

    "btn_olustur": SelectorChain("btn_olustur", [
        S("xpath", "//button[contains(normalize-space(),'tur') and contains(normalize-space(),'nceleme')]"),
        S("css",   "#addButton"),
        S("role",  "button", {"name": "Oluştur"}),
        S("xpath", "//button[contains(@id,'add') or contains(@id,'create') or contains(@id,'olustur')]"),
    ]),

    # ── Adım 1: Tutanak sayısı ──────────────────────────────────────────────

    "inp_tutanak_sayi": SelectorChain("inp_tutanak_sayi", [
        S("xpath", "//input[contains(@placeholder,'Sayı') or contains(@placeholder,'sayı') or contains(@id,'sayi') or contains(@name,'sayi')]"),
        S("css",   "input[placeholder*='ayı']"),
        S("xpath", "(//input[@type='text'])[1]"),
    ]),

    "btn_ileri": SelectorChain("btn_ileri", [
        S("xpath", "//button[contains(normalize-space(),'leri') and string-length(normalize-space())<20]"),
        S("role",  "button", {"name": "İleri"}),
        S("css",   "button:has-text('İleri')"),
        S("xpath", "//button[@data-testid='button-component' and contains(.,'leri')]"),
    ]),

    "btn_geri": SelectorChain("btn_geri", [
        S("css",   "#back-button"),
        S("xpath", "//button[@id='back-button']"),
        S("role",  "button", {"name": "Geri"}),
    ]),

    # ── Adım 2: Form alanları (React — ID stabil) ──────────────────────────
    # Bu alanlar JS React setter ile doldurulur (karsit_engine._react_fill)
    # ID'ler main.py'den alındı, doğrulanmış.

    "inp_ymm_telefon":         SelectorChain("inp_ymm_telefon",         [S("css", "#tel")]),
    "inp_mukellef_tel":        SelectorChain("inp_mukellef_tel",        [S("css", "#mukellefTel")]),
    "inp_karsit_vkn":          SelectorChain("inp_karsit_vkn",          [S("css", "#incelemeYapilanVknTckn")]),
    "inp_mukellef_vkn":        SelectorChain("inp_mukellef_vkn",        [S("css", "#kdvVknTckn")]),
    "inp_kdv_bas":             SelectorChain("inp_kdv_bas",             [S("css", "#iadeyeEsasOlanBaslangicDonemi")]),
    "inp_kdv_bit":             SelectorChain("inp_kdv_bit",             [S("css", "#iadeyeEsasOlanBitisDonemi")]),
    "inp_kdv_iade":            SelectorChain("inp_kdv_iade",            [S("css", "#iadeTalepEdilenDonem")]),
    "inp_kdv_soz_tarih":       SelectorChain("inp_kdv_soz_tarih",       [S("css", "#tasdikSozlesmesininTarihi")]),
    "inp_kdv_soz_no":          SelectorChain("inp_kdv_soz_no",          [S("css", "#tasdikSozlesmesininNumarasi")]),
    "inp_kdv_soz_giris":       SelectorChain("inp_kdv_soz_giris",       [S("css", "#tasdikSozlesmesiGirildigiTarih")]),
    "inp_tam_bas":             SelectorChain("inp_tam_bas",             [S("css", "#tasdikBaslangicDonemi")]),
    "inp_tam_bit":             SelectorChain("inp_tam_bit",             [S("css", "#tasdikBitisDonemi")]),
    "inp_tam_soz_tarih":       SelectorChain("inp_tam_soz_tarih",       [S("css", "#tasdikSozlesmeTarihi")]),
    "inp_tam_soz_no":          SelectorChain("inp_tam_soz_no",          [S("css", "#tasdikSozlesmeNumarasi")]),
    "inp_tam_soz_giris":       SelectorChain("inp_tam_soz_giris",       [S("css", "#tasdikSozlesmesiGirildigiTarih")]),
    "inp_karsit_ad":           SelectorChain("inp_karsit_ad",           [S("css", "#incelemeYapilanAdSoyad")]),

    "btn_ekle": SelectorChain("btn_ekle", [
        S("xpath", "//button[@data-testid='button-component'][normalize-space()='Ekle']"),
        S("role",  "button", {"name": "Ekle"}),
        S("text",  "Ekle", {"exact": True}),
    ]),

    "btn_onayla_form": SelectorChain("btn_onayla_form", [
        S("xpath", "//button[@type='submit' and @data-testid='button-component']"),
        S("css",   "button[type='submit'][data-testid='button-component']"),
        S("role",  "button", {"name": "Onayla"}),
    ]),

    "btn_sorgula": SelectorChain("btn_sorgula", [
        S("css",   "#sorgula"),
        S("xpath", "//button[@id='sorgula']"),
        S("role",  "button", {"name": "Sorgula"}),
    ]),

    # ── Adım 5: Excel yükleme ───────────────────────────────────────────────

    "inp_file_upload": SelectorChain("inp_file_upload", [
        S("css",   "input[type='file']"),
        S("xpath", "//input[@type='file']"),
    ]),

    # ── Adım 10: Kaydet ────────────────────────────────────────────────────

    "btn_kaydet": SelectorChain("btn_kaydet", [
        S("xpath", "//button[@data-testid='button-component' and normalize-space()='Kaydet']"),
        S("role",  "button", {"name": "Kaydet"}),
        S("text",  "Kaydet", {"exact": True}),
    ]),

    # ── Liste dönüşü ────────────────────────────────────────────────────────

    "btn_listeye_don": SelectorChain("btn_listeye_don", [
        S("css",   "#sorgula"),
        S("xpath", "//button[@id='sorgula']"),
        S("role",  "button", {"name": "Sorgula"}),
        S("xpath", "//button[contains(normalize-space(),'Sorgula')]"),
    ]),

    "btn_add_list": SelectorChain("btn_add_list", [
        S("css",   "#addButton"),
        S("xpath", "//button[@id='addButton']"),
    ]),

    # ── Hata tespiti ────────────────────────────────────────────────────────

    "adim2_hata_cemberi": SelectorChain("adim2_hata_cemberi", [
        S("css",   "circle[fill='#EF4242'], circle[fill='#ef4242']"),
        S("xpath", "//circle[@fill='#EF4242' or @fill='#ef4242']"),
    ]),

    "overlay_backdrop": SelectorChain("overlay_backdrop", [
        S("css", ".MuiBackdrop-root"),
    ]),

    "error_fields": SelectorChain("error_fields", [
        S("css",   "p.Mui-error"),
        S("xpath", "//p[contains(@class,'Mui-error')]"),
    ]),
}
