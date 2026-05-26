# ContraCore — License System

**Last updated:** 2026-05-25

---

## Overview

ContraCore uses a custom HMAC-SHA256 based license system (V2). There is no external license server — all validation is done locally. The secret key is split across two files with XOR obfuscation to prevent trivial reverse engineering.

---

## File Map

| File | Role |
|---|---|
| `core/license/validator.py` | Key generation + validation logic |
| `core/license/storage.py` | license.json read/write with HMAC signature |
| `core/license/manager.py` | Public API facade (the only file external code should import) |
| `core/license/trial.py` | Trial tracking (time + file count), dual storage |
| `core/license/hwid.py` | Hardware ID generation |
| `core/license/_secret.py` | First half of HMAC secret (XOR encoded) |
| `core/license/_secret_b.py` | Second half of HMAC secret (plain) |
| `core/license/activation_dialog.py` | End-user activation UI |
| `tools/key_service.py` | Admin tool: key generation + saving to customer store |
| `tools/restore_service.py` | Admin tool: license restore on HWID change |
| `tools/keygen.py` | Standalone CLI keygen (dev use only) |

---

## V2 Key Format

```
V2-XXXXXXXX-XXXXXXXX-XXXXXXXX-XXXXXXXX
```

- Total: `V2-` prefix + 32 base32 characters in 4 groups of 8
- Base32 alphabet: `A-Z2-7` (standard RFC 4648)

### Binary Layout (20 bytes total)

```
Offset  Size  Content
──────────────────────────────────────────────────────
0       1     Version byte: 0x02
1-3     3     Days since epoch (2020-01-01) — big endian 24-bit
4-11    8     HMAC-SHA256('_H', hwid)[:8]    — HWID fingerprint
12-15   4     HMAC-SHA256('_M', module_id)[:4]  — module binding
16-19   4     HMAC-SHA256('_S', body[0:16])[:4] — integrity signature
```

### Epoch

`date(2020, 1, 1)` — allows dates from 2020-01-01 to ~2045 with a 24-bit day counter.

### Grace Period

`_GRACE_DAYS = 1` — license is still valid 1 day after the expire date. Handles timezone/clock drift.

---

## HMAC Secret (`_secret.py` / `_secret_b.py`)

The HMAC key is assembled at runtime from two files:

```python
# _secret.py
_A  = bytes([...])   # XOR-encoded bytes
_KA = 0x3B           # XOR key
_fa() → bytes(x ^ _KA for x in _A).decode()  # first half

# _secret_b.py
_fb() → str   # second half (plain bytes/string)

# Combined:
_secret.get() → _fa() + _fb()
```

**Security rationale:** A single plaintext string in one file would be trivially found with `strings`. The XOR split means neither file alone reveals the secret. Both files must be present and correctly implemented for any HMAC to validate.

Do not: combine both halves into one file, add logging that prints the secret, or commit the real `_secret_b.py` to a public repo.

---

## HWID Generation (`hwid.py`)

```
Primary source (Windows):
  HKLM\SOFTWARE\Microsoft\Cryptography\MachineGuid
  → strip hyphens → uppercase → take first 16 chars
  → SHA256 hash → XXXX-XXXX-XXXX-XXXX (first 16 hex chars)

Fallback 1: wmic cpu get ProcessorId
Fallback 2: platform.node() + platform.processor()
Fallback 3: 'DEFAULT' string
```

