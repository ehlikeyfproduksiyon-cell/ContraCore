# ContraCore — Build Pipeline

**Last updated:** 2026-05-25

---

## Overview

Two separate Nuitka-based build scripts produce two executables. PyInstaller is **not used** — Nuitka compiles Python to C and produces genuinely compiled code, which is harder to reverse-engineer and generally faster.

Both builds are **standalone** (not onefile): the output is a folder of files, not a single embedded EXE. This is intentional — updaters and external assets need to be accessible as real files.

---

## Prerequisites

```powershell
pip install nuitka
```

Nuitka version should be 2.x or later. Check: `python -m nuitka --version`

Also required: Visual Studio Build Tools (for the C compiler on Windows) or MinGW.

---

## Build Scripts

| Script | Output |
|---|---|
| `build_tools/build_contracore.py` | `release/ContraCORE/` |
| `build_tools/build_license_manager.py` | `release/LicenseManager/` |
| `build_tools/_build_common.py` | Shared utilities (not run directly) |

---

## Build 1: ContraCORE (Customer Build)

```powershell
python build_tools/build_contracore.py
python build_tools/build_contracore.py --clean   # wipe release/ContraCORE/ first
```

**Entry point:** `main.py`  
**Output exe:** `release/ContraCORE/ContraCORE.exe`  
**Output folder:** `release/ContraCORE/`

### Nuitka Flags

```
--standalone                   Produces a self-contained folder
--windows-disable-console      No console window (GUI app)
--lto=yes                      Link-time optimization (smaller, faster)
--jobs=4                       Parallel compile jobs
--enable-plugin=pyside6        Includes all required PySide6 plugins
--windows-product-name=ContraCORE
--windows-company-name=Serkan ŞAHİN
--windows-product-version=1.0.0.0
--windows-file-version=1.0.0.0
--windows-file-description=ContraCORE
--output-filename=ContraCORE.exe
--output-dir=<ROOT_DIR>        Nuitka writes main.dist/ here
--include-package=core         Include core package
--include-package=modules      Include modules package
--include-package-data=core    Include non-Python files in core/
--include-package-data=modules Include non-Python files in modules/
--windows-icon-from-ico=Logom/ico/ContraCoreAppRenkliBeyaz2.ico
```

### Post-Build Steps

After Nuitka finishes (outputs `main.dist/`):
1. `main.dist/` is moved to `release/ContraCORE/`
2. Runtime assets are copied into `release/ContraCORE/`:
   - `Icon/` → `release/ContraCORE/Icon/`
   - `Logom/` → `release/ContraCORE/Logom/`
   - `modules/xml-fatura/` → `release/ContraCORE/modules/xml-fatura/` (non-Python files only)
   - `modules/compare-191/` → `release/ContraCORE/modules/compare-191/` (non-Python files only)

Module asset copy skips:
- Directories: `__pycache__`, `.claude`, `build`, `dist`, `ÇALIŞAN`
- Extensions: `.pyc`, `.pyo`, `.spec`, `.bat`

---

## Build 2: License Manager (Developer Build)

```powershell
python build_tools/build_license_manager.py
python build_tools/build_license_manager.py --clean
```

**Entry point:** `tools/license_manager.py`  
**Output exe:** `release/LicenseManager/ContraCORE License Manager.exe`  
**Output folder:** `release/LicenseManager/`

### Nuitka Flags

Same core flags as ContraCORE build plus:
```
--include-package=tools        Include tools package
--include-package-data=tools   Include non-Python files in tools/
--include-package=core
--include-package-data=core
--output-filename=ContraCORE License Manager.exe
--windows-icon-from-ico=Icon/SETUP.ico
```

Nuitka outputs `license_manager.dist/` (named after the entry script).

### Post-Build Steps

1. `license_manager.dist/` moved to `release/LicenseManager/`
2. Runtime assets copied:
   - `Icon/` → `release/LicenseManager/Icon/`
   - `Logom/` → `release/LicenseManager/Logom/`
3. `tools/customers.json` copied if it exists; otherwise an empty `{"customers": []}` file is created
4. `release/LicenseManager/logs/` directory created

---

## Release Directory Structure

```
release/
├── ContraCORE/
│   ├── ContraCORE.exe
│   ├── ContraCORE.exe.manifest  (auto-generated)
│   ├── python3XX.dll
│   ├── ... (Nuitka runtime DLLs)
│   ├── PySide6/                  (Qt DLLs + plugins)
│   │   ├── platforms/
│   │   │   └── qwindows.dll      (CRITICAL — must be present)
│   │   ├── imageformats/
│   │   └── ...
│   ├── Icon/                     (copied by build script)
│   │   ├── xml.png
│   │   ├── 191m.png
│   │   ├── lock.png
│   │   └── ... (all Icon/ files)
│   ├── Logom/                    (copied by build script)
│   │   ├── ico/
│   │   │   └── ContraCoreAppRenkliBeyaz2.ico
│   │   └── big_logo/
│   │       ├── sidebarlogo.png
│   │       └── ContraCore.png
│   └── modules/
│       ├── xml-fatura/           (runtime assets, no .py files)
│       │   ├── Icon/
│       │   ├── preferences.json
│       │   └── version.txt
│       └── compare-191/          (runtime assets)
│
└── LicenseManager/
    ├── ContraCORE License Manager.exe
    ├── ... (Nuitka runtime DLLs)
    ├── PySide6/
    ├── Icon/
    ├── Logom/
    ├── customers.json            (copied or created empty)
    └── logs/                     (empty dir, log file created on first run)
```

