# ContraCore — DO NOT REINTRODUCE

**Last updated:** 2026-05-25

> **Bu dosya Claude ve gelecekteki geliştiriciler için kritik bir referanstır.**  
> Aşağıdaki sistemler bilinçli olarak kaldırılmıştır. Yeniden eklenmemeli.

---

## 1. V1 License System

**What it was:** An earlier license format (no `V2-` prefix, different byte layout, weaker HMAC structure).

**Where it existed:** `modules/xml-fatura/license.py` and `modules/compare-191/license.py` in their original standalone form, before the unified `core/license/` system was built.

**Why removed:**
- No module binding (a key for xml-fatura could theoretically validate for compare-191)
- No proper HWID embedding in the key bytes
- Secret was a single plaintext string in one file
- No JSON signature on `license.json` — file could be manually edited

**Current replacement:** `core/license/validator.py` V2 format — HMAC-SHA256 with HWID + module binding + JSON HMAC signature.

**Do not:** Add a V1 compatibility fallback, try to parse keys without the `V2-` prefix, or read unsigned `license.json` files as trusted.

---

## 2. Module-Internal Keygen (`modules/*/keygen.py` and `modules/*/keygen.py.disabled`)

**What it was:** Each module (`xml-fatura`, `compare-191`) had its own `keygen.py` that could generate license keys using the module's internal secret.

**Where it exists now:** Still present as files (`modules/xml-fatura/keygen.py`, `modules/compare-191/keygen.py`) but **not used by anything**. The `keygen.py.disabled` files are dead code.

**Why removed from active use:**
- Generated keys used the old secret and format
- Each module had a different secret → keys were not interoperable with the unified system
- Admin panel's `tools/key_service.py` replaces all keygen functionality using `core/license/validator.generate_v2_key()`

**Do not:** Call `modules/*/keygen.py` from anywhere. Do not use their `generate_key()` functions. Do not import them. If they become confusing, delete them — they are not needed.

---

## 3. Module-Internal `activation.py`

**What it was:** `modules/xml-fatura/activation.py` and `modules/compare-191/activation.py` — standalone activation dialogs specific to each module, containing their own UI for entering license keys.

**Current status:** Files still exist but are **bypassed**. The adapters call `core/license/activation_dialog.LicenseManagerDialog` instead.

**Why removed:**
- Each module's activation dialog was a separate, inconsistent UI
- Could not handle multi-module activation (only knew about one module)
- Duplicated HWID display and key validation logic
- No connection to the unified `core/license/manager`

**Current replacement:** `core/license/activation_dialog.py` — a single unified dialog that shows all module statuses, handles activation for any module, and emits `module_activated(module_id)` to Shell.

**Do not:** Call `modules/*/activation.py` from adapters or shell. Do not import the old activation dialogs. Do not create per-module activation dialogs.

---

## 4. Module-Internal `license.py` (Old Standalone Version)

**What it was:** `modules/xml-fatura/license.py` and `modules/compare-191/license.py` — the modules' original license check code, designed for standalone use.

**Current status:** Files still exist but are **shimmed out**. The adapter installs a `sys.modules['license']` shim that routes all `from license import ...` calls to `core/license/manager` and `core/license/trial`.

**Why shimmed instead of removed:**
- `gui.py` for each module still does `from license import check_license, add_trial_usage, ...`
- Modifying `gui.py` would require touching the module's core code
- The shim allows the module GUI to remain unchanged while routing to the unified system

**Do not:** Let the modules' `license.py` be imported directly. Do not remove the `_install_license_shim()` call from adapters. Do not add direct imports of `modules/*/license.py` anywhere in `core/` or `tools/`.

---

## 5. Dual-Path Adapter System (Old Design)

**What it was:** An earlier adapter design where the adapter would check the license itself and then conditionally call either a "licensed path" or a "trial path" through different code branches with different UI initializations.

**Why replaced:**
- Logic was duplicated across both adapters
- Trial auto-start was inconsistent
- The activation dialog was called from inside `get_embedded_widget()` in a way that made it hard to differentiate between "user cancelled" and "needs activation"

**Current design:** `get_embedded_widget()` has a single clear flow:
```
check license → if valid: build host
             → if not valid: check trial → if active: build host with trial_status
                                        → if expired: run_activation_dialog()
                                          → if activated: re-check, build host
                                          → if cancelled: return (None, None)
```

**Do not:** Add multiple code paths inside `get_embedded_widget()` based on license tier/type. Keep the flow linear. The adapter should not contain business logic beyond license routing.

---

## 6. QComboBox for Customer Selection (Admin Panel)

**What it was:** Both `LicenseGeneratorPanel` and `RestorePanel` originally used `QComboBox` populated with all customer names for selection.

**Why replaced:**
- With 100+ customers, scrolling a combo box is unusable
- QComboBox triggers `currentIndexChanged` signal during programmatic population (e.g. `blockSignals` was needed everywhere)
- No search/filter capability

**Current replacement:**
- `QLineEdit` (search input) + `QListWidget` (results) — live filtering as user types
- `_CustomerList` subclass in `restore_panel.py` with a `customer_selected = Signal(str)` and a `select_by_id()` method
- `LicenseGeneratorPanel` uses `_selected_cid: str | None` to track selection state

**Do not:** Reintroduce QComboBox for customer selection. Do not use QComboBox for any list that can have more than ~20 items.

---

## 7. QCheckBox Inside Module Cards (Restore Panel)

