# ContraCore — Known Issues & Risk Registry

**Last updated:** 2026-05-25

---

## Active Bugs (Minor)

### 1. sys.modules['license'] Race Condition (Low Risk)

**Location:** `core/shell.py:_activate_module_license()`, both adapters  
**Symptom:** If a background thread in one module calls `from license import ...` at the exact moment the user switches to the other module, the wrong license shim could be active for that import.  
**Why it exists:** `sys.modules['license']` is a shared global, overwritten on each module switch.  
**Actual risk:** Very low. Background threads in both modules do not dynamically import `license` — they use already-bound references from startup.  
**Resolution:** Acceptable as-is. Would only matter if a background thread did a fresh `import license` mid-run.

---

### 2. Expiring Page Does Not Auto-Refresh

**Location:** `tools/license_manager.py:_build_expiring_page()`  
**Symptom:** The "Süresi Yaklaşan Lisanslar" page builds its content once at startup, then only refreshes when `_on_data_changed()` fires (after generate/restore). Navigating to the page via sidebar does call `_rebuild_expiring2()`, so it's actually fine for normal use.  
**Actual risk:** None — `_switch_page('expiring')` always calls `_rebuild_expiring2()`.  
**Status:** Not a bug; noted for clarity.

---

### 3. Customer Details Panel Not Refreshed After Direct HWID Edit

**Location:** `tools/widgets/customer_details.py`  
**Symptom:** If a customer's HWID is updated via restore, the CustomerDetails panel on the right may still show the old HWID until the user re-selects the customer.  
**Why:** `_on_data_changed()` calls `cust_table.refresh()` but not `cust_details.load_customer()` on the currently loaded customer.  
**Workaround:** Click the customer again in the table to reload the details.

---

### 4. `QStackedWidget` Geometry Glitch on First Show

**Location:** `core/shell.py:showEvent()`  
**Symptom:** On some systems, the embedded module widget renders at wrong size on first show (e.g. 0×0 or partial size).  
**Current fix:** Two `QTimer.singleShot` calls at 0ms and 50ms force a geometry refresh after first paint.  
**Residual risk:** On very slow machines or with unusual DPI scaling, the 50ms window may not be enough. Adding a third timer at 200ms would be a safe fallback if reported.

---

### 5. Trial Registry Write Silently Fails on Non-Admin

**Location:** `core/license/trial.py:_reg_write()`, `_hidden_write()`  
**Symptom:** On machines where `HKCU` writes are restricted (some enterprise group policies), registry writes fail silently. The file-based storage (Layer 1) still works.  
**Actual risk:** Low. `HKCU` writes are normally user-level and don't require admin. With three-layer storage, file-only still prevents trivial trial reset. Clock rollback protection also still applies via file layer's `last_seen`.  
**Fix if needed:** Add a warning log on registry write failure.

---

### 6. `customers.json` Not Atomic on Write

**Location:** `tools/customer_store.py:save()`  
**Symptom:** If the process is killed mid-write, `customers.json` could be partially written and corrupted.  
**Current implementation:** Direct `json.dump()` to the file — not atomic.  
**Risk:** Low in practice (admin tool on developer machine), but could lose data.  
**Fix if needed:** Write to a temp file, then `os.replace()` — atomic on all major OS.

---

### 7. Fake Customer Cleanup Doesn't Remove `customers_backup_*` Files

**Location:** `tools/generate_fake_customers.py:cmd_cleanup()`  
**Symptom:** Each cleanup run leaves a `customers_backup_before_cleanup_*.json` file in `tools/`. Multiple runs accumulate backup files.  
**Design intent:** The backup is kept deliberately (safety net). But old backups from previous fake runs can be deleted manually.  
**Fix if needed:** After successful cleanup, offer to delete backups older than N days.

---

## Edge Case Risks

### A. Module Added to Registry But Missing adapter.py

If a new entry is added to `MODULE_REGISTRY` in `core/router.py` without creating `modules/<id>/adapter.py`, the router returns an error widget (`⚠ Modül yüklenemedi`) and the sidebar shows the module as `locked`. This is handled gracefully — no crash.

### B. license.json Deleted Mid-Session

If `%APPDATA%\ContraCore\license.json` is deleted while the app is running, the next `load_license()` call returns `None`. The module continues running (license was already checked at load time). On next startup, the module will ask for activation.

### C. Two ContraCore Instances Simultaneously

Both would share `%APPDATA%\ContraCore\license.json` and read/write it concurrently. No file locking is implemented. Last-write wins. In practice, only one instance runs at a time.

### D. Very Long Customer Names in Table

The `Firma Adı` column is fixed at 180px. Very long names are clipped without a tooltip. No overflow handling exists.

### E. HWID Contains Non-ASCII Characters (Non-Windows)

On Linux/Mac, HWID falls back to `platform.node() + platform.processor()`, which could contain non-ASCII hostnames. `hashlib.sha256(raw.encode())` handles this correctly via UTF-8 encoding, but the resulting HWID may be unexpected.

### F. Key Generator: Süresiz (Eternal) Date

`ETERNAL_DATE = datetime(2099, 12, 31)`. A key with this expiry will encode `days = (2099-12-31 - 2020-01-01).days = 29219`. This fits in 24 bits (max ~45.5 years from epoch). The year 2065 is the true ceiling — keys generated with expiry > 2065 would overflow the 24-bit counter.

---

## Future Attention Points

### Security: No Key Revocation

Once a V2 key is delivered and validated, there is no way to remotely revoke it. If a key is leaked or a customer dispute arises, the only option is to wait for expiry. **Consider:** if a cloud revocation list is ever added, it must be optional/graceful (offline validation must still work).

### Security: Nuitka Build Still Extractable

Nuitka compiles Python to C, which makes extraction harder than a PyInstaller onefile, but not impossible. A determined attacker with the right tools can still extract `_secret.py` values. For higher security: consider moving secret storage to Windows DPAPI or a platform keystore.

### Scalability: CustomerStore Loads All Customers into Memory

`CustomerStore._data` holds the entire `customers.json` in RAM. With thousands of customers this is fine (JSON is compact), but at ~100k+ records, startup load time and search performance would degrade. Add pagination/indexing if the database grows significantly.

### Updater: Not Integrated at Shell Level

The updater is per-module (xml-fatura only). There is no ContraCore-level update mechanism. If a new module is added or shell code changes, users get no update notification. Consider a shell-level version check in a future release.

### Trial: No Server-Side Verification

Trial data is purely local (three-layer storage). The hidden registry layer's machine-derived CLSID path is unknown to generic cleanup scripts, and clock rollback is blocked by `last_seen` quota saturation. A sufficiently motivated attacker with hex editing skills could potentially bypass, but casual bypass via bat scripts is blocked. For stricter enforcement, a server-side usage record would be needed.
