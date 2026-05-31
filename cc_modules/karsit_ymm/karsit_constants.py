# -*- coding: utf-8 -*-
import os
from pathlib import Path

# ── URL'ler ───────────────────────────────────────────────────────────────────
GIB_LOGIN_URL   = "https://dijital.gib.gov.tr/portal/login"
GIB_PORTAL_URL  = "https://dijital.gib.gov.tr/portal"
EYMM_BASE_URL   = "https://eymm.gib.gov.tr"

# ── Timeout'lar (saniye) ──────────────────────────────────────────────────────
TIMEOUT_PAGE     = 30_000   # ms — sayfa yükleme
TIMEOUT_ELEMENT  = 10_000   # ms — eleman bekleme
TIMEOUT_UPLOAD   = 60_000   # ms — dosya yükleme
TIMEOUT_CAPTCHA  = 120_000  # ms — kullanıcı CAPTCHA girişi

# ── Yollar ────────────────────────────────────────────────────────────────────
APPDATA = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
KARSIT_DIR      = APPDATA / "ContraCore" / "karsit_ymm"
SESSION_DIR     = KARSIT_DIR / "browser_session"
DB_PATH         = KARSIT_DIR / "karsit.db"
ARTIFACT_DIR    = KARSIT_DIR / "artifacts"
TEMP_EXCEL_DIR  = KARSIT_DIR / "temp_excel"

# Dizinleri oluştur
for _d in (SESSION_DIR, ARTIFACT_DIR, TEMP_EXCEL_DIR):
    _d.mkdir(parents=True, exist_ok=True)

# ── Excel sütun eşleme (master Excel → job alanları) ─────────────────────────
EXCEL_COL_FIRMA     = "Firma Adı"
EXCEL_COL_VKN       = "VKN"
EXCEL_COL_DONEM_YIL = "Dönem Yılı"
EXCEL_COL_DONEM_AY  = "Dönem Ayı"
EXCEL_COL_KARSIT_TUR= "Karşıt Türü"
EXCEL_COL_WORD_DOSYA= "Word Dosya"
EXCEL_COL_TELEFON   = "Telefon"

# ── Browser ayarları ──────────────────────────────────────────────────────────
BROWSER_OFFSCREEN_X = -32000
BROWSER_OFFSCREEN_Y = -32000
BROWSER_VISIBLE_X   = 100
BROWSER_VISIBLE_Y   = 50
BROWSER_WIDTH       = 1280
BROWSER_HEIGHT      = 900

# ── Job engine ────────────────────────────────────────────────────────────────
MAX_ATTEMPTS            = 3
RECYCLE_AFTER_JOBS      = 50
RECYCLE_AFTER_MINUTES   = 90
HEALTH_CHECK_EVERY_JOBS = 10
ORPHAN_TIMEOUT_MINUTES  = 10   # startup_recovery: bu kadar dakika sonra 'running' job orphan sayılır

# ── CAPTCHA ───────────────────────────────────────────────────────────────────
CAPTCHA_AUTO_THRESHOLD  = 0.82
CAPTCHA_MAX_AUTO_TRIES  = 2
