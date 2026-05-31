# -*- coding: utf-8 -*-
"""
SQLite veritabanı katmanı — WAL mode, CRUD, startup recovery.
Thread-safe: her çağrı kendi bağlantısını açar (check_same_thread=False).
"""
import json
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from .karsit_constants import DB_PATH, ORPHAN_TIMEOUT_MINUTES


# ── Bağlantı havuzu (thread-local) ───────────────────────────────────────────
_local = threading.local()


def _get_conn() -> sqlite3.Connection:
    if not getattr(_local, "conn", None):
        _local.conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
        _local.conn.row_factory = sqlite3.Row
        _configure((_local.conn))
    return _local.conn


def _configure(conn: sqlite3.Connection):
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA wal_autocheckpoint=100")


@contextmanager
def _tx():
    conn = _get_conn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise


# ── Schema ────────────────────────────────────────────────────────────────────
_SCHEMA = """
CREATE TABLE IF NOT EXISTS batches (
    id          TEXT    PRIMARY KEY,
    status      TEXT    DEFAULT 'pending',
    ymm_profil  TEXT,
    kullanici   TEXT,
    toplam      INTEGER DEFAULT 0,
    tamamlanan  INTEGER DEFAULT 0,
    baslatildi  TEXT    DEFAULT (datetime('now')),
    bitti       TEXT
);

CREATE TABLE IF NOT EXISTS jobs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id        TEXT    NOT NULL REFERENCES batches(id),
    status          TEXT    DEFAULT 'pending',
    current_step    TEXT    DEFAULT 'PENDING',
    step_data       TEXT,
    -- Submission tracking (idempotency)
    form_opened_at  TEXT,
    submitted_at    TEXT,
    submission_ref  TEXT,
    portal_verified INTEGER DEFAULT 0,
    -- Business data
    excel_row       INTEGER,
    firma_adi       TEXT    NOT NULL,
    vkn             TEXT,
    donem_yil       INTEGER,
    donem_ay        INTEGER,
    karsit_tur      TEXT,
    word_dosya      TEXT,
    telefon         TEXT,
    -- Retry
    attempt         INTEGER DEFAULT 0,
    max_attempts    INTEGER DEFAULT 3,
    last_error      TEXT,
    error_step      TEXT,
    -- Timing
    created_at      TEXT    DEFAULT (datetime('now')),
    started_at      TEXT,
    finished_at     TEXT
);

CREATE TABLE IF NOT EXISTS step_transitions (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id     INTEGER NOT NULL REFERENCES jobs(id),
    from_step  TEXT,
    to_step    TEXT    NOT NULL,
    reason     TEXT,
    ts         TEXT    DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS logs (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id       INTEGER REFERENCES jobs(id),
    batch_id     TEXT,
    level        TEXT    DEFAULT 'INFO',
    step         TEXT,
    message      TEXT,
    artifact_path TEXT,
    ts           TEXT    DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_jobs_batch    ON jobs(batch_id);
CREATE INDEX IF NOT EXISTS idx_jobs_status   ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_logs_job      ON logs(job_id);
"""


def init_db():
    """Schema oluştur (idempotent)."""
    with _tx() as conn:
        conn.executescript(_SCHEMA)


# ── Batch CRUD ────────────────────────────────────────────────────────────────

def create_batch(batch_id: str, ymm_profil: str, kullanici: str, toplam: int):
    with _tx() as conn:
        conn.execute(
            "INSERT INTO batches(id, ymm_profil, kullanici, toplam) VALUES (?,?,?,?)",
            [batch_id, ymm_profil, kullanici, toplam]
        )


def get_batch(batch_id: str) -> sqlite3.Row | None:
    return _get_conn().execute(
        "SELECT * FROM batches WHERE id=?", [batch_id]
    ).fetchone()


