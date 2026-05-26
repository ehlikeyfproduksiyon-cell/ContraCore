# ContraCore — Production Architecture

**Version:** 1.0.0  
**Last updated:** 2026-05-25  
**Purpose:** Yeni geliştirici referansı. Tüm production sistemlerin eksiksiz mimarisi.

---

## İçindekiler

1. [Genel Bakış](#1-genel-bakış)
2. [Proje Klasör Yapısı](#2-proje-klasör-yapısı)
3. [Runtime Release Yapısı](#3-runtime-release-yapısı)
4. [Shell / Router / Module İlişkisi](#4-shell--router--module-ilişkisi)
5. [modules/ Klasör Contract Yapısı](#5-modules-klasör-contract-yapısı)
6. [sys.modules İzolasyon Sistemi](#6-sysmodules-izolasyon-sistemi)
7. [Lisans Sistemi](#7-lisans-sistemi)
8. [Trial Sistemi](#8-trial-sistemi)
9. [AppData ve Registry Yapısı](#9-appdata-ve-registry-yapısı)
10. [Launcher Mimarisi](#10-launcher-mimarisi)
11. [Auto-Update Sistemi](#11-auto-update-sistemi)
12. [GitHub Release Akışı](#12-github-release-akışı)
13. [Güncelleme Sırasında Korunan Alanlar](#13-güncelleme-sırasında-korunan-alanlar)
14. [Rollback Mantığı](#14-rollback-mantığı)
15. [Build Pipeline](#15-build-pipeline)
16. [Setup / Installer Sistemi](#16-setup--installer-sistemi)
17. [Build Komutları](#17-build-komutları)
18. [Yeni Modül Ekleme Standardı](#18-yeni-modül-ekleme-standardı)

---

## 1. Genel Bakış

ContraCore, PySide6 ile yazılmış çok modüllü bir masaüstü uygulamasıdır. Bir **shell** çerçevesi içinde bağımsız lisanslı **modüller** barındırır.

```
Kullanıcı
  └── ContraCORELauncher.exe    (giriş noktası, update kontrolü)
        └── ContraCORE.exe      (saf uygulama, update logic içermez)
              └── Shell         (QMainWindow)
                    ├── Sidebar (collapsible, 3-state per module)
                    └── QStackedWidget
                          ├── xml-fatura widget   (lazy-loaded)
                          └── compare-191 widget  (lazy-loaded)
```

**Temel prensipler:**
- Her modül bağımsız lisans ve trial'a sahip
- Shell, modüllerin kaynak koduna dokunmaz — sadece `adapter.py` eklenir
- Launcher, update mantığını taşır; ContraCORE.exe saf kalır
- Kullanıcı hiçbir zaman `ContraCORE.exe`'yi doğrudan açmaz — her zaman `ContraCORELauncher.exe` üzerinden girer

---

## 2. Proje Klasör Yapısı

```
ContraCore/                         ← proje kökü
├── main.py                         ← uygulama giriş noktası
├── update.json                     ← lokal versiyon metadata (build tarafından üretilir)
│
├── core/                           ← shell çekirdeği
│   ├── shell.py                    ← QMainWindow, pending update okuma, banner
│   ├── sidebar.py                  ← collapsible sidebar, 3-state module items
│   ├── router.py                   ← MODULE_REGISTRY, lazy-load, adapter import
│   ├── version.py                  ← APP_VERSION — TEK KAYNAK
│   ├── update_state.py             ← pending_update.json okuma/silme
│   ├── crash_log.py                ← hata loglama
│   └── license/
│       ├── manager.py              ← public API (dışarıya açık tek dosya)
│       ├── validator.py            ← V2 key üretme + doğrulama
│       ├── storage.py              ← license.json okuma/yazma + HMAC imza
│       ├── trial.py                ← trial takip (3-katman depolama)
│       ├── hwid.py                 ← hardware ID üretme
│       ├── activation_dialog.py    ← son kullanıcı aktivasyon UI
│       ├── _secret.py              ← HMAC secret — yarısı XOR kodlu
│       └── _secret_b.py            ← HMAC secret — ikinci yarı
│
├── modules/                        ← modüller (kaynak, runtime'da external .py olarak kalır)
│   ├── xml-fatura/
│   │   ├── adapter.py              ← Shell–modül köprüsü (zorunlu)
│   │   ├── gui.py                  ← modül ana penceresi
│   │   ├── main.py                 ← standalone çalışma (opsiyonel)
│   │   └── ...                     ← modüle özel dosyalar
│   └── compare-191/
│       ├── adapter.py
│       ├── gui.py
│       ├── karsilastir.py
│       └── ...
│
├── launcher/
│   └── launcher.py                 ← ContraCORELauncher kaynağı
│
├── build_tools/
│   ├── build_launcher.py           ← PyInstaller: ContraCORELauncher.exe
│   ├── build_contracore.py         ← Nuitka: ContraCORE.exe + assets + ZIP
│   ├── build_setup.py              ← Inno Setup: Setup_vX.Y.Z.exe
│   ├── gen_update_json.py          ← update.json otomatik üretimi
│   └── _build_common.py            ← paylaşılan build yardımcıları
│
├── installer/
│   └── ContraCORE.iss              ← Inno Setup scripti
│
├── tools/                          ← geliştirici araçları (ASLA müşteriye gitmez)
│   ├── license_manager.py          ← admin panel (standalone)
│   ├── key_service.py              ← key üretme servisi
│   ├── restore_service.py          ← HWID değişikliği sonrası restore
│   ├── customer_store.py           ← customers.json CRUD
│   └── customers.json              ← müşteri veritabanı
│
├── docs/
│   ├── ARCHITECTURE.md             ← bu dosya
│   ├── UPDATE_TEST_CHECKLIST.md
│   ├── README_SETUP.md
│   └── project_state/
│       ├── STATE_CURRENT.md
│       ├── ROADMAP.md
│       ├── KNOWN_ISSUES.md
│       └── LICENSE_SYSTEM.md
│
├── Icon/                           ← UI ikonları (runtime asset)
├── Logom/                          ← logo assetleri (runtime asset)
│   ├── ico/
│   └── big_logo/
│
└── release/                        ← build çıktıları (git'e commit edilmez)
    ├── ContraCORE/                 ← runtime kurulum klasörü
    ├── ContraCORE_update.zip       ← updater için ZIP paketi
    └── setup/
        └── ContraCORE_Setup_v1.0.0.exe
```

---

## 3. Runtime Release Yapısı

`release/ContraCORE/` müşteriye giden tam kurulum klasörüdür.

```
release/ContraCORE/
├── ContraCORE.exe              ← Nuitka standalone (54 MB)
├── ContraCORELauncher.exe      ← PyInstaller onefile (11 MB)
├── update.json                 ← lokal versiyon bilgisi
│
├── modules/                    ← Python kaynak dosyaları (external, importlib ile yüklenir)
│   ├── xml-fatura/
│   │   ├── adapter.py
│   │   ├── gui.py
│   │   └── ...
│   └── compare-191/
│       ├── adapter.py
│       ├── gui.py
│       └── ...
│
├── Icon/                       ← UI görsel assetleri
├── Logom/                      ← logo assetleri
│
├── PySide6/                    ← Qt runtime (Nuitka tarafından eklendi)
├── *.dll                       ← Windows runtime DLL'leri
└── *.pyd                       ← Python extension modülleri
```

> **Önemli:** `modules/` klasörü Python kaynak dosyaları içerir çünkü Nuitka
> `importlib.util.spec_from_file_location` ile dinamik yüklenen dosyaları
> embed edemez. Bu tasarım gereğidir — modüller external .py olarak kalmalıdır.

---

## 4. Shell / Router / Module İlişkisi

### Başlangıç Akışı

```
main.py
  QApplication()
  Shell()
    ├── ModuleRouter()
    ├── _setup_window()
    ├── _setup_ui()
    │     ├── Sidebar(modules, module_states)
    │     └── update_banner (gizli, pending_update varsa gösterilir)
    ├── _open_default_module()
    │     └── router.load(first_id) → adapter.get_embedded_widget()
    └── pending_update kontrolü (1500ms timer)
  shell.show()
```

### Modül Geçiş Akışı

```
Sidebar → module_selected(id)
  Shell._on_module_selected(id)
    1. _call_lifecycle(current, 'on_module_deactivated')
    2. id not in stack → _load_into_stack(id)
           router.load(id) → adapter.get_embedded_widget()
    3. stacked.setCurrentIndex(idx)
    4. _activate_module_license(id)      # sys.modules['license'] güncelle
    5. _call_lifecycle(id, 'on_module_activated')
```

### ModuleRouter İç Yapısı

```python
MODULE_REGISTRY = [
    {
        'id':           'xml-fatura',      # tekil anahtar
        'label':        'XML Fatura',      # sidebar metni
        'icon_file':    'xml.png',         # Icon/ altındaki dosya
        'adapter_dir':  'xml-fatura',      # modules/ altındaki klasör
        'adapter_mod':  'adapter',         # adapter Python dosyası
        'accent_color': '#F6C244',         # sidebar glow rengi
    },
    ...
]
```

Router, `_import_adapter()` ile `modules/<adapter_dir>/adapter.py`'ı
`importlib.util.spec_from_file_location` üzerinden yükler ve
`sys.modules['cc_adapter_<id>']` anahtarına kaydeder.

---

## 5. modules/ Klasör Contract Yapısı

Her modülün `adapter.py` dosyası şu fonksiyonları **kesinlikle** export etmelidir:

```python
def get_embedded_widget(parent=None) -> tuple[QWidget | None, object | None]:
    """
    Modül widget'ını döner.
    - Lisans/trial geçerliyse: (central_widget, host_window)
    - Aktivasyon iptal edildiyse: (None, None)
    central_widget._cc_host_window = host  # Shell lifecycle hooks için
    """

def get_license_status() -> dict:
    """
    {
        'valid':            bool,
        'trial_active':     bool,
        'expire':           datetime | None,
        'trial_status':     tuple | None,   # (kalan_gun, islenen, kalan_dosya, max_dosya)
        'needs_activation': bool,
    }
    """

def run_activation_dialog(parent=None) -> dict:
    """
    LicenseManagerDialog'u bu modüle odaklı açar.
    Returns: {'activated': bool}
    """

def activate_module_context():
    """
    sys.modules['license'] shim'ini bu modüle yönlendirir.
    sys.modules['gui'] de güncellenebilir.
    """
```

`host_window` (genellikle modülün `MainWindow`'u) şu attribute'lara sahip olmalıdır
(Shell'in `closeEvent` lifecycle'ı için):

| Attribute | Tip | Açıklama |
|---|---|---|
| `stop_flag` veya `_stop_flag` | `threading.Event` | Worker thread durdurma |
| `worker` | `QThread` | Ana işlem thread'i |
| `_duzelt_worker` | `QThread` | compare-191'e özgü |
| `fc_a`, `fc_s`, `fc_c` | obje | xml-fatura FolderCard'ları |
| `_upd_checker` | `QThread` | per-modül updater thread |

---

## 6. sys.modules İzolasyon Sistemi

İki modül aynı Python dosya isimlerini kullanır (`gui.py`, `license.py`, `adapter.py`).
Çakışmayı önlemek için her şey özel anahtarlarla kaydedilir:

| sys.modules anahtarı | İçerik |
|---|---|
| `cc_adapter_xml_fatura` | xml-fatura adapter modülü |
| `cc_adapter_compare_191` | compare-191 adapter modülü |
| `cc_gui_xml_fatura` | xml-fatura gui.py |
| `cc_gui_compare_191` | compare-191 gui.py |
| `license` | Aktif modülün license shim'i (modül geçişinde güncellenir) |

Modül geçişinde `Shell._activate_module_license(module_id)` çağrısı
`sys.modules['license']`'ı yeni modüle yönlendirir.

---

## 7. Lisans Sistemi

### V2 Key Formatı

```
V2-XXXXXXXX-XXXXXXXX-XXXXXXXX-XXXXXXXX
     (32 base32 karakter, 4 grupta)
```

**Binary layout (20 byte):**

```
Offset  Boyut  İçerik
0       1      Version byte: 0x02
1-3     3      Epoch'tan geçen gün sayısı (2020-01-01 base, big-endian 24-bit)
4-11    8      HMAC('_H', hwid)[:8]       — HWID parmak izi
12-15   4      HMAC('_M', module_id)[:4]  — modül bağlama
16-19   4      HMAC('_S', body[:16])[:4]  — bütünlük imzası
```

**Doğrulama adımları:**
1. `V2-` prefix kontrolü
2. 32 karakter uzunluk + base32 alfabe (A-Z2-7)
3. base32 decode → 20 byte
4. Version byte == 0x02
5. İmza: `HMAC('_S', body[:16])[:4]` == `payload[16:20]`
6. Süre: `now <= expire + 1 gün` (grace period)
7. HWID: `HMAC('_H', get_hwid())[:8]` == `body[4:12]`
8. Modül: `HMAC('_M', module_id)[:4]` == `body[12:16]`

### HMAC Secret

İki dosyaya bölünmüş, ilki XOR kodlu:
```python
# _secret.py  → XOR ile kodlanmış birinci yarı
# _secret_b.py → düz ikinci yarı
# Birleşim: _secret.get() = _fa() + _fb()
```

### license.json Yapısı

```
%APPDATA%\ContraCore\license.json
```

```json
{
  "hwid": "XXXX-XXXX-XXXX-XXXX",
  "modules": {
    "xml-fatura": {
      "enabled": true,
      "expire":  "2027-05-25",
      "tier":    "pro",
      "key":     "V2-XXXXXXXX-XXXXXXXX-XXXXXXXX-XXXXXXXX"
    }
  },
  "sig": "ABCD1234ABCD1234"
}
```

`sig`: `HMAC(secret, 'hwid|module_id:enabled:expire:tier:key|...')[:16].upper()`

Yükleme sırasında HWID + imza doğrulanır. Uyuşmazlık → `None` döner (yeniden aktivasyon).

### HWID Üretimi

```
Windows: HKLM\SOFTWARE\Microsoft\Cryptography\MachineGuid
         → strip hyphens → uppercase → first 16 chars
         → SHA256 → XXXX-XXXX-XXXX-XXXX formatı
Fallback 1: wmic cpu get ProcessorId
Fallback 2: platform.node() + platform.processor()
Fallback 3: 'DEFAULT'
```

### Restore Akışı

Müşteri Windows yeniden kurduğunda HWID değişir. Admin panel:
1. Yeni HWID alır
2. Aynı expire date ile yeni V2 key üretir
3. `customers.json`'ı günceller
4. Yeni key'i müşteriye iletir

---

## 8. Trial Sistemi

**Versiyon: v2** — makine bağlı HMAC + 3-katman depolama + saat geri alma koruması

### Konfigürasyon

```python
_TRIAL_CFG = {
    'xml-fatura':  {'days': 30, 'max_files': 5000},  # dosya sayısı
    'compare-191': {'days': 30, 'max_files': 5000},  # muavin SATIR sayısı
}
```

### 3-Katman Depolama

| Katman | Konum | Not |
|---|---|---|
| 1 — Dosya | `%APPDATA%\ContraCore\trial_<module_id>.json` | Birincil |
| 2 — Registry (açık) | `HKCU\Software\ContraCore\Trial\<module_id>` | Standart yol |
| 3 — Registry (gizli) | `HKCU\Software\Classes\CLSID\{makine-türetilmiş-guid}` | GUID SHA256'dan türetilir |

Gizli GUID türetimi:
```python
h    = sha256(f'ccv2_{machine_id[:24]}_{module_safe}'.encode()).hexdigest()
guid = f'{{{h[0:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:32]}}}'
```

Okumada **en kısıtlayıcı değerler** alınır (en erken başlangıç tarihi, en yüksek kullanım sayısı).

### Makine Bağlı HMAC

```python
payload = f'{machine_id[:12]}:{start_date}:{used_files}'
sig     = hmac.new(secret, payload.encode(), sha256).hexdigest()[:20]
```

v2 imzası olmayan veri kesinlikle reddedilir.

### Saat Geri Alma Koruması

Her erişimde `last_seen` (ISO timestamp) `lss` imzasıyla kaydedilir:

```python
payload_ls = f'{machine_id[:12]}:ls:{last_seen_iso}'
lss        = hmac.new(secret, payload_ls.encode(), sha256).hexdigest()[:16]
```

`now < last_seen - 300 saniye` → saat geri alma tespit edildi:
- `used_files = max_files` (kota kalıcı olarak dolu)
- Yeni HMAC imzası yazılır (geri alınamaz)
- `CLOCK_ROLLBACK_DETECTED` crash log'a yazılır

Tolerans: **5 dakika** (NTP drift, timezone değişimi, yeniden başlatmaya karşı güvenli).

---

## 9. AppData ve Registry Yapısı

### Uygulama Yazma Bölgeleri

| Veri | Konum |
|---|---|
| Lisans dosyası | `%APPDATA%\ContraCore\license.json` |
| Trial (katman 1) | `%APPDATA%\ContraCore\trial_<module_id>.json` |
| Pending update | `%APPDATA%\ContraCore\pending_update.json` |
| Launcher log | `%TEMP%\contracore_launcher_log.txt` |
| Update lock | `%TEMP%\contracore_update.lock` |

### Registry Yazma Bölgeleri

| Veri | Konum |
|---|---|
| Trial (katman 2) | `HKCU\Software\ContraCore\Trial\<module_id>` |
| Trial (katman 3) | `HKCU\Software\Classes\CLSID\{makine-türetilmiş-guid}` |

> **CRITICAL:** Updater bu bölgelerin hiçbirine dokunmaz. Güncelleme,
> sadece `ContraCore/` kurulum klasörünü değiştirir.

### Geliştirici Araçları (Müşteriye Gitmeyen)

| Veri | Konum |
|---|---|
| Müşteri veritabanı | `tools/customers.json` |
| Admin log | `tools/logs/license_manager.log` |

---

## 10. Launcher Mimarisi

`ContraCORELauncher.exe` kullanıcının her zaman başlattığı giriş noktasıdır.
Update mantığını taşır ve `ContraCORE.exe`'yi başlatır.

### Ana Akış

```
ContraCORELauncher.exe başlar
  │
  ├── --do-update flag?
  │     Evet → ContraCORE kapanmasını bekle (30s)
  │           → _run_update()
  │           → ContraCORE.exe başlat → çık
  │
  ├── ContraCORE.exe zaten çalışıyor? → çık
  │
  ├── _check_for_update(install_dir)
  │     → _local_version() — update.json'dan oku
  │     → _fetch_remote_meta()
  │           → GitHub raw'dan update.json indir
  │           → GitHub API'den ZIP asset URL'yi al
  │     → versiyon karşılaştır
  │
  ├── Güncelleme yok → ContraCORE.exe başlat → çık
  │
  └── Güncelleme var
        → Tkinter dialog: "Şimdi Güncelle" / "Sonra"
        │
        ├── Şimdi → _run_update() → ContraCORE.exe başlat → çık
        └── Sonra → pending_update.json yaz → ContraCORE.exe başlat → çık
```

### IPC: Launcher ↔ ContraCORE İletişimi

`%APPDATA%\ContraCore\pending_update.json` dosyası üzerinden:

```json
{
  "version":     "1.0.1",
  "notes":       "Yeni özellikler",
  "zip_name":    "ContraCORE_update.zip",
  "zip_sha256":  "9f94a1e2...",
  "zip_url":     "https://github.com/.../ContraCORE_update.zip"
}
```

ContraCORE başlarken bu dosyayı okur → banner gösterir.
"Güncelle" tıklanınca:
```python
subprocess.Popen([launcher, '--do-update'], creationflags=DETACHED_PROCESS)
QApplication.quit()
```

---

## 11. Auto-Update Sistemi

### _run_update() Adımları

```
1. Update lock al (%TEMP%\contracore_update.lock + PID)
2. ZIP URL'yi meta'dan al
3. ZIP'i indir (SSL verify=True, timeout=180s)
4. Doğrulama:
     - Minimum boyut: 30 MB
     - SHA256: update.json'daki zip_sha256 ile karşılaştır
5. Temp klasörüne extract et
6. ContraCORE.exe var mı kontrol et (sağlık kontrolü)
7. Yedek al: _backup/ klasörüne kritik dosyaları kopyala
8. Güvenli uygula (_temp_apply staging):
     a. Tüm yeni içerik install_dir/_temp_apply/'a kopyalanır
     b. ContraCORELauncher.exe ATLANIR (çalışırken kilitli)
     c. Staging başarılıysa: eski klasörler silinir, yeniler move edilir
9. update.json lokal versiyon güncellenir
10. pending_update.json silinir
11. _backup/ silinir (başarılı ise)
12. Lock bırakılır
```

Hata durumunda: rollback → hata dialog → ContraCORE eski sürümle açılır.

### Güvenlik

| Tehdit | Önlem |
|---|---|
| MITM / bozuk ZIP | SHA256 doğrulama + minimum boyut kontrolü |
| SSL strip | verify=True, kapatılamaz |
| İki eş zamanlı updater | PID-tabanlı lock (tasklist kontrolü) |
| Yarım apply | _temp_apply staging — staging bitmeden replace yok |
| Launcher kendini ezme | Launcher adlı dosya apply sırasında skip edilir |
| Offline / timeout | Sessizce bypass, ContraCORE açılır |

---

## 12. GitHub Release Akışı

### Repo Yapısı

```
GitHub repo (GITHUB_REPO = 'owner/repo')
  main branch:
    update.json              ← remote versiyon metadata
  releases/vX.Y.Z assets:
    ContraCORE_update.zip    ← sabit isim, tam kurulum içeriği
```

### update.json Formatı (Remote)

```json
{
  "version":     "1.0.1",
  "mandatory":   false,
  "notes":       "Yeni modül, performans iyileştirmeleri",
  "zip_name":    "ContraCORE_update.zip",
  "zip_sha256":  "9f94a1e2...",
  "min_version": "1.0.0"
}
```

### ZIP URL Bulma (GitHub API)

Launcher hardcoded URL kullanmaz:

```python
GET https://api.github.com/repos/{REPO}/releases/latest
  → assets[].browser_download_url where name == 'ContraCORE_update.zip'
```

Rate limit / timeout → sessizce geç, ContraCORE aç.

---

## 13. Güncelleme Sırasında Korunan Alanlar

Updater bu alanlara **asla dokunmaz:**

| Alan | Açıklama |
|---|---|
| `%APPDATA%\ContraCore\license.json` | Aktif lisans dosyası |
| `%APPDATA%\ContraCore\trial_*.json` | Trial kullanım verisi |
| `HKCU\Software\ContraCore\Trial\*` | Trial registry (katman 2) |
| `HKCU\Software\Classes\CLSID\{...}` | Gizli trial registry (katman 3) |

Güncellenen alanlar:

| Alan | Açıklama |
|---|---|
| `ContraCORE.exe` | Ana uygulama |
| `modules/` | Tüm modül Python dosyaları |
| `Icon/`, `Logom/` | Görsel assetler |
| `update.json` (kurulum) | Lokal versiyon bilgisi |

---

## 14. Rollback Mantığı

### Yedekleme (_backup/)

```python
# Güncelleme öncesi yedeklenir:
items = ['ContraCORE.exe', 'ContraCORELauncher.exe', 'update.json',
         'modules/', 'Icon/', 'Logom/']
```

DLL/PYD dosyaları yedeklenmez (büyük, nadiren değişir).

### Rollback Tetikleyicileri

- ZIP indirme hatası
- SHA256 uyuşmazlığı
- Extract sonrası ContraCORE.exe bulunamadı
- Apply sırasında exception

### Rollback Akışı

```
_rollback(install_dir, backup_dir)
  1. _temp_apply/ varsa sil (yarım staging temizle)
  2. backup_dir içindeki her dosyayı install_dir'e kopyala
  3. Log: "Rollback tamamlandı"
  4. Hata dialog göster
  5. ContraCORE.exe eski sürümle başlatılır
```

Başarılı güncellemede `_backup/` otomatik silinir.

---

## 15. Build Pipeline

### Araçlar

| Araç | Amaç | Kurulum |
|---|---|---|
| **Nuitka** | ContraCORE.exe → Python'u C'ye derler | `pip install nuitka` |
| **PyInstaller** | ContraCORELauncher.exe → onefile | `pip install pyinstaller` |
| **Inno Setup 6** | ContraCORE_Setup_vX.Y.Z.exe | https://jrsoftware.org/isdl.php |
| **ccache** | Nuitka C derleme cache | Nuitka ile otomatik |

### Tek Gerçek Versiyon Kaynağı

```python
# core/version.py
APP_VERSION = '1.0.0'   ← SADECE BURASI DEĞİŞTİRİLİR
```

`update.json` build sırasında bu dosyadan otomatik üretilir. Manuel sync yoktur.

### Build Adımları

```
build_launcher.py
  └── PyInstaller --onefile --noconsole launcher/launcher.py
  └── Çıktı: build_tools/dist/ContraCORELauncher.exe
  └── Doğrulama: exe yoksa sys.exit(1)

build_contracore.py
  ├── [--clean] release/ContraCORE/ + main.dist + main.build temizle
  ├── Nuitka --standalone main.py → main.dist/ContraCORE.exe
  ├── main.dist/ → release/ContraCORE/ (taşı)
  ├── Assetleri kopyala:
  │     Icon/, Logom/, modules/
  │     ContraCORELauncher.exe  ← build_tools/dist/'tan (yoksa HARD ERROR)
  │     update.json             ← proje kökünden
  ├── Release doğrulama (ContraCORE.exe, Launcher, adapter.py'lar)
  └── [--zip]
        ContraCORE_update.zip oluştur (sabit isim)
        gen_update_json.py → SHA256 hesapla → update.json üret
        update.json → proje kökü + release/ContraCORE/'a kopyala
        ZIP sonrası tam doğrulama (update.json dahil)

build_setup.py
  ├── Ön koşul: release/ContraCORE/ + ContraCORELauncher.exe + ContraCORE.exe
  ├── core/version.py'dan APP_VERSION oku
  ├── ISCC.exe /DMyAppVersion=X.Y.Z installer/ContraCORE.iss
  └── Çıktı: release/setup/ContraCORE_Setup_vX.Y.Z.exe
```

---

## 16. Setup / Installer Sistemi

**Teknoloji:** Inno Setup 6, LZMA2 Ultra sıkıştırma

**Script:** `installer/ContraCORE.iss`

### Kurulum Davranışı

| Özellik | Değer |
|---|---|
| Varsayılan dizin | `C:\Program Files\ContraCORE\` |
| UAC | Gerekli (Program Files) |
| Kısayol hedefi | `ContraCORELauncher.exe` (ContraCORE.exe asla değil) |
| Start Menu | `ContraCORE` kısayolu |
| Masaüstü | İsteğe bağlı (kurulum sihirbazında seçilir) |
| Kurulum sonrası | "ContraCORE'u Başlat" checkbox |
| Uninstaller | Add/Remove Programs'a kayıtlı |
| Dil | Türkçe (Turkish.isl) |

### Hariç Tutulanlar (Setup'tan)

```
__pycache__/, *.log, *.tmp, *.pyc, *.pyo, _backup/, _temp_apply/
```

### Versiyon Aktarımı

```
core/version.py (APP_VERSION)
  └── build_setup.py okur
        └── ISCC.exe /DMyAppVersion=1.0.0 ...
              └── ContraCORE.iss → {#MyAppVersion} kullanır
```

---

## 17. Build Komutları

### İlk Kurulum / Tam Build

```powershell
python build_tools/build_launcher.py
python build_tools/build_contracore.py --clean --zip
python build_tools/build_setup.py
```

### Sadece Launcher Güncelle

```powershell
python build_tools/build_launcher.py
python build_tools/build_contracore.py --clean --zip
# (Launcher exe'yi release'e kopyalar, Nuitka ccache'den hızlı geçer)
```

### Sadece Setup Üret (Exe'ler Güncel)

```powershell
python build_tools/build_setup.py
```

### update.json Manuel Üret

```powershell
python build_tools/gen_update_json.py --zip release/ContraCORE_update.zip
```

### GitHub Release Sonrası Adımlar

```
1. update.json → git commit → main branch'e push
2. ContraCORE_update.zip → GitHub release vX.Y.Z assets'e yükle
3. ContraCORE_Setup_vX.Y.Z.exe → müşterilere ilet
```

---

## 18. Yeni Modül Ekleme Standardı

### Zorunlu Adımlar

**1. Modül dizini oluştur:**
```
modules/yeni-modul/
├── adapter.py      ← zorunlu, 4 fonksiyon export etmeli
├── gui.py          ← modül ana penceresi
└── ...             ← modüle özel dosyalar
```

**2. adapter.py'ı yaz:** Bölüm 5'teki contract'ı tam uygula.

**3. MODULE_REGISTRY'e ekle (`core/router.py`):**
```python
{
    'id':           'yeni-modul',
    'label':        'Yeni Modül',
    'icon_file':    'yeni.png',
    'adapter_dir':  'yeni-modul',
    'adapter_mod':  'adapter',
    'accent_color': '#HEX_RENK',
},
```

**4. key_service.py'a ekle (`tools/key_service.py`):**
```python
MODULES = {
    'xml-fatura':  {...},
    'compare-191': {...},
    'yeni-modul':  {'label': 'Yeni Modül', 'default_days': 365},  # YENİ
}
```

**5. Trial konfigürasyonunu ekle (`core/license/trial.py`):**
```python
_TRIAL_CFG = {
    'xml-fatura':  {'days': 30, 'max_files': 5000},
    'compare-191': {'days': 30, 'max_files': 5000},
    'yeni-modul':  {'days': 30, 'max_files': 5000},  # YENİ
}
```

**6. İkon ekle:**
```
Icon/yeni.png   ← sidebar ikonu (32x32 PNG önerilen)
```

**7. build_contracore.py'ı kontrol et:**
`_copy_module_assets()` zaten tüm `modules/` dizinini tarar,
yeni modül için özel bir ekleme **gerekmez**.

### Test Senaryoları (Yeni Modül İçin)

- [ ] Lazy-load: modüle tıklayınca yükleniyor mu?
- [ ] Trial otomatik başlıyor mu (ilk açılışta)?
- [ ] Trial kotası doğru sayılıyor mu?
- [ ] Aktivasyon dialog açılıyor mu (locked state)?
- [ ] Aktivasyon sonrası reload çalışıyor mu?
- [ ] Kapatmada thread'ler temiz kapanıyor mu?
- [ ] sys.modules çakışması yok mu?

---

## Hızlı Referans

### Versiyon Değiştirme

```
core/version.py → APP_VERSION = 'X.Y.Z'
```
Başka hiçbir yerde değiştirilmez.

### Kritik Dosya Konumları

| Dosya | Amaç |
|---|---|
| `core/version.py` | Tek versiyon kaynağı |
| `core/router.py` | Modül kayıt defteri |
| `core/shell.py` | Ana pencere, update banner |
| `core/sidebar.py` | Sidebar, 3-state görünüm |
| `core/license/manager.py` | Lisans public API |
| `core/license/trial.py` | Trial sistemi |
| `launcher/launcher.py` | Launcher + updater mantığı |
| `installer/ContraCORE.iss` | Setup scripti |
| `tools/customers.json` | Müşteri veritabanı (geliştirici) |

### Mimari Değişmezler

1. `ContraCORE.exe` hiçbir update mantığı içermez
2. Kullanıcı kısayolları `ContraCORELauncher.exe`'ye işaret eder
3. `modules/` Python kaynak olarak kalır (importlib zorunluluğu)
4. `tools/` içindeki hiçbir şey müşteriye gitmez
5. Updater `%APPDATA%\ContraCore\` veri dizinlerine dokunmaz
6. Tüm HTTP bağlantıları SSL verify=True, kapatılamaz
7. ZIP adı her zaman `ContraCORE_update.zip` (sabit)
8. Versiyon tek kaynaktan gelir: `core/version.py`
