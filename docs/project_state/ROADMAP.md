# ContraCore — Roadmap

**Last updated:** 2026-05-25

---

## Status Legend

| Symbol | Meaning |
|---|---|
| ✅ | Done (in production) |
| 🔄 | In progress |
| 📋 | Planned (high priority) |
| 💡 | Idea (low priority / optional) |

---

## Core System

| Item | Status | Notes |
|---|---|---|
| Shell + sidebar + QStackedWidget | ✅ | Production |
| Lazy module loading via adapters | ✅ | Production |
| 3-state sidebar (licensed/trial/locked) | ✅ | Production |
| V2 license key system | ✅ | Production |
| Unified activation dialog | ✅ | Production |
| Trial system (time + quota, 3-layer + machine-bound HMAC + clock rollback) | ✅ | Production |
| Module reload after activation | ✅ | Production |
| Graceful thread shutdown on close | ✅ | Production |
| Nuitka build pipeline | ✅ | Production |
| Admin panel (License Manager) | ✅ | Production |

---

## Near-Term (Next Release)

### Setup / Installer System

Create a Windows installer so customers receive a single `Setup.exe` instead of a ZIP.

Requirements:
- Müşteri yalnızca `ContraCORE_Setup.exe` alır — kaynak dosyalar, Icon/, Logom/ klasörleri görünmez
- Kurulum sonrası uygulama normal çalışır
- Start Menu + isteğe bağlı Desktop kısayolu
- Add/Remove Programs'a kayıt (uninstaller)
- Admin gerektirmeden `%LocalAppData%` altına kurabilmeli (tercih)
- Installer branding için `Icon/SETUP.ico` veya mevcut logo kullanılır

Muhtemel araç: **Inno Setup** — `modules/xml-fatura/setup.iss` referans olarak mevcut.  
Script hedefi: `build_tools/contracore.iss`

**Status:** Konuşuldu, henüz implement edilmedi (2026-05-25).

---

### Atomic CustomerStore Writes

Replace the direct `json.dump()` in `CustomerStore.save()` with an atomic write:

```python
def save(self):
    tmp = _STORE_FILE + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(self._data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, _STORE_FILE)   # atomic on all OS
```

This prevents partial-write corruption if the process is killed during save.

---

### CustomerDetails Auto-Refresh After Restore/Generate

After `_on_data_changed()` fires, also reload the currently displayed customer in `CustomerDetails`:

```python
def _on_data_changed(self):
    STORE.reload()
    self._dashboard.refresh()
    self._cust_table.refresh()
    self._rebuild_expiring2()
    # NEW: refresh details panel if a customer is loaded
    if self._cust_details._current_cid:
        c = STORE.get_by_id(self._cust_details._current_cid)
        if c:
            self._cust_details.load_customer(c)
```

---

## Medium-Term

### Shell-Level Update Checker

Add a lightweight version check at shell startup:
- Read local `version.txt` from the release root
- Compare against a remote version endpoint (e.g. GitHub Releases API or a simple hosted JSON)
- If update available: show a non-intrusive banner in the sidebar footer or a dialog on next launch
- Do not auto-update — just notify

Location: `core/updater.py` (new file), called from `Shell.__init__()` in a background QThread.

---

### ContraCORE Backup System

Auto-backup `tools/customers.json` to a rolling set of timestamped copies:

```
tools/backups/
  customers_2026-05-25.json
  customers_2026-05-24.json
  ... (keep last 30 days)
```

Trigger: on every `CustomerStore.save()` call, if the date has changed since the last backup. Or: on admin panel startup.

---

### Key Expiry Notifications (Admin Panel)

Add email or system notification when a customer's license is expiring soon. Options:
- Admin panel banner on startup: "X müşterinin lisansı 7 gün içinde bitiyor"
- Export expiring-soon list to CSV / clipboard
- (Optional) Send WhatsApp message directly from admin panel

---

### Per-Module Version Tracking

Track which version of each module a customer is running. Add `version` field to the customer's module entry:

```json
"xml-fatura": {
  "key": "V2-...",
  "expire": "2027-05-25",
  "tier": "pro",
  "issued_date": "2026-05-25",
  "version": "2.4.1"    ← new
}
```

This would be set at key generation time based on the current module version.

---

## Long-Term / Optional

### Cloud Sync (Optional)

Sync `customers.json` to a cloud backend (Firebase, Supabase, or a simple REST API) so the admin panel can be used from multiple machines. Requirements:
- Offline-first: local file is authoritative
- Conflict resolution: last-write wins, or manual merge
- Auth: API key based
- Privacy: all customer data should be encrypted at rest

**This is a significant architectural change.** Only pursue if working from multiple machines becomes a real need.

---

### Telemetry / Analytics (Optional)

Lightweight anonymous usage data:
- Module usage counts
- Activation success/failure rates
- Trial conversion rate

Requirements: must be opt-in, GDPR-aware, no PII. If implemented, add to `Settings` dialog.

---

### Enterprise Features

For large customers with multiple seats:
- Site license (one key, unlimited machines on a domain)
- License pools (N seats shared across org)
- Admin portal (web-based, separate from the desktop admin panel)

These require a server-side license service and are a significant departure from the current offline model.

---

### Release Automation

Automate the full build + release flow:

```powershell
# build_tools/release.py
# 1. Bump version in version.txt
# 2. Run build_contracore.py --clean
# 3. Run build_license_manager.py --clean
# 4. Run Inno Setup to produce ContraCORE_Setup_v1.x.x.exe
# 5. Create zip of release/ContraCORE/ for manual distribution
# 6. Tag git commit with version
# 7. Upload to GitHub Releases (optional)
```

---

### Multi-Language Support (i18n)

Currently UI is Turkish only. If international customers are targeted:
- Extract all strings to a JSON/PO translation file
- Add language selector to settings
- Qt has built-in `QTranslator` support

---

### New Module Onboarding Checklist

When adding a third module, the required steps are:

1. Create `modules/<new-id>/` directory
2. Write `adapter.py` implementing the 4 required functions
3. Add entry to `MODULE_REGISTRY` in `core/router.py`
4. Add to `MODULES` dict in `tools/key_service.py`
5. Add trial config to `_TRIAL_CFG` in `core/license/trial.py`
6. Add icon file to `Icon/` directory
7. Add to `build_tools/build_contracore.py` asset copy if needed
8. Test: lazy-load, trial auto-start, activation, reload after activation, thread cleanup on close