def update_batch_status(batch_id: str, status: str):
    with _tx() as conn:
        bitti = datetime.now().isoformat() if status in ("completed", "failed") else None
        conn.execute(
            "UPDATE batches SET status=?, bitti=? WHERE id=?",
            [status, bitti, batch_id]
        )


# ── Job CRUD ──────────────────────────────────────────────────────────────────

def create_job(batch_id: str, row: dict) -> int:
    with _tx() as conn:
        cur = conn.execute("""
            INSERT INTO jobs(batch_id, firma_adi, vkn, donem_yil, donem_ay,
                             karsit_tur, word_dosya, telefon, excel_row, step_data)
            VALUES (?,?,?,?,?,?,?,?,?,?)
        """, [
            batch_id,
            row.get("firma_adi", ""),
            row.get("vkn", ""),
            row.get("donem_yil"),
            row.get("donem_ay"),
            row.get("karsit_tur", ""),
            row.get("word_dosya", ""),
            row.get("telefon", ""),
            row.get("excel_row"),
            row.get("step_data", "{}"),
        ])
        return cur.lastrowid


def get_job(job_id: int) -> sqlite3.Row | None:
    return _get_conn().execute(
        "SELECT * FROM jobs WHERE id=?", [job_id]
    ).fetchone()


def get_batch_jobs(batch_id: str) -> list[sqlite3.Row]:
    return _get_conn().execute(
        "SELECT * FROM jobs WHERE batch_id=? ORDER BY id", [batch_id]
    ).fetchall()


def get_pending_jobs(batch_id: str) -> list[sqlite3.Row]:
    return _get_conn().execute(
        "SELECT * FROM jobs WHERE batch_id=? AND status='pending' ORDER BY id",
        [batch_id]
    ).fetchall()


def update_job_step(job_id: int, to_step: str, reason: str = "success", data: dict = None):
    """Step geçişini atomik olarak kaydeder (transition log dahil)."""
    job = get_job(job_id)
    from_step = job["current_step"] if job else None
    with _tx() as conn:
        if data is not None:
            conn.execute(
                "UPDATE jobs SET current_step=?, step_data=? WHERE id=?",
                [to_step, json.dumps(data), job_id]
            )
        else:
            # step_data'yı koruyarak sadece current_step güncelle
            conn.execute(
                "UPDATE jobs SET current_step=? WHERE id=?",
                [to_step, job_id]
            )
        conn.execute(
            "INSERT INTO step_transitions(job_id, from_step, to_step, reason) VALUES (?,?,?,?)",
            [job_id, from_step, to_step, reason]
        )


def mark_job_running(job_id: int):
    with _tx() as conn:
        conn.execute(
            "UPDATE jobs SET status='running', started_at=datetime('now') WHERE id=?",
            [job_id]
        )


def mark_job_complete(job_id: int, submission_ref: str):
    job = get_job(job_id)
    from_step = job["current_step"] if job else "UNKNOWN"
    with _tx() as conn:
        conn.execute("""
            UPDATE jobs SET
                status='completed',
                current_step='COMPLETE',
                submission_ref=?,
                portal_verified=1,
                finished_at=datetime('now')
            WHERE id=?
        """, [submission_ref, job_id])
        conn.execute(
            "INSERT INTO step_transitions(job_id, from_step, to_step, reason) VALUES (?,?,?,?)",
            [job_id, from_step, "COMPLETE", "verified"]
        )


def mark_job_failed(job_id: int, error: str, error_step: str):
    job = get_job(job_id)
    from_step = job["current_step"] if job else "UNKNOWN"
    with _tx() as conn:
        conn.execute("""
            UPDATE jobs SET
                status='failed',
                current_step='FAILED',
                last_error=?,
                error_step=?,
                finished_at=datetime('now')
            WHERE id=?
        """, [error, error_step, job_id])
        conn.execute(
            "INSERT INTO step_transitions(job_id, from_step, to_step, reason) VALUES (?,?,?,?)",
            [job_id, from_step, "FAILED", error[:200]]
        )


