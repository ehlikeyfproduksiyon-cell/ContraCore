# ContraCore — Technical Architecture

**Last updated:** 2026-05-25

---

## High-Level Layout

```
┌─────────────────────────────────────────────────────────────┐
│                      ContraCore Process                     │
│                                                             │
│  main.py → QApplication → Shell (QMainWindow)               │
│                                                             │
│  ┌──────────────┬──────────────────────────────────────┐    │
│  │   Sidebar    │        QStackedWidget                │    │
│  │   (265px)    │  ┌───────────────────────────────┐   │    │
│  │              │  │  Module Widget (centralWidget) │   │    │
│  │  [xml-fat.]  │  │  (xml-fatura or compare-191)  │   │    │
│  │  [191-kars.] │  │                               │   │    │
│  │              │  │  _cc_host_window → host obj   │   │    │
│  │  [Lisans Yön]│  └───────────────────────────────┘   │    │
│  └──────────────┴──────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

---

## Component Breakdown

### 1. Shell (`core/shell.py`)

**Role:** Master container. Owns sidebar + stacked widget. Manages module lifecycle.

**Key attributes:**
```python
_router        : ModuleRouter          # Loads adapters and widgets
_stacked       : QStackedWidget        # Holds all module widgets
_stack_index   : dict[str, int]        # module_id → stack index
_active_module : str | None            # Currently visible module
_sidebar       : Sidebar
```

**Lifecycle methods on host windows (optional — modules don't have to implement):**
```python
host.on_module_activated()    # called when user switches to this module
host.on_module_deactivated()  # called when user switches away
```
Shell calls these via `_call_lifecycle()` which uses `getattr` — safe if not implemented.

**showEvent timing fix:**
```python
QTimer.singleShot(0,  self._initial_layout_refresh)
QTimer.singleShot(50, self._initial_layout_refresh)
```
This handles a Qt6 + QMainWindow embed quirk where the geometry isn't final at first paint.

---

### 2. ModuleRouter (`core/router.py`)

**Role:** Lazy-load factory. Imports adapters via `importlib.util`, caches widgets.

**Flow:**
```
router.load('xml-fatura')
  → already in _cache? → return cached widget
  → _load_module('xml-fatura')
      → find entry in MODULE_REGISTRY
      → _import_adapter(entry)
          → load modules/xml-fatura/adapter.py
          → register as sys.modules['cc_adapter_xml_fatura']
      → adapter.get_embedded_widget(parent=shell)
          → returns (central_widget, host_window)
      → store host in _hosts (GC protection)
  → cache widget
  → return widget
```

**sys.modules key pattern:** `cc_adapter_{id.replace('-', '_')}`

**Error handling:**
- Adapter file missing → `_error_widget("...yüklenemedi")`
- Adapter import exception → prints error, returns error widget
- `get_embedded_widget()` returns `(None, None)` → `_activation_cancelled_widget()`

**`invalidate(module_id)`:** Removes from `_cache` and `_hosts`. Called before `reload_module()` so the widget is rebuilt fresh after activation.

---

### 3. Sidebar (`core/sidebar.py`)

**Role:** Navigation + license status display.

**Animation system:**
```python
_anim     = QPropertyAnimation(self, b'maximumWidth')  # 265px ↔ 64px
_anim_min = QPropertyAnimation(self, b'minimumWidth')  # same target
# Both run simultaneously → smooth collapse without layout jump
duration = 280ms, easing = InOutCubic
```

**ModuleItem state machine:**
```
state = 'licensed' | 'trial' | 'locked'

licensed + active  → gold glow (QGraphicsDropShadowEffect, blur=20)
                   → gradient background: accent_t → NAVY2
                   → active indicator bar (3x36px) in accent color

licensed + inactive → no glow, transparent bg, white-dim text

trial + active     → amber glow, gradient bg with accent
trial + inactive   → no glow, amber text, "TRIAL" badge visible

locked            → grey text, forbidden cursor
                  → click → lock_clicked(module_id) → activation dialog
```

**Signal flow:**
```
ModuleItem.clicked(module_id)
  → Sidebar._on_item_clicked()
  → Sidebar.set_active(module_id)
  → Sidebar.module_selected.emit(module_id)
  → Shell._on_module_selected(module_id)

ModuleItem.lock_clicked(module_id)
  → Sidebar._on_lock_clicked()
  → Sidebar.activation_requested.emit(module_id)
  → Shell._on_activation_requested(module_id)

Footer "Lisans Yönet" button
  → Sidebar.activation_requested.emit('')   # empty string = general
  → Shell._on_activation_requested('')
```

**State update after activation:**
```python
Shell._on_license_activated(module_id)
  → _compute_module_states()     # re-queries ALL adapters (no GUI load)
  → sidebar.update_module_states(states)  # updates all ModuleItems
  → reload_module(module_id)
```

---

### 4. License System

See [LICENSE_SYSTEM.md](LICENSE_SYSTEM.md) for full detail.

Brief flow:
```
validator.py  — V2 key parse + HMAC verify + expire + HWID + module check
storage.py    — license.json read/write with HMAC signature
manager.py    — public API: activate_module(), check_module_license()
trial.py      — trial state in AppData + Windows registry (dual write)
hwid.py       — Windows MachineGuid → SHA256 → XXXX-XXXX-XXXX-XXXX
_secret.py    — XOR-encoded first half of HMAC secret
_secret_b.py  — plain second half of HMAC secret
```

---

### 5. Adapter Structure

Each module in `modules/<id>/adapter.py` follows this contract:

```python
_MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
_MODULE_ID  = 'xml-fatura'

def _load_unique(key, filename):
    """Load a module file under a unique sys.modules key."""

