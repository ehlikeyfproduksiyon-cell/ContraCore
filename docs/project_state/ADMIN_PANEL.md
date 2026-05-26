# ContraCore — Admin Panel (License Manager)

**Last updated:** 2026-05-25

> **!! MÜŞTERİYE GÖNDERİLMEZ !!**  
> `tools/license_manager.py` is a developer-only tool. Never include it in the customer build.

---

## Overview

The Admin Panel is a standalone PySide6 application (`tools/license_manager.py`) for managing customer licenses. It runs separately from ContraCore — it is not embedded inside the shell.

Entry: `python tools/license_manager.py` or `release/LicenseManager/ContraCORE License Manager.exe`

---

## Architecture

```
MainWindow (QMainWindow)
│
├── tools/widgets/sidebar.py        ← left nav, 7 pages
│
└── QStackedWidget
      ├── [0] DashboardPanel        ← stats + expiring + activity
      ├── [1] Customers Page        ← QSplitter: table | details
      │         ├── CustomerTablePanel
      │         └── CustomerDetails
      ├── [2] LicenseGeneratorPanel ← key generation
      ├── [3] RestorePanel          ← HWID restore
      ├── [4] Expiring Page         ← expiring licenses list
      ├── [5] TrialPanel            ← trial management
      └── [6] LogsPanel             ← log viewer
```

**Page map** (page_id → stack index):
```python
{'dashboard': 0, 'customers': 1, 'generate': 2,
 'restore': 3, 'expiring': 4, 'trial': 5, 'logs': 6}
```

---

## Customer Database (`tools/customers.json`)

### Customer Schema

```json
{
  "customer_id": "A1B2C3D4",         // 8 char UUID prefix, uppercase
  "name":        "ABC Muhasebe Ltd.",
  "hwid":        "XXXX-XXXX-XXXX-XXXX",
  "modules": {
    "xml-fatura": {
      "key":         "V2-XXXXXXXX-XXXXXXXX-XXXXXXXX-XXXXXXXX",
      "expire":      "2027-05-25",
      "tier":        "pro",
      "issued_date": "2026-05-25"
    },
    "compare-191": { ... }
  },
  "history": [
    {
      "date":   "2026-05-25 14:30:00",
      "action": "key_generated",
      "module": "xml-fatura",
      "key":    "V2-...",
      "expire": "2027-05-25",
      "hwid":   "XXXX-XXXX-XXXX-XXXX",
      "tier":   "pro",
      "note":   ""
    }
  ],
  "trial": {
    "xml-fatura": {
      "start_date": "2026-04-01",
      "used": 150
    }
  },
  "notes":      "Muhasebe firması, Ankara",
  "created_at": "2026-05-25",
  "is_fake":    false   // only present on test data, true for fake records
}
```

### History Actions

| action | When |
|---|---|
| `key_generated` | New key issued from generator |
| `restore` | HWID changed, new key issued |
| `customer_added` | Customer first created |
| `trial_updated` | Trial parameters changed |

### CustomerStore (`tools/customer_store.py`)

Singleton: `STORE = CustomerStore()` at module level.

Key methods:
- `get_all()` → all customers as list
- `get_by_id(customer_id)` → dict or None
- `get_by_hwid(hwid)` → dict or None (case-insensitive)
- `add_customer(name, hwid, notes)` → new customer dict
- `update_customer(customer_id, **kwargs)` → bool
- `delete_customer(customer_id)` → bool
- `set_module_license(customer_id, module_id, key, expire, tier, issued_date)` → bool
- `set_trial(customer_id, module_id, start_date, used)`
- `add_history(customer_id, action, **extra)`
- `search(query)` → filters by name, hwid, notes (case-insensitive)
- `get_expiring_soon(days=30)` → sorted list of expiring module entries
- `stats()` → `{total, active, expiring, trial, today_gen, restored}`

---

## Pages

### Dashboard (`tools/widgets/dashboard.py`)

- **Stats row** (`stats_cards.py`): 6 cards — Total Customers, Active Licenses, Expiring (30d), Trial Only, Generated Today, Total Restored
- **Expiring Soon**: scrollable list of licenses expiring in ≤60 days, color-coded (red ≤7d, amber ≤30d, green >30d)
- **Recent Activity**: last 25 history entries across all customers, sorted by date