def set_submitted_at(job_id: int):
    """'Gönder' tıklanmadan ÖNCE çağrılır — submission fence."""
    with _tx() as conn:
        conn.execute(
            "UPDATE jobs SET submitted_at=datetime('now') WHERE id=?",
            [job_id]
        )


def clear_submitted_at(job_id: int):
    """verify_portal not-found: submitted_at sıfırlanır; form yeniden doldurulabilir."""
    with _tx() as conn:
        conn.execute(
            "UPDATE jobs SET submitted_at=NULL WHERE id=?",
            [job_id]
        )


def set_submission_ref(job_id: int, ref: str):
    with _tx() as conn:
        conn.execute(
            "UPDATE jobs SET submission_ref=?, portal_verified=1 WHERE id=?",
            [ref, job_id]
        )


def increment_attempt(job_id: int):
    with _tx() as conn:
        conn.execute(
            "UPDATE jobs SET attempt=attempt+1 WHERE id=?",
            [job_id]
        )


# ── Logging ───────────────────────────────────────────────────────────────────

def log(batch_id: str = None, job_id: int = None, level: str = "INFO",
        step: str = None, message: str = "", artifact_path: str = None):
    with _tx() as conn:
        conn.execute(
            "INSERT INTO logs(job_id, batch_id, level, step, message, artifact_path) VALUES (?,?,?,?,?,?)",
            [job_id, batch_id, level, step, message, artifact_path]
        )


# ── Startup Recovery ──────────────────────────────────────────────────────────

_SAFE_RESET_STEPS = {
    "PENDING", "SESSION_CHECK", "LOGIN", "CAPTCHA",
    "PORTAL_NAV", "EYMM_NAV",
    "FORM_STEP_1", "FORM_STEP_2", "FORM_STEP_5",
}
_VERIFY_REQUIRED_STEPS = {"FORM_SUBMIT", "CONFIRMATION"}


def startup_recovery() -> list[dict]:
    """
    Crash'te 'running' kalan job'ları tespit eder ve güvenli adıma geri alır.
    Döner: [{'job': row, 'action': 'reset'|'verify_required'}, ...]
    """
    orphans = _get_conn().execute(f"""
        SELECT * FROM jobs
        WHERE status='running'
          AND started_at < datetime('now', '-{ORPHAN_TIMEOUT_MINUTES} minutes')
    """).fetchall()

    report = []
    for job in orphans:
        step = job["current_step"]
        if step in _SAFE_RESET_STEPS:
            with _tx() as conn:
                conn.execute(
                    "UPDATE jobs SET status='pending', current_step=? WHERE id=?",
                    [step, job["id"]]
                )
            report.append({"job": dict(job), "action": "reset"})
        elif step in _VERIFY_REQUIRED_STEPS:
            with _tx() as conn:
                conn.execute(
                    "UPDATE jobs SET status='pending', current_step='VERIFY_PORTAL' WHERE id=?",
                    [job["id"]]
                )
            report.append({"job": dict(job), "action": "verify_required"})

    return report


def cleanup_running_jobs(batch_id: str):
    """Batch sonunda hâlâ 'running' kalan job'ları 'pending'e çek (bir sonraki run hemen alır)."""
    jobs = _get_conn().execute(
        "SELECT id FROM jobs WHERE batch_id=? AND status='running'",
        [batch_id]
    ).fetchall()
    for job in jobs:
        with _tx() as conn:
            conn.execute("UPDATE jobs SET status='pending' WHERE id=?", [job["id"]])


def integrity_check() -> bool:
    """True = veritabanı sağlıklı."""
    row = _get_conn().execute("PRAGMA integrity_check").fetchone()
    return row and row[0] == "ok"


def wal_checkpoint():
    _get_conn().execute("PRAGMA wal_checkpoint(TRUNCATE)")