def _install_license_shim():
    """Install sys.modules['license'] pointing to unified manager."""
    shim = types.ModuleType('license')
    shim.check_license    = lambda: manager.check_module_license(_MODULE_ID)
    shim.add_trial_usage  = lambda count: trial.add_trial_usage(_MODULE_ID, count)
    shim.get_trial_status = lambda: trial.get_trial_status(_MODULE_ID)
    shim.TRIAL_MAX_FILES  = trial.get_trial_max_files(_MODULE_ID)
    sys.modules['license'] = shim

def activate_module_context():
    _install_license_shim()
    sys.modules['gui'] = _load_unique('cc_gui_xml_fatura', 'gui.py')

def get_license_status() -> dict: ...
def run_activation_dialog(parent=None) -> dict: ...
def get_embedded_widget(parent=None) -> tuple[QWidget|None, object|None]: ...
```

**The shim pattern** lets the original `gui.py` call `from license import check_license` as if it's a standalone app, while actually routing through the unified `core.license.manager`.

---

### 6. Worker / Thread Architecture

ContraCore does not own any threads directly. Threads belong to the host windows:

| Module | Thread attribute | Type | Purpose |
|---|---|---|---|
| xml-fatura | `worker` | QThread | Main processing worker |
| xml-fatura | `_upd_checker` | QThread | Update check |
| xml-fatura | `fc_a._counter`, `fc_s._counter`, `fc_c._counter` | QThread | Folder file counting |
| xml-fatura | `stop_flag` | `threading.Event` | Stop signal |
| compare-191 | `worker` | QThread | Main processing worker |
| compare-191 | `_duzelt_worker` | QThread | Correction worker |
| compare-191 | `_stop_flag` | `threading.Event` | Stop signal |

**Shutdown sequence (Shell.closeEvent → _stop_host_threads):**
```
1. Set stop_flag / _stop_flag (both names tried with getattr)
2. worker.quit() → wait(3000ms) → terminate() if not stopped
3. _duzelt_worker.quit() → wait(2000ms) → terminate()
4. fc_a/b/c._counter.quit() → wait(1000ms)
5. _upd_checker.quit() → wait(1000ms)
```

---

### 7. Popup / Dialog Parenting

- `LicenseManagerDialog` is always parented to `Shell` (the `QMainWindow`), not to the module widget. This ensures it appears centered over the whole application.
- Module-internal dialogs are parented to the host window or module widget — they don't interact with Shell.
- `QDialog.exec()` is used (blocking modal) for all license dialogs.

---

### 8. Module Isolation

Two modules can have files with the same name (`gui.py`, `license.py`, `activation.py`). Isolation is maintained by:

1. **`importlib.util` + unique sys.modules keys** — each file gets a unique registry key
2. **`_install_license_shim()`** — overwrites `sys.modules['license']` with the correct module's context whenever a module is activated
3. **`_MODULE_DIR` in sys.path** — each adapter prepends its own directory so relative imports within the module work
4. **`_load_unique(key, filename)`** — checks `sys.modules` first, only loads once

**Risk:** `sys.modules['license']` is a shared slot. If both modules run code simultaneously (e.g. a background thread calls `from license import ...` while the user switches modules), there is a race condition. This is unlikely in practice since only one module is active at a time and background threads don't import `license` dynamically.

---

## Data Flow Diagrams

### Module Load Flow

```
User clicks sidebar item
        │
        ▼
Shell._on_module_selected(mid)
        │
        ├── if mid == _active_module → return (no-op)
        │
        ├── _call_lifecycle(_active_module, 'on_module_deactivated')
        │
        ├── if mid not in _stack_index:
        │       router.load(mid, parent=self)
        │           → adapter.get_embedded_widget()
        │               → license check → trial check → maybe dialog
        │               → _install_license_shim()
        │               → load gui.py → MainWindow()
        │               → extract centralWidget
        │               → central._cc_host_window = host
        │           → stacked.addWidget(central)
        │           → _stack_index[mid] = idx
        │
        ├── stacked.setCurrentIndex(idx)
        ├── _active_module = mid
        ├── _activate_module_license(mid)   # update sys.modules['license']
        └── _call_lifecycle(mid, 'on_module_activated')
```

### Activation Flow

```
Shell._on_activation_requested(module_id)
        │
        ▼
LicenseManagerDialog.exec()   [modal]
        │
        ├── Shows HWID, module statuses, key input
        │
        ├── User enters key → _activate()
        │       → manager.activate_module(module_id, key)
        │           → validator.validate_v2_key(key, module_id)
        │               [parse → integrity → expire → hwid → module]
        │           → storage.write_module_entry(...)
        │               → load_license() → update → sign → save
        │       → emit module_activated(module_id)
        │
        └── Shell._on_license_activated(module_id)
                → _compute_module_states()  [queries all adapters]
                → sidebar.update_module_states(states)
                → reload_module(module_id)
                    → remove old widget from stack
                    → router.invalidate(module_id)
                    → router.load(module_id) → rebuild
                → sidebar.set_active(module_id)
```

### Trial State Machine

```
First load of module (no license, no trial)
        │
        ▼
adapter.get_embedded_widget()
  → trial.is_trial_started() == False
  → trial.start_trial()
      → write %APPDATA%\ContraCore\trial_xml_fatura.json
      → write HKCU\Software\ContraCore\Trial\xml_fatura
  → trial.get_trial_status()
      → merge file + registry data (most restrictive wins)
      → return (aktif=True, kalan_gun, islenen, kalan_dosya)
  → pass trial_status to MainWindow()

Each file processed:
  → license_shim.add_trial_usage(count)
  → trial.add_trial_usage(module_id, count)
  → increments used_files in both storage locations

Trial expired (days or files exhausted):
  → get_trial_status() returns aktif=False
  → next load → run_activation_dialog()
```
