# ContraCore — Production Architecture

**Version:** 1.0.4
**Last updated:** 2026-05-26
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
19. [Bilinen Hatalar ve Çözümleri](#19-bilinen-hatalar-ve-çözümleri)

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
│   ├── update_state.py             ← pending/last_update okuma/silme
│   ├── crash_log.py                ← hata loglama
│   └── license/
│       ├── manager.py              ← public API (dışarıya açık tek dosya)
│       ├── validator.py            ← V2 key üretme + doğrulama
│       ├── storage.py              ← license.json okuma/yazma + HMAC imza
│       ├── trial.py                ← trial takip (3-katman depolama)
│       ├── hwid.py                 ← hardware ID üretme
│       ├── activation_dialog.py    ← son kullanıcı aktivasyon UI
│       ├── _secret.py              ← HMAC secret — yarısı XOR kodlu (GitHub'a asla!)
│       └── _secret_b.py            ← HMAC secret — ikinci yarı (GitHub'a asla!)
│
├── modules/                        ← modüller (kaynak, runtime'da external .py olarak kalır)
│   ├── xml-fatura/
│   │   ├── adapter.py              ← Shell–modül köprüsü (zorunlu)
│   │   ├── gui.py                  ← modül ana penceresi
│   │   └── ...
│   └── compare-191/
│       ├── adapter.py
│       ├── gui.py
│       └── ...
│
├── launcher/
│   └── launcher.py                 ← ContraCORELauncher kaynağı
│
├── build_tools/
│   ├── build_launcher.py           ← PyInstaller: ContraCORELauncher.exe
│   ├── build_contracore.py         ← Nuitka: ContraCORE.exe + assets + ZIP
│   ├── build_setup.py              ← Inno Setup: Setup_vX.Y.Z.exe
│   ├── gen_update_json.py          ← update.json SHA256 otomatik üretimi
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
├── docs/                           ← dokümantasyon
│   ├── ARCHITECTURE.md             ← bu dosya
│   ├── UPDATE_TEST_CHECKLIST.md
│   ├── README_SETUP.md
│   └── project_state/
│
├── build.bat                       ← tek komut: launcher + ContraCORE + ZIP + setup
├── Icon/                           ← UI ikonları (runtime asset)
├── Logom/                          ← logo assetleri (runtime asset)
│
└── release/                        ← build çıktıları (git'e commit edilmez)
    ├── ContraCORE/                 ← runtime kurulum klasörü
    ├── ContraCORE_update.zip       ← updater için ZIP paketi
    └── setup/
        └── ContraCORE_Setup_vX.Y.Z.exe
```

---

## 3. Runtime Release Yapısı

`release/ContraCORE/` müşteriye giden tam kurulum klasörüdür.

```
release/ContraCORE/
├── ContraCORE.exe              ← Nuitka standalone (~80 MB)
├── ContraCORELauncher.exe      ← PyInstaller onefile (~11 MB)
├── update.json                 ← lokal versiyon bilgisi
│
├── modules/                    ← Python kaynak dosyaları (external, importlib ile yüklenir)
│   ├── xml-fatura/
│   └── compare-191/
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
    │     └── sidebar.update_clicked → shell._on_update_clicked
    ├── _open_default_module()
    │     └── router.load(first_id) → adapter.get_embedded_widget()
    ├── pending_update kontrolü (1500ms timer)
    └── last_update kontrolü (2000ms timer → "Yenilikler" dialog)
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
    4. _activate_module_license(id)
    5. _call_lifecycle(id, 'on_module_activated')
```

### Pending Update Kontrolü (Shell.__init__)

```python
from core.update_state import read_pending, clear_pending, read_last_update, clear_last_update
from core.version import APP_VERSION

self._pending_update = read_pending()
if self._pending_update:
    def _ver(s):
        try: return tuple(int(x) for x in str(s).split('.'))
        except: return (0,)
    if _ver(self._pending_update.get('version', '0')) <= _ver(APP_VERSION):
        clear_pending()   # stale pending temizle
        self._pending_update = None
    else:
        QTimer.singleShot(1500, self._show_update_banner)

last = read_last_update()
if last:
    QTimer.singleShot(2000, lambda: self._show_whats_new(last))
    clear_last_update()
```

### Güncelle Butonu Akışı (Shell)

```python
def _on_update_clicked(self):
    launcher = os.path.join(os.path.dirname(sys.executable), 'ContraCORELauncher.exe')
    if not os.path.exists(launcher):
        QMessageBox.warning(self, 'Hata', 'ContraCORELauncher.exe bulunamadı.')
        return
    _sp.Popen([launcher, '--do-update', '--pid', str(os.getpid())],
              creationflags=_sp.DETACHED_PROCESS,
              cwd=os.path.dirname(launcher))
    QApplication.quit()
```

---

## 5. modules/ Klasör Contract Yapısı

Her modülün `adapter.py` dosyası şu fonksiyonları **kesinlikle** export etmelidir:

```python
def get_embedded_widget(parent=None) -> tuple[QWidget | None, object | None]:
def get_license_status() -> dict:
def run_activation_dialog(parent=None) -> dict:
def activate_module_context():
```

---

## 6. sys.modules İzolasyon Sistemi

| sys.modules anahtarı | İçerik |
|---|---|
| `cc_adapter_xml_fatura` | xml-fatura adapter modülü |
| `cc_adapter_compare_191` | compare-191 adapter modülü |
| `license` | Aktif modülün license shim'i (modül geçişinde güncellenir) |

---

## 7. Lisans Sistemi

### V2 Key Formatı

```
V2-XXXXXXXX-XXXXXXXX-XXXXXXXX-XXXXXXXX
```

**Binary layout (20 byte):**

| Offset | Boyut | İçerik |
|---|---|---|
| 0 | 1 | Version byte: 0x02 |
| 1-3 | 3 | Epoch'tan geçen gün (2020-01-01 base, big-endian 24-bit) |
| 4-11 | 8 | HMAC('_H', hwid)[:8] — HWID parmak izi |
| 12-15 | 4 | HMAC('_M', module_id)[:4] — modül bağlama |
| 16-19 | 4 | HMAC('_S', body[:16])[:4] — bütünlük imzası |

### HMAC Secret

```python
# _secret.py  → XOR ile kodlanmış birinci yarı  (GitHub'a ASLA)
# _secret_b.py → düz ikinci yarı                (GitHub'a ASLA)
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
      "key":     "V2-..."
    }
  },
  "sig": "ABCD1234ABCD1234"
}
```

---

## 8. Trial Sistemi

**Versiyon: v2** — makine bağlı HMAC + 3-katman depolama + saat geri alma koruması

### Konfigürasyon

```python
_TRIAL_CFG = {
    'xml-fatura':  {'days': 30, 'max_files': 5000},
    'compare-191': {'days': 30, 'max_files': 5000},
}
```

### 3-Katman Depolama

| Katman | Konum |
|---|---|
| 1 — Dosya | `%APPDATA%\ContraCore\trial_<module_id>.json` |
| 2 — Registry (açık) | `HKCU\Software\ContraCore\Trial\<module_id>` |
| 3 — Registry (gizli) | `HKCU\Software\Classes\CLSID\{makine-türetilmiş-guid}` |

Okumada **en kısıtlayıcı değerler** alınır.

### Saat Geri Alma Koruması

`now < last_seen - 300 saniye` → `used_files = max_files` → trial kalıcı biter.

---

## 9. AppData ve Registry Yapısı

| Veri | Konum |
|---|---|
| Lisans dosyası | `%APPDATA%\ContraCore\license.json` |
| Trial (katman 1) | `%APPDATA%\ContraCore\trial_<module_id>.json` |
| Pending update | `%APPDATA%\ContraCore\pending_update.json` |
| Last update | `%APPDATA%\ContraCore\last_update.json` |
| Launcher log | `%TEMP%\contracore_launcher_log.txt` |
| Update lock | `%TEMP%\contracore_update.lock` |

> **CRITICAL:** Updater bu alanlara asla dokunmaz.

---

## 10. Launcher Mimarisi

`ContraCORELauncher.exe` — PyInstaller onefile — kullanıcının her zaman başlattığı giriş noktası.

### Ana Akış

```
ContraCORELauncher.exe başlar
  │
  ├── --do-update --pid <PID>?
  │     → WaitForSingleObject(PID, 30s) — ContraCORE kapanmasını bekle
  │     → _run_update()
  │     → ShellExecuteW ile ContraCORE.exe başlat → çık
  │
  ├── ContraCORE.exe zaten çalışıyor? → çık
  │
  ├── _check_for_update(install_dir)
  │     → raw GitHub'dan update.json indir
  │     → GitHub API'den ZIP URL al
  │     → versiyon karşılaştır
  │
  ├── Güncelleme yok → ShellExecuteW ile ContraCORE.exe başlat → çık
  │
  └── Güncelleme var → Tkinter dialog
        ├── "Şimdi Güncelle" → _run_update() → ContraCORE.exe → çık
        └── "Sonra" → pending_update.json yaz → ContraCORE.exe → çık
```

### Kritik Teknik Kararlar

**ShellExecuteW** (subprocess.Popen değil):
```python
ctypes.windll.shell32.ShellExecuteW(None, 'open', exe, None, install_dir, 1)
```
- PyInstaller onefile `%TEMP%\_MEI*` konumundan çalışır
- Defender bu konumdan `CreateProcess` (subprocess.Popen) çağrısını WinError 225 ile bloke eder
- `ShellExecuteW` Windows Shell API'sinden geçer, bu kısıtlamaya takılmaz

**WaitForSingleObject** (tasklist polling değil):
```python
handle = ctypes.windll.kernel32.OpenProcess(SYNCHRONIZE, False, pid)
result = ctypes.windll.kernel32.WaitForSingleObject(handle, timeout_ms)
```
- Tasklist polling güvenilmez (process zaten kapanmış olabilir)
- WaitForSingleObject OS kernel'den sinyal alır — anında ve kesin

**rename-first `_replace_file`** (delete+copy değil):
```python
os.rename(dst, dst + '.ccold')   # kilitli DLL'lere izin verilir
shutil.copy2(src, dst)
os.remove(dst + '.ccold')        # temizle
```
- `os.remove()` yüklü DLL/exe'lerde WinError 5 verir
- `os.rename()` yüklü dosyalara Windows'ta izin verilir

**İndirme progress bar** (Tkinter + thread-safe queue):
- Navy arka plan, `#0970fc` mavi progress bar
- Ana thread: Tkinter mainloop
- İndirme thread: queue ile UI günceller
- Non-closeable pencere

---

## 11. Auto-Update Sistemi

### _run_update() Adımları

```
1. Lock al (%TEMP%\contracore_update.lock + PID)
2. ZIP URL'yi meta veya pending_update.json'dan al
3. ZIP'i indir (progress bar, SSL=True, timeout=180s)
4. Doğrulama: min 30 MB + SHA256 eşleşmesi
5. Temp klasörüne extract et
6. ContraCORE.exe var mı? (sağlık kontrolü)
7. Yedek al → install_dir/_backup/
8. Güvenli uygula:
   a. install_dir/_temp_apply/ klasörüne staging
   b. ContraCORELauncher.exe atlanır (çalışırken değiştirilemez)
   c. Staging tamamsa: _replace_file ile rename-first replace
9. update.json lokal versiyon güncelle
10. pending_update.json sil
11. last_update.json yaz (ContraCORE açılışta "Yenilikler" gösterir)
12. _backup/ sil (başarılıysa)
13. Lock bırak
Hata → rollback → hata dialog → ContraCORE eski sürümle açılır
```

---

## 12. GitHub Release Akışı

```
GitHub repo: ehlikeyfproduksiyon-cell/ContraCore
  main branch:
    update.json              ← launcher buradan okur
  releases/vX.Y.Z assets:
    ContraCORE_update.zip    ← sabit isim, ZIP URL GitHub API'den dinamik alınır
```

**update.json:**
```json
{
  "version": "1.0.4",
  "mandatory": false,
  "notes": "...",
  "zip_name": "ContraCORE_update.zip",
  "zip_sha256": "<64 char hex>",
  "min_version": "1.0.0"
}
```

---

## 13. Güncelleme Sırasında Korunan Alanlar

Updater **asla dokunmaz:**

| Alan |
|---|
| `%APPDATA%\ContraCore\license.json` |
| `%APPDATA%\ContraCore\trial_*.json` |
| `HKCU\Software\ContraCore\Trial\*` |
| `HKCU\Software\Classes\CLSID\{...}` |

---

## 14. Rollback Mantığı

Yedeklenen dosyalar: `ContraCORE.exe`, `ContraCORELauncher.exe`, `update.json`, `modules/`, `Icon/`, `Logom/`

Rollback tetikleyicileri: indirme hatası, SHA256 uyuşmazlığı, extract sonrası exe eksik, apply exception.

Başarılı güncellemede `_backup/` otomatik silinir.

---

## 15. Build Pipeline

### Araçlar

| Araç | Amaç |
|---|---|
| **Nuitka** | ContraCORE.exe — Python'u C'ye derler |
| **PyInstaller** | ContraCORELauncher.exe — onefile |
| **Inno Setup 6** | ContraCORE_Setup_vX.Y.Z.exe |

### Tek Gerçek Versiyon Kaynağı

```python
# core/version.py
APP_VERSION = '1.0.4'   ← SADECE BURASI DEĞİŞTİRİLİR
```

### Build Adımları (build.bat)

```
1. ContraCORELauncher yoksa → build_launcher.py
2. build_contracore.py --clean --zip
   → Nuitka --standalone main.py
   → release/ContraCORE/ oluştur
   → ContraCORE_update.zip oluştur
   → gen_update_json.py → SHA256 → update.json
3. build_setup.py
   → Inno Setup → ContraCORE_Setup_vX.Y.Z.exe
```

> **UYARI:** `--clean` olmadan build alma. Nuitka cache eski kodu kullanabilir,
> kritik hatalara yol açar (geçmişte: `read_last_update` eksikliği gözden kaçtı).

---

## 16. Setup / Installer Sistemi

**Script:** `installer/ContraCORE.iss`

| Özellik | Değer |
|---|---|
| Kurulum dizini | `{localappdata}\ContraCORE` (admin gerektirmez) |
| Registry | HKCU |
| Kısayol hedefi | `ContraCORELauncher.exe` |
| Masaüstü kısayolu | `checkedonce` (ilk kurulumda seçili gelir) |

---

## 17. Build Komutları

```powershell
# Tam build (önerilen)
build.bat

# Sadece launcher güncelle
python build_tools/build_launcher.py
python build_tools/build_contracore.py --clean --zip

# Sadece setup üret
python build_tools/build_setup.py

# SHA256 manuel üret
python build_tools/gen_update_json.py --zip release/ContraCORE_update.zip
```

### Her Versiyon Release Sonrası

```
1. core/version.py → APP_VERSION güncelle
2. update.json → version güncelle
3. git push
4. build.bat çalıştır
5. git add update.json && git push (gerçek SHA256)
6. GitHub: vX.Y.Z Release oluştur
7. ContraCORE_update.zip yükle
8. ContraCORE_Setup_vX.Y.Z.exe müşterilere ilet
```

---

## 18. Yeni Modül Ekleme Standardı

```
modules/yeni-modul/
├── adapter.py      ← 4 fonksiyon: get_embedded_widget, get_license_status,
│                                   run_activation_dialog, activate_module_context
├── gui.py
└── ...
```

1. `core/router.py` → `MODULE_REGISTRY`'e ekle
2. `tools/key_service.py` → `MODULES`'a ekle
3. `core/license/trial.py` → `_TRIAL_CFG`'ya ekle
4. `Icon/yeni.png` ekle

---

## 19. Bilinen Hatalar ve Çözümleri

| Hata | Sebep | Çözüm |
|---|---|---|
| WinError 32 (build sırasında) | `main.build/` Python process tarafından kilitli | `Get-Process python* \| Stop-Process -Force` |
| WinError 5 (güncelleme sırasında) | Yüklü DLL/exe `os.remove()` ile silinemez | `rename-first _replace_file()` — production'da çözüldü |
| WinError 225 (Defender block) | PyInstaller temp klasöründen `CreateProcess` Defender tarafından bloke | `ShellExecuteW` kullan — production'da çözüldü |
| `ImportError: read_last_update` | `update_state.py`'de fonksiyon eksikti | Eklendi: `read_last_update()`, `clear_last_update()` — `--clean` build şart |
| SHA256 uyuşmazlığı | GitHub Release'e yanlış ZIP yüklendi | Her zaman `release/ContraCORE_update.zip` yükle |
| Stale pending_update.json | Eski pending versiyon ≤ mevcut versiyon | Shell.py başlangıçta kontrol eder, temizler |
| Güncelleme sonrası program açılmıyor | Eski ZIP'teki ContraCORE.exe'de eksik fonksiyon derlenmiş | `--clean` ile yeniden build al |
| Nuitka cache sorunu | `--clean` kullanılmadan build alındı | Her zaman `build.bat` veya `--clean` flag kullan |

---

## Mimari Değişmezler

1. `ContraCORE.exe` hiçbir update mantığı içermez
2. Kullanıcı kısayolları `ContraCORELauncher.exe`'ye işaret eder
3. `modules/` Python kaynak olarak kalır (importlib zorunluluğu)
4. `tools/` içindeki hiçbir şey müşteriye gitmez
5. Updater `%APPDATA%\ContraCore\` veri dizinlerine dokunmaz
6. Tüm HTTP bağlantıları SSL verify=True, kapatılamaz
7. ZIP adı her zaman `ContraCORE_update.zip` (sabit)
8. Versiyon tek kaynaktan gelir: `core/version.py`
9. `ContraCORE.exe` başlatılması için her zaman `ShellExecuteW` kullan (subprocess.Popen WinError 225 verir)
10. Build öncesi her zaman `--clean` kullan