`refresh()` re-queries store on every page switch.

### Customer Table (`tools/widgets/customer_table.py`)

- QTableWidget with 10 columns: Firma Adı, HWID, Modüller, Bitiş, Kalan Gün, Trial, Tier, İssued, Son İşlem, Notlar
- Columns 3–4 (expiry + days left) color-coded by days remaining
- Live search (QLineEdit → `store.search(query)`)
- "Yeni Müşteri" button opens `_AddCustomerDialog` (name + hwid + notes)
- Row selection emits `customer_selected(dict)` → CustomerDetails panel
- Sorting enabled on all columns

**Primary module selection:** For customers with multiple modules, picks the one with the soonest expiry date for display in the table.

### Customer Details (`tools/widgets/customer_details.py`)

- Right panel (in QSplitter with CustomerTable)
- Shows customer header (name, HWID, created date)
- Module cards: one per licensed module — key, expire date, tier, issued date, copy button
- History timeline
- Buttons: "Lisans Üret" (→ prefill generate page), "Restore Et" (→ prefill restore page)
- Signals: `request_generate(customer_id)`, `request_restore(customer_id)`

### License Generator (`tools/widgets/license_generator.py`)

**Flow:**
1. Live search QLineEdit + QListWidget — type to filter customers by name/HWID
2. Click a customer to select (`_selected_cid` tracks selection)
3. Module selector (buttons: XML Fatura / 191 Karşılaştır)
4. Duration buttons: 1 Ay / 3 Ay / 6 Ay / 1 Yıl / Süresiz — active button highlighted gold
5. OR: custom date picker (QDateEdit)
6. Tier selector (basic / pro / enterprise)
7. Notes textarea
8. "Üret" button → `_generate()`

**HWID validation logic (3 paths):**
```python
if _selected_cid:
    # Customer selected from list → use their HWID
    cid = _selected_cid
elif hwid_field.text():
    # New customer — HWID entered manually
    c = store.get_by_hwid(hwid)
    cid = c['customer_id'] if c else create_new_customer()
else:
    # No selection, no HWID → show error
    QMessageBox.warning(..., 'Listeden seçin veya HWID girin.')
    return
```

After generation: shows result card with key (copyable), HWID, expiry. Emits `license_generated` signal → main window refreshes dashboard + table.

Key generation backend: `tools/key_service.generate_and_save(store, cid, module_id, expire, tier, note)`

### Restore Panel (`tools/widgets/restore_panel.py`)

**Flow:**
1. Live search QLineEdit + `_CustomerList` (QListWidget subclass) — shows only customers WITH modules
2. Select customer → loads `_ModuleCheckCard` per module
3. Each card is fully clickable (mousePressEvent override) — click to toggle checked
4. Enter new HWID
5. "Restore Et" button

**Multi-module restore:**
```python
# Snapshot BEFORE any store changes
selected_mids = [(card.mid, card.mdata) for card in selected_cards]

# Restore each selected module
results = []
for mid, mdata in selected_mids:
    result = restore_service.restore_license(store, cid, mid, new_hwid)
    results.append(result)

# Then update UI
self._show_result(results, new_hwid)
self._load_customers()   # blockSignals to prevent cascade
self._cust_list.select_by_id(cid)
```

**Checked card style:** gold border + gold-tinted background  
**Unchecked card style:** grey border + transparent

Emits `restored` signal → main window refreshes.

### Trial Panel (`tools/widgets/trial_panel.py`)

- Lists all customers that have trial data
- Shows trial start date, used file count, remaining files/days
- Allows manual trial reset or extension (developer use)
- `_TrialCard` per customer/module

### Logs Panel (`tools/widgets/logs_panel.py`)

- Reads `tools/logs/license_manager.log`
- Displays in a QTextEdit (read-only)
- Refresh button
- Inline scrollbar styling (not using shared SCROLL_SS — it breaks QTextEdit stylesheet parser)

### Stats Cards (`tools/widgets/stats_cards.py`)

- `StatsRow`: horizontal row of 6 `_StatCard` widgets
- Each card: glass background (`rgba(255,255,255,0.04)`), top accent border, icon + value + label
- `update_stats(stats_dict)` updates all values
- Cards: 🏢 Toplam / ✅ Aktif / ⚠️ Bitiyor / 🔬 Trial / 🔑 Bugün / ♻️ Restore