The HWID is stable per machine (MachineGuid doesn't change on Windows without a reinstall/sysprep). It changes on OS reinstall or hardware swap — hence the restore flow.

Format: `XXXX-XXXX-XXXX-XXXX` (4 groups of 4 hex chars, uppercase).

---

## Key Validation Steps (`validator.py:validate_v2_key`)

```
1. Parse: must start with 'V2-', strip prefix, remove hyphens
2. Length check: exactly 32 base32 characters
3. Alphabet check: all chars in A-Z2-7
4. base32decode → 20 bytes
5. Version check: byte[0] == 0x02
6. Integrity: HMAC('_S', body[:16])[:4] == payload[16:20]
7. Expiry: decode days → date, check datetime.now() <= expire + 1 day
8. HWID: HMAC('_H', get_hwid())[:8] == body[4:12]
9. Module: HMAC('_M', module_id)[:4] == body[12:16]
```

If any step fails, returns `(False, error_message, None)`.  
If all pass, returns `(True, 'Lisans geçerli.', expire_datetime)`.

---

## License Storage (`storage.py`)

### File location

```
%APPDATA%\ContraCore\license.json
```

### Structure

```json
{
  "hwid": "XXXX-XXXX-XXXX-XXXX",
  "modules": {
    "xml-fatura": {
      "enabled": true,
      "expire":  "2027-05-25",
      "tier":    "pro",
      "key":     "V2-XXXXXXXX-XXXXXXXX-XXXXXXXX-XXXXXXXX"
    },
    "compare-191": { ... }
  },
  "sig": "ABCD1234ABCD1234"
}
```

### JSON Signature

Payload string format:
```
hwid|module_id_1:enabled:expire:tier:key|module_id_2:...
```
(modules sorted alphabetically by key)

Signature: `HMAC-SHA256(secret, payload)[:16].upper()` — 16 hex chars.

**Verification on load:** If `sig` doesn't match recomputed signature, `load_license()` returns `None`. If `hwid` in file doesn't match `get_hwid()`, also returns `None`. This prevents copying a license file from one machine to another.

### Write Flow

```python
write_module_entry(module_id, key, expire, tier):
  data = load_license() or {'hwid': get_hwid(), 'modules': {}}
  data['hwid'] = get_hwid()           # always refresh HWID
  data['modules'][module_id] = {...}
  save_license(data)                  # recomputes and writes sig
```

Other modules in the file are preserved untouched.

---

## Activation Flow (manager.py)

```python
manager.activate_module(module_id, key, tier='pro')
  → validator.validate_v2_key(key, module_id)
  → if valid: storage.write_module_entry(module_id, key, expire, tier)
  → returns (success, message, expire)
```

```python
manager.check_module_license(module_id)
  → storage.is_entry_valid(module_id)
      → read_module_entry(module_id)
      → check enabled==True
      → parse expire, check against now + grace
  → returns (valid, message, expire)
```

---

## Trial System (`trial.py`)

**Version:** v2 — machine-bound HMAC + three-layer storage + clock rollback protection.

### Configuration

```python
_TRIAL_CFG = {
    'xml-fatura':  {'days': 30, 'max_files': 5000},  # max_files = dosya sayısı
    'compare-191': {'days': 30, 'max_files': 5000},  # max_files = muavin SATIR sayısı
}
```

### Three-Layer Storage

Trial data is written to three locations simultaneously. On read, all three are merged and the **most restrictive** values are used (earliest start date, highest used count). This prevents trial reset by deleting any combination of storage locations.

| Layer | Location | Notes |
|---|---|---|
| 1 — File | `%APPDATA%\ContraCore\trial_<module_id>.json` | Primary, easiest to find |
| 2 — Registry (open) | `HKCU\Software\ContraCore\Trial\<module_id>` | Standard path |
| 3 — Registry (hidden) | `HKCU\Software\Classes\CLSID\{machine-derived-guid}` | GUID derived from machine fingerprint — unknown to generic cleanup scripts |

Hidden registry GUID derivation:
```python
h    = sha256(f'ccv2_{machine_id[:24]}_{module_safe}'.encode()).hexdigest()
guid = f'{{{h[0:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:32]}}}'
# → HKCU\Software\Classes\CLSID\{GUID}
```

File format (v2):
```json
{
  "v": 2,
  "start_date": "2026-05-25",
  "used_files": 47,
  "sig": "a1b2c3d4e5f6a1b2c3d4",
  "ls": "2026-05-25T14:30:00",
  "lss": "a1b2c3d4e5f6a1b2"
}
```

Registry values (open layer): `start_date`, `used_count`, `sig`, `vr`, `ls`, `lss`  
Registry values (hidden layer): `sd`, `uc`, `sg`, `vr`, `ls`, `lss` (short names)

### Machine-Bound HMAC (v2)

```python
# Main signature — covers start_date + used_files
payload = f'{machine_id[:12]}:{start_date}:{used_files}'
sig     = hmac.new(secret, payload.encode(), sha256).hexdigest()[:20]

# last_seen signature — independent field
payload_ls = f'{machine_id[:12]}:ls:{last_seen_iso}'
lss        = hmac.new(secret, payload_ls.encode(), sha256).hexdigest()[:16]
```

Any data without `v=2` and a valid machine-bound `sig` is rejected outright.

### Clock Rollback Protection

Every successful trial access records `last_seen` (ISO timestamp) signed with `lss`. On each `get_trial_status()` call:

```
now < last_seen - 300 seconds  →  CLOCK_ROLLBACK_DETECTED
```

When rollback is detected:
1. `used_files` is set to `max_files` (quota saturated) across all 3 layers
2. New HMAC signature written — tamper-proof even after clock is restored
3. Event logged to crash log
4. Returns `(False, 0, max_files, 0)` — trial permanently expired

Tolerance: **5 minutes** (safe against NTP drift, timezone changes, reboots).  
`last_seen` is updated at most every **10 minutes** to avoid excessive storage writes.

### Trial Active Condition

```python
aktif = kalan_gun > 0 and kalan_dosya > 0
# Both time AND quota must have remaining balance
```

### is_trial_started() Logic

Controls whether the "Deneme Başlat" button appears. Returns True if trial was ever started on this machine (active OR expired):

1. AppData file present and valid → `True`
2. Open registry active + valid → restore to file → `True`
3. Hidden registry present (active OR expired) → `True` (blocks re-trial on same machine)
4. Nothing found → `False`

### Usage Tracking

`compare-191` counts **muavin rows** (not files):
```python
# In _on_done():
add_trial_usage(module_id, len(result.get('muavin_rows', [])))
```

`xml-fatura` counts processed files.

---

## Restore Flow

When a customer reinstalls Windows or replaces hardware, their HWID changes. The restore service generates a new key for the same module + same expire date, but bound to the new HWID.

```python
restore_license(store, customer_id, module_id, new_hwid):
  c       = store.get_by_id(customer_id)
  mdata   = c['modules'][module_id]
  expire  = datetime.strptime(mdata['expire'], '%Y-%m-%d')
  new_key = generate_v2_key(new_hwid, module_id, expire)

  store.update_customer(customer_id, hwid=new_hwid)   # update HWID
  store.set_module_license(...)                        # store new key
  store.add_history(..., action='restore')             # log it
  return {'key': new_key, 'expire': ..., 'old_hwid': ..., 'new_hwid': ...}
```

The old key is immediately invalid (HWID mismatch). The new key uses the same expiry date — restore does not extend the license.

---

## Admin Panel Connection

The License Manager (`tools/`) does NOT write to `%APPDATA%\ContraCore\license.json`. That file is only written by the activation dialog on the customer's machine.

The admin panel maintains its own `tools/customers.json` database tracking:
- Which customers have which keys
- When keys were generated / restored
- Trial usage history

These two databases are independent. The customer's `license.json` is validated locally; the admin's `customers.json` is the developer's record-keeping system.

---

## Module Binding

A V2 key is bound to exactly one `module_id` (4-byte HMAC fingerprint). A key generated for `xml-fatura` will fail validation if presented for `compare-191`. This is checked in step 9 of `validate_v2_key`.

This means:
- A customer with both modules needs two separate keys
- The admin generates and delivers each key separately
- The activation dialog allows selecting which module to activate

---

## Security Approach

| Threat | Mitigation |
|---|---|
| Copy license.json to another machine | HWID check in `load_license()` + HMAC signature covers HWID field |
| Modify license.json manually | HMAC signature on all fields; any modification invalidates `sig` |
| Extract secret from exe | Secret split across two files; first half XOR-encoded; Nuitka compilation makes extraction harder |
| Key reuse across modules | Module ID embedded in key with HMAC binding |
| Key reuse across machines | HWID embedded in key with HMAC binding |
| Clock manipulation | `last_seen` signed with machine-bound HMAC; rollback > 5 min saturates quota permanently |
| Trial reset by deleting file/registry | Three-layer storage; hidden layer path derived from machine fingerprint |
| Trial reset by AppData + Registry wipe | Hidden CLSID registry survives generic cleanup scripts |
| Trial reset + clock rollback combo | Hidden registry `last_seen` still triggers rollback → quota saturated → expired |

**Known limitation:** No online validation or revocation. Once a key is valid on a machine, it remains valid until expiry. There is no way to remotely invalidate a key after delivery.