---

## Icon Handling

Icons are resolved relative to `__file__` at runtime, not via hardcoded absolute paths:

```python
# core/shell.py
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ICON_DIR = os.path.join(ROOT_DIR, 'modules', 'xml-fatura', 'Icon')
ico_path = os.path.join(ICON_DIR, 'contralogoo.ico')
```

In a Nuitka standalone build, `__file__` resolves correctly relative to the `.exe` location. The build script copies icon files alongside the executable so the relative paths remain valid.

**Build script icon paths** (used for the exe's own icon, not runtime):
- ContraCORE: `Logom/ico/ContraCoreAppRenkliBeyaz2.ico`
- LicenseManager: `Icon/SETUP.ico`

If an icon file is missing, the build proceeds without it (warning only, not fatal).

---

## PySide6 Plugin Requirements

`--enable-plugin=pyside6` handles most of this automatically. Critical files Nuitka includes:

| File | Purpose |
|---|---|
| `PySide6/platforms/qwindows.dll` | Windows platform plugin (MUST be present) |
| `PySide6/imageformats/qpng.dll` | PNG image loading |
| `PySide6/imageformats/qico.dll` | ICO loading |
| `PySide6/Qt6Core.dll` | Qt core |
| `PySide6/Qt6Widgets.dll` | Qt widgets |
| `PySide6/Qt6Gui.dll` | Qt GUI |

If `qwindows.dll` is missing, the app fails with `This application failed to start because no Qt platform plugin could be initialized.`

---

## Path Resolution in Standalone Build

`os.path.abspath(__file__)` works correctly in Nuitka standalone builds. The exe's `__file__` points to the exe location, so relative path construction using `os.path.dirname(__file__)` is reliable.

**Verified safe patterns:**
```python
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ICON_DIR = os.path.join(ROOT_DIR, 'Icon')
```

**Do not use:** `sys._MEIPASS` (PyInstaller-specific), `__file__` without `os.path.abspath()`, hardcoded absolute paths.

---

## Updater Compatibility

The xml-fatura module's updater (`modules/xml-fatura/updater.py`) downloads and replaces files. In a standalone build:
- The updater must write to the same directory as the exe (not to a temp dir)
- The release folder structure must remain stable between updates
- Python files compiled into the exe cannot be hot-patched; the updater would need to replace the entire exe or specific asset files

**Current status:** The updater is a per-module concern. ContraCore shell does not interfere with it. The updater thread is gracefully stopped on shutdown via `_upd_checker`.

---

## Build Step-by-Step (Full Flow)

```
1. cd c:\Serkan\OTOMASYONLARIM\ContraCore

2. (Optional) python build_tools/build_contracore.py --clean
      → deletes release/ContraCORE/, main.dist/, main.build/

3. python build_tools/build_contracore.py
      → checks Nuitka installed
      → verifies Logom/ico/ContraCoreAppRenkliBeyaz2.ico exists
      → runs: python -m nuitka --standalone ... main.py
      → Nuitka compiles → outputs main.dist/ in ROOT_DIR
      → script moves main.dist/ → release/ContraCORE/
      → copies Icon/, Logom/, modules/ assets

4. Test: double-click release/ContraCORE/ContraCORE.exe

5. python build_tools/build_license_manager.py --clean
      → deletes release/LicenseManager/, license_manager.dist/, license_manager.build/

6. python build_tools/build_license_manager.py
      → same flow but for license_manager.py
      → outputs release/LicenseManager/

7. Test: double-click release/LicenseManager/ContraCORE License Manager.exe

8. Ship release/ContraCORE/ to customers.
   Keep release/LicenseManager/ for internal use only.
```

---

## What NOT to Ship to Customers

| File/Directory | Reason |
|---|---|
| `release/LicenseManager/` | Admin tool — contains key generation logic |
| `tools/` | Admin panel source code |
| `tools/customers.json` | Customer database |
| `tools/keygen.py` | Standalone key generator |
| `build_tools/` | Build scripts |
| `dev_tools/` | Dev utilities |
| `core/license/_secret*.py` | HMAC secret halves |
| `docs/` | Internal documentation |
| `.claude/` | AI assistant session data |
| Any `.py` source file | Source code |
