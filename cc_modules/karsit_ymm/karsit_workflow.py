# -*- coding: utf-8 -*-
"""
Workflow State Machine — Step enum, geçiş haritası, WorkflowEngine.
"""
import asyncio
import json
import logging
from enum import Enum

from . import karsit_db as db

log = logging.getLogger(__name__)


# ── State tanımları ───────────────────────────────────────────────────────────

class Step(str, Enum):
    PENDING        = "PENDING"
    SESSION_CHECK  = "SESSION_CHECK"
    LOGIN          = "LOGIN"
    CAPTCHA        = "CAPTCHA"
    PORTAL_NAV     = "PORTAL_NAV"
    EYMM_NAV       = "EYMM_NAV"
    FORM_STEP_1    = "FORM_STEP_1"
    FORM_STEP_2    = "FORM_STEP_2"
    FORM_STEP_5    = "FORM_STEP_5"
    FORM_SUBMIT    = "FORM_SUBMIT"
    CONFIRMATION   = "CONFIRMATION"
    VERIFY_PORTAL  = "VERIFY_PORTAL"
    COMPLETE       = "COMPLETE"
    FAILED         = "FAILED"
    SKIPPED        = "SKIPPED"


TRANSITIONS: dict[Step, set[Step]] = {
    Step.PENDING:       {Step.SESSION_CHECK},
    Step.SESSION_CHECK: {Step.LOGIN, Step.PORTAL_NAV},
    Step.LOGIN:         {Step.CAPTCHA, Step.PORTAL_NAV},
    Step.CAPTCHA:       {Step.PORTAL_NAV, Step.LOGIN},
    Step.PORTAL_NAV:    {Step.EYMM_NAV},
    Step.EYMM_NAV:      {Step.FORM_STEP_1},
    Step.FORM_STEP_1:   {Step.FORM_STEP_2, Step.VERIFY_PORTAL},
    Step.FORM_STEP_2:   {Step.FORM_STEP_5},
    Step.FORM_STEP_5:   {Step.FORM_SUBMIT},
    Step.FORM_SUBMIT:   {Step.CONFIRMATION},
    Step.CONFIRMATION:  {Step.COMPLETE, Step.VERIFY_PORTAL},
    Step.VERIFY_PORTAL: {Step.COMPLETE, Step.FORM_STEP_1},
    Step.COMPLETE:      set(),
    Step.FAILED:        set(),
    Step.SKIPPED:       set(),
}

TERMINAL_STEPS = {Step.COMPLETE, Step.FAILED, Step.SKIPPED}

SAFE_RESET_STEPS = {
    Step.PENDING, Step.SESSION_CHECK, Step.LOGIN, Step.CAPTCHA,
    Step.PORTAL_NAV, Step.EYMM_NAV,
    Step.FORM_STEP_1, Step.FORM_STEP_2, Step.FORM_STEP_5,
}

VERIFY_REQUIRED_STEPS = {Step.FORM_SUBMIT, Step.CONFIRMATION}


class InvalidTransitionError(Exception):
    pass


# ── WorkflowEngine ────────────────────────────────────────────────────────────

class WorkflowEngine:
    """
    Step geçişlerini doğrular ve DB'ye atomik olarak yazar.
    Otomasyon mantığı karsit_engine.py'de; bu sınıf yalnızca state yönetimi yapar.
    """

    def transition(self, job_id: int, to: Step, reason: str = "success", data: dict = None):
        job = db.get_job(job_id)
        if not job:
            raise ValueError(f"Job {job_id} bulunamadı")
        from_step = Step(job["current_step"])
        if to not in TRANSITIONS[from_step]:
            raise InvalidTransitionError(
                f"Job {job_id}: {from_step.value} → {to.value} geçersiz geçiş"
            )
        db.update_job_step(job_id, to.value, reason=reason, data=data)
        log.debug("Job %d: %s → %s [%s]", job_id, from_step.value, to.value, reason)

    def skip(self, job_id: int):
        db.update_job_step(job_id, Step.SKIPPED.value, reason="user_skip")

    def fail(self, job_id: int, error: str, step: str):
        db.mark_job_failed(job_id, error, step)

    def current_step(self, job_id: int) -> Step:
        job = db.get_job(job_id)
        return Step(job["current_step"]) if job else Step.FAILED
