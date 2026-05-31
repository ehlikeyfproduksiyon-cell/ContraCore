# -*- coding: utf-8 -*-
"""
Debug yardımcıları — production debugging için.
DEBUG=1 env var ile aktif olur.
"""
import asyncio
import logging
import os
import time
from datetime import datetime
from pathlib import Path

from playwright.async_api import Page

log = logging.getLogger(__name__)

DEBUG = os.environ.get("DEBUG", "0") == "1"

_ARTIFACT_DIR = Path(os.environ.get("APPDATA", ".")) / "ContraCore" / "debug_artifacts"


def _artifact_dir() -> Path:
    _ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    return _ARTIFACT_DIR


async def capture_context(page: Page, label: str = "") -> dict:
    """Mevcut sayfa durumunu toplar — her zaman çalışır (DEBUG bağımsız)."""
    ctx = {
        "label":    label,
        "ts":       datetime.now().strftime("%H:%M:%S.%f")[:-3],
        "url":      "(unknown)",
        "title":    "(unknown)",
        "overlay":  False,
        "modals":   0,
    }
    try:
        ctx["url"]   = page.url
        ctx["title"] = await page.title()
        ctx["overlay"], ctx["modals"] = await page.evaluate("""
            () => {
                var bd = document.querySelector('.MuiBackdrop-root');
                var ov = bd ? window.getComputedStyle(bd).opacity !== '0' : false;
                var modals = document.querySelectorAll(
                    '[role="dialog"], .MuiModal-root, .MuiDialog-root'
                ).length;
                return [ov, modals];
            }
        """)
    except Exception:
        pass
    return ctx


def log_step_start(log_cb, step: str, firma: str, ctx: dict):
    log_cb(
        f"[STEP_START] {step} | {firma[:40]} | url={ctx['url'][-60:]} | "
        f"overlay={ctx['overlay']} modals={ctx['modals']}",
        "#64748B"
    )


def log_step_success(log_cb, step: str, firma: str, elapsed_ms: int):
    log_cb(f"[STEP_OK] {step} | {firma[:40]} | {elapsed_ms}ms", "#22C55E")


def log_step_error(log_cb, step: str, firma: str, exc: Exception, ctx: dict, elapsed_ms: int):
    log_cb(
        f"[STEP_ERR] {step} | {firma[:40]} | {elapsed_ms}ms | "
        f"url={ctx['url'][-60:]} | err={exc}",
        "#EF4444"
    )


async def dump_failure(page: Page, job_id: int, step: str):
    """Screenshot + HTML + console dump — her hata için."""
    ts  = datetime.now().strftime("%Y%m%d_%H%M%S")
    dir = _artifact_dir() / f"job{job_id}_{step}_{ts}"
    dir.mkdir(parents=True, exist_ok=True)

    # Screenshot
    try:
        await page.screenshot(path=str(dir / "screenshot.png"), full_page=True)
        log.info("DEBUG screenshot: %s", dir / "screenshot.png")
    except Exception as e:
        log.debug("Screenshot alınamadı: %s", e)

    # HTML dump
    try:
        html = await page.content()
        (dir / "page.html").write_text(html, encoding="utf-8", errors="replace")
        log.info("DEBUG html dump: %s", dir / "page.html")
    except Exception as e:
        log.debug("HTML dump alınamadı: %s", e)

    # DOM özeti (button listesi)
    try:
        buttons = await page.evaluate("""
            () => {
                var bs = document.querySelectorAll('button');
                var out = [];
                for (var b of bs) {
                    var t = (b.innerText || b.textContent || '').trim().slice(0,60);
                    var id = b.id || '';
                    var cls = b.className || '';
                    if (t || id) out.push({text: t, id: id, cls: cls.slice(0,40)});
                }
                return out;
            }
        """)
        lines = [f"  [{b['id'] or '—'}] {b['text']!r} cls={b['cls']}" for b in buttons]
        (dir / "buttons.txt").write_text(
            f"URL: {page.url}\nButtons ({len(buttons)}):\n" + "\n".join(lines),
            encoding="utf-8"
        )
        log.info("DEBUG buttons: %s", dir / "buttons.txt")
    except Exception as e:
        log.debug("Button dump alınamadı: %s", e)

    # Overlay / backdrop durumu
    try:
        info = await page.evaluate("""
            () => {
                var bd = document.querySelector('.MuiBackdrop-root');
                var overlay = null;
                if (bd) {
                    var s = window.getComputedStyle(bd);
                    overlay = {opacity: s.opacity, visibility: s.visibility, display: s.display};
                }
                var inputs = [];
                for (var inp of document.querySelectorAll('input')) {
                    inputs.push({id: inp.id, placeholder: inp.placeholder,
                                 type: inp.type, value: inp.value.slice(0,30)});
                }
                return {overlay: overlay, inputs: inputs};
            }
        """)
        import json
        (dir / "dom_info.json").write_text(
            json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        log.info("DEBUG dom_info: %s", dir / "dom_info.json")
    except Exception as e:
        log.debug("DOM info alınamadı: %s", e)

    return dir


async def pause_for_inspect(page: Page, log_cb, seconds: int = 30):
    """Hata sonrası browser açık kalır, geliştirici DOM inceleyebilir."""
    if not DEBUG:
        return
    log_cb(f"[DEBUG] {seconds}s pause — browser açık, DOM inceleyebilirsin.", "#F59E0B")
    await asyncio.sleep(seconds)
