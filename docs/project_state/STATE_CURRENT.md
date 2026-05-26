# ContraCore — Current Production State

**Last updated:** 2026-05-25  
**Status:** Production-ready. All core systems operational.

---

## Overview

ContraCore is a multi-module desktop application built with PySide6. It hosts independently licensed modules (currently `xml-fatura` and `compare-191`) inside a unified shell. Each module has its own GUI, license, and business logic. The shell embeds modules without modifying their source code — only an `adapter.py` file is added per module.

---

## Active Architecture

### Runtime Entry Point

```
main.py
  └── Shell()         ← QMainWindow
        ├── Sidebar   ← collapsible nav, 3-state per module
        └── QStackedWidget
              ├── [0] xml-fatura widget   (lazy-loaded)
              └── [1] compare-191 widget  (lazy-loaded)
```

**main.py** sets `ROOT_DIR` via `__file__`, adds it to `sys.path`, launches `QApplication`, creates `Shell`, calls `shell.show()`.

### Shell System (`core/shell.py`)

- `Shell` extends `QMainWindow`
- On init: creates `ModuleRouter`, `QStackedWidget`, calls `_setup_ui()` then `_open_default_module()`
- `_setup_ui()`: reads `router.registry()`, calls `_compute_module_states()` (queries each adapter without loading GUI), builds `Sidebar`
- `_open_default_module()`: loads first registry entry into stack, activates it
- Module switching via `_on_module_selected(module_id)`:
  1. Calls `on_module_deactivated` lifecycle hook on current module
  2. If not in cache → `_load_into_stack()`
  3. `QStackedWidget.setCurrentIndex(idx)`
  4. Calls `_activate_module_license()` to update `sys.modules['license']` shim
  5. Calls `on_module_activated` lifecycle hook
- `reload_module(module_id)`: removes widget from stack, calls `router.invalidate()`, re-loads. Called after activation dialog succeeds.
- `closeEvent`: gracefully stops all worker threads per module (checks `stop_flag`, `_stop_flag`, `worker`, `_duzelt_worker`, `fc_a/b/c._counter`, `_upd_checker`)

### Router / Lazy-Load (`core/router.py`)

- `MODULE_REGISTRY` list defines all modules:
  ```python
  {'id': 'xml-fatura', 'label': 'XML Fatura', 'icon_file': 'xml.png',
   'adapter_dir': 'xml-fatura', 'adapter_mod': 'adapter', 'accent_color': '#F6C244'}
  ```
- `ModuleRouter.load(module_id)` → checks `_cache`, else calls `_load_module()`
- `_import_adapter(entry)`: loads `modules/<adapter_dir>/adapter.py` via `importlib.util`, registers as `sys.modules['cc_adapter_<id>']` (e.g. `cc_adapter_xml_fatura`)
- `adapter.get_embedded_widget(parent)` → returns `(QWidget, host_window)` or `(None, None)` if activation cancelled
- Widget stored in `_cache`, host stored in `_hosts` (GC protection)

### Module Adapter Interface

Each module's `adapter.py` must implement:

| Function | Purpose |
|---|---|
| `get_embedded_widget(parent)` | Returns `(central_widget, host_window)` or `(None, None)` |
| `get_license_status()` | Returns dict with `valid`, `trial_active`, `expire`, `trial_status`, `needs_activation` |
| `run_activation_dialog(parent)` | Opens `LicenseManagerDialog` focused on this module |
| `activate_module_context()` | Updates `sys.modules['license']` shim + `sys.modules['gui']` |

The central widget returned must have `central._cc_host_window = host` set so Shell can call lifecycle hooks.

### Sidebar System (`core/sidebar.py`)

- 265px expanded ↔ 64px collapsed, 280ms `InOutCubic` animation via `QPropertyAnimation`
- Two animations run in parallel: `maximumWidth` and `minimumWidth`
- `ModuleItem` per module: 76px tall, shows name + status line + right icon
- **3 states:**
  - `licensed` → gold glow when active, white-dim when inactive
  - `trial` → amber text, "TRIAL" badge, same glow pattern as licensed
  - `locked` → grey text, forbidden cursor, click emits `lock_clicked` → triggers activation dialog
- Active item: `QGraphicsDropShadowEffect` glow in module's accent color
- Logo section: large logo (expanded) ↔ small icon (collapsed), toggle chevron button
- Footer (expanded): "Lisans Yönet" gold button + version label
- Footer (collapsed): 🔑 emoji button
- Signals: `module_selected(str)`, `activation_requested(str)`

### License Activation Flow (End-User)

```
User clicks locked module or "Lisans Yönet" button
  → Shell._on_activation_requested(module_id)
  → LicenseManagerDialog(module_registry, focused_module, parent=shell)
  → User enters V2 key → _activate()
  → core.license.manager.activate_module(module_id, key)
  → validate_v2_key() → write_module_entry()
  → dialog emits module_activated(module_id)
  → Shell._on_license_activated()
  → sidebar.update_module_states() (re-queries all adapters)
  → shell.reload_module(module_id)
  → sidebar.set_active(module_id)
```