---

## Key Service (`tools/key_service.py`)

```python
MODULES = {'xml-fatura': 'XML Fatura', 'compare-191': '191 Karşılaştır'}
DURATIONS = {'1 Ay': 30, '3 Ay': 90, '6 Ay': 180, '1 Yıl': 365, 'Süresiz': None}
ETERNAL_DATE = datetime(2099, 12, 31)

generate_and_save(store, customer_id, module_id, expire, tier, note) → dict
  # 1. get customer by ID → get HWID
  # 2. generate_v2_key(hwid, module_id, expire)
  # 3. store.set_module_license(...)
  # 4. store.add_history(..., action='key_generated')
  # 5. log.info(...)
  # returns {'key', 'expire', 'hwid'}
```

---

## Restore Service (`tools/restore_service.py`)

```python
restore_license(store, customer_id, module_id, new_hwid) → dict
  # 1. get customer → get existing module data → get expire date
  # 2. generate_v2_key(new_hwid, module_id, same_expire)
  # 3. store.update_customer(hwid=new_hwid)   # update HWID on customer
  # 4. store.set_module_license(new_key, ...)
  # 5. store.add_history(..., action='restore')
  # 6. log.info(...)
  # returns {'key', 'expire', 'old_hwid', 'new_hwid'}
```

The old key becomes invalid immediately (HWID mismatch). Expiry date is preserved.

---

## Fake Customer Generator (`tools/generate_fake_customers.py`)

Developer tool for stress-testing the admin panel with large datasets.

```bash
python tools/generate_fake_customers.py           # generate 1000 fakes
python tools/generate_fake_customers.py -n 500    # generate 500 fakes
python tools/generate_fake_customers.py --cleanup # remove all fakes
```

All fake records have `"is_fake": true` in the customer object. Cleanup:
1. Creates timestamped backup (`customers_backup_before_cleanup_YYYYMMDD_HHMMSS.json`)
2. Aborts if backup fails (protects real data)
3. Removes all `is_fake: true` records
4. Removes log lines containing any fake customer ID
5. Reports: real customers preserved, backup path

Real customers are never touched.

---

## Theme System (`tools/widgets/theme.py`)

Dark navy/gold design system. All widgets import from here.

Key variables:
```python
BG      = '#081631'    # main background
BG2     = '#0A1E43'    # card background
BG_DEEP = '#060E1E'    # deepest background
GOLD    = '#C8A45B'    # primary accent
GOLD_LIGHT = '#E0BA7A'
GOLD_DARK  = '#A8843B'
TEXT    = '#E8EDF5'    # primary text
TEXT2   = '#B0BBCE'    # secondary text
TEXT3   = '#6B7A91'    # tertiary text
GREEN   = '#4ADE80'
RED     = '#F87171'
AMBER   = '#FBB040'
```

Stylesheets:
- `INPUT_SS` — QLineEdit only
- `TEXTAREA_SS` — QTextEdit
- `DATE_SS` — QDateEdit (with `drop-down: none`)
- `SPIN_SS` — QSpinBox
- `BTN_GOLD` — gold gradient button
- `BTN_GLASS` / `BTN_GHOST` / `BTN_NAVY` — secondary button styles

**CSS cascade prevention:** All card frames use `QFrame#objectname {}` with `setObjectName()` — never plain `QFrame {}` — to prevent borders cascading to child widgets.

**Global reset** applied in `main()`:
```python
app.setStyleSheet('''
    QLabel  { border: none; background: transparent; }
    QWidget { border: none; }
    QFrame  { border: none; }
    QScrollArea { border: none; background: transparent; }
    QScrollArea > QWidget > QWidget { background: transparent; }
''')
```
This is required because Qt Fusion style cascades borders onto children.

---

## Logging

All key events are logged to `tools/logs/license_manager.log`:
```
2026-05-25 14:30:00  INFO      Key generated | customer=ABC Ltd module=xml-fatura expire=2027-05-25 hwid=XXXX-XXXX-XXXX-XXXX
2026-05-25 14:31:00  INFO      License restored | customer=ABC Ltd module=xml-fatura old_hwid=... new_hwid=...
```

Logger name: `license_manager` (used by both `key_service.py` and `restore_service.py`).