**What it was:** `_ModuleCheckCard` originally contained a `QCheckBox` widget inside the card. The card itself was clickable, but the checkbox click area was only the small indicator square.

**Why replaced:**
- Users clicking the card body (outside the tiny checkbox square) did not toggle the checkbox
- `isChecked()` returned the checkbox state, not whether the user intended to select it
- The visual feedback was inconsistent — card looked selected but checkbox wasn't toggled

**Current replacement:** `_ModuleCheckCard` has no `QCheckBox`. It maintains `self._checked: bool` internally and toggles it in `mousePressEvent()`. The entire card surface is the clickable area. Visual state (gold border/background vs grey) updates via `_apply_style()`.

**Do not:** Re-add `QCheckBox` to module cards. Do not use any widget whose click area is smaller than its visual representation as a selection mechanism.

---

## 8. `blockSignals` Workarounds in Old Restore Panel

**What it was:** The original restore panel called `_load_customers()` (which repopulated the QComboBox) inside `_do_restore()`, which triggered `currentIndexChanged`, which called `_on_customer_changed()`, which called `_clear_mod_cards()` with `deleteLater()` — destroying the mod cards mid-restore.

**Why it was dangerous:**
- `selected` cards were deleted while the restore loop was still iterating over them
- Keys were not generated for all selected modules
- The bug was silent — no exception, just missing keys

**Current fix:**
```python
# Snapshot card data BEFORE any store/UI changes
selected_mids = [(card.mid, card.mdata) for card in selected_cards]
# Then do all restore operations using the snapshot
# Then update UI
self._load_customers()  # safe — uses blockSignals
```

**Do not:** Modify store or UI (especially card containers) before extracting all needed data from the current UI state. Always snapshot first.

---

## 9. `INPUT_SS.replace('QLineEdit', 'QDateEdit')` Pattern

**What it was:** The theme used a single `INPUT_SS` string for QLineEdit, and other widgets did `.replace('QLineEdit', 'QDateEdit')` to get their stylesheet.

**Why removed:**
- If `INPUT_SS` contained `QTextEdit` or `QSpinBox` substrings (which it later did), `.replace()` would corrupt them too
- Also replaced substrings inside property values, not just selectors
- Unpredictable and fragile

**Current replacement:** Separate stylesheet variables for each widget type:
- `INPUT_SS` → QLineEdit only
- `TEXTAREA_SS` → QTextEdit
- `DATE_SS` → QDateEdit (with `drop-down: none`)
- `SPIN_SS` → QSpinBox

**Do not:** Use `.replace()` on stylesheet strings to derive widget-specific styles. Add a new variable instead.

---

## 10. `QFrame { }` (Unscoped) in Widget Stylesheets

**What it was:** Cards and containers using `self.setStyleSheet('QFrame { border: 1px solid ... }')`.

**Why it causes problems:**
- Qt's stylesheet cascade: `QFrame { }` applies to ALL `QFrame` descendants of the widget, including frames inside labels, separators, etc.
- Labels inside a card would get borders; nested frames would all get the card's border style
- Visual result: stray borders appearing on text, icon areas, child widgets

**Current fix:** All card frames use `setObjectName('cardname')` and `QFrame#cardname { border: ... }`. Scoped to exactly one element.

**Global reset in `main()`:**
```python
app.setStyleSheet('''
    QLabel  { border: none; background: transparent; }
    QWidget { border: none; }
    QFrame  { border: none; }
    ...
''')
```

**Do not:** Write `QFrame { }`, `QLabel { }`, or `QWidget { }` in widget-level `setStyleSheet()` calls. Always scope with `#objectname` or use the global reset as a baseline.

---

## 11. SCROLL_SS Embedded in QScrollArea / QTextEdit setStyleSheet

**What it was:** `SCROLL_SS` was a multi-widget stylesheet block containing `QScrollBar:vertical { ... }` rules. It was embedded inside `QScrollArea.setStyleSheet(SCROLL_SS)` or `QTextEdit.setStyleSheet(... + SCROLL_SS)`.

**Why it fails:**
- Qt raises `Could not parse stylesheet of object QScrollArea` because QScrollArea's `setStyleSheet` is applied to the QScrollArea's own properties, not its child scrollbar
- Multi-widget blocks (with `QScrollBar:vertical {}` selectors) inside a single widget's stylesheet are not valid in this context

**Current fix:**
- Remove `SCROLL_SS` from QScrollArea stylesheets
- Inline scrollbar CSS directly inside QTextEdit stylesheets (where Qt does accept multi-rule blocks)
- Or use `QApplication.setStyleSheet()` for global scrollbar styling

**Do not:** Embed `SCROLL_SS` or any multi-selector block inside `widget.setStyleSheet()`. Use `app.setStyleSheet()` for global rules or inline directly in the widget stylesheet where supported.

---

## 12. Tray Icon in Embedded Mode

**What it was:** The xml-fatura module creates a `QSystemTrayIcon` (`host._tray`) in its `MainWindow.__init__()`. In standalone mode this is fine. In embedded mode (inside ContraCore shell), the tray icon appears in the system tray unexpectedly.

**Current fix:**
```python
# In adapter._build_host()
tray = getattr(host, '_tray', None)
if tray is not None:
    tray.hide()
```

**Do not:** Remove this tray hide call. Do not let module-internal system tray icons show when running embedded in Shell. If future modules also create tray icons, apply the same pattern in their adapters.