### Module Embedding (xml-fatura example)

```python
# adapter.py
def get_embedded_widget(parent=None):
    # 1. Check license
    valid, _, expire = manager.check_module_license('xml-fatura')
    if not valid:
        # 2. Check trial; auto-start if first run
        aktif, kalan_gun, islenen, kalan = trial.get_trial_status('xml-fatura')
        if not aktif and not trial.is_trial_started('xml-fatura'):
            trial.start_trial('xml-fatura')
            ...
        if not aktif:
            # 3. Run activation dialog
            result = run_activation_dialog(parent)
            if not result['activated']:
                return None, None
    # 4. Install license shim
    activate_module_context()
    # 5. Load gui.py, create MainWindow
    host = gui.MainWindow(expire_date=expire, trial_status=trial_status)
    # 6. Hide tray (not applicable in embedded mode)
    host._tray.hide()
    # 7. Extract centralWidget, tag with host reference
    central = host.centralWidget()
    central._cc_host_window = host
    return central, host
```

### sys.modules Isolation

Each adapter uses unique keys to prevent name collision:

| sys.modules key | Content |
|---|---|
| `cc_adapter_xml_fatura` | xml-fatura adapter module |
| `cc_adapter_compare_191` | compare-191 adapter module |
| `cc_gui_xml_fatura` | xml-fatura gui.py |
| `cc_gui_compare_191` | compare-191 gui.py |
| `license` | Current active module's license shim (updated on switch) |

### Updater System

- `modules/xml-fatura/updater.py` runs as a background thread inside the host window
- Shell's `closeEvent` catches it via `_upd_checker` attribute
- Updater is per-module; not a ContraCore-level system
- compare-191 does not currently have an updater

### Release / Build System

See [BUILD_PIPELINE.md](BUILD_PIPELINE.md) for full details.

Two separate executables:
- `release/ContraCORE/ContraCORE.exe` — customer-facing product
- `release/LicenseManager/ContraCORE License Manager.exe` — developer-only tool

### Admin Panel System

`tools/license_manager.py` — standalone developer tool, **never ships to customers**.  
See [ADMIN_PANEL.md](ADMIN_PANEL.md) for full details.

---

## Current Module Registry

| ID | Label | Accent | Status |
|---|---|---|---|
| `xml-fatura` | XML Fatura | `#F6C244` | Production |
| `compare-191` | 191 Karşılaştır | `#4DCC78` | Production |

---

## Recent Changes (2026-05-25)

### Trial System — v2 Overhaul
- **3-layer storage:** AppData JSON + open registry + hidden CLSID registry (machine-derived path)
- **Machine-bound HMAC:** `machine_id[:12]:start_date:used_files` — invalid on other machines
- **Clock rollback protection:** `last_seen` field signed separately; rollback > 5 min saturates quota permanently
- **compare-191 quota:** now counts muavin **rows** (not files), limit 5000 rows

### Bug Fixes (5 items)
1. **XML fatura UI freeze:** `get_trial_status()` was called on every `_on_stats` signal. Now `_trial_quota` cached once at `_start()`.
2. **191 trial partial results:** When quota < file rows, truncates at invoice boundary, delivers results, then shows quota-full log.
3. **DonutChart animation:** Replaced step-based linear with time-based ease-out cubic (`1-(1-t)³`).
4. **Detayları gör delay:** Lazy-populate — category content built only on first click, not at dialog open.
5. **Expired trial placeholder:** Router shows "Deneme Sürümünüz Bitti" widget (with ⏰ icon) when trial expired, instead of generic locked message.

---

## Data Locations (Runtime)

| Data | Location |
|---|---|
| License file | `%APPDATA%\ContraCore\license.json` |
| Trial data (layer 1) | `%APPDATA%\ContraCore\trial_<module_id>.json` |
| Trial backup (layer 2) | `HKCU\Software\ContraCore\Trial\<module_id>` |
| Trial hidden (layer 3) | `HKCU\Software\Classes\CLSID\{machine-derived-guid}` |
| Customer database | `tools/customers.json` |
| License manager log | `tools/logs/license_manager.log` |

---

## Asset Directory Structure (Runtime)

```
ContraCORE/              ← release root
├── ContraCORE.exe
├── Icon/                ← UI images (xml.png, 191m.png, lock.png, etc.)
├── Logom/               ← Logo assets
│   ├── ico/             ← .ico files
│   └── big_logo/        ← sidebarlogo.png, ContraCore.png
└── modules/
    ├── xml-fatura/      ← module runtime assets (non-Python)
    └── compare-191/     ← module runtime assets (non-Python)
```
