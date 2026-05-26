# ContraCore — Distribution & Install Validation

**Son güncelleme:** 2026-05-25

---

## 1. Sıfır Ortam Test Checklist

Başka bir bilgisayarda (temiz Windows, hiç Python yok) aşağıdaki adımları sırayla doğrula.

### 1.1 Sistem Gereksinimleri

| Kontrol | Beklenen | Kontrol Yöntemi |
|---------|----------|-----------------|
| Windows 10/11 x64 | ✓ | winver |
| VC++ Redistributable 2015-2022 x64 | Gerekli | `VCRUNTIME140.dll`, `MSVCP140.dll` System32'de var mı? |
| .NET framework | Gerekmez | — |
| Python yüklü olması | Gerekmez | Standalone exe |

> **Not:** Nuitka standalone exe, Python runtime'ı kendi içine gömer. Müşteri makinesinde Python yüklü olmak zorunda değil. Ancak `VCRUNTIME140.dll` eksikse PySide6 başlamaz.

**VC++ test komutu (cmd'de):**
```
where VCRUNTIME140.dll
```
Bulunamazsa: https://aka.ms/vs/17/release/vc_redist.x64.exe indir ve kur.

---

### 1.2 DLL Eksik Testi

Exe çalıştırıldıktan sonra hata olursa:

1. `%APPDATA%\ContraCore\crash_log.txt` dosyasına bak
2. Windows Event Viewer → Application Errors → ContraCORE.exe
3. `Dependencies.exe` (ücretsiz tool) ile `ContraCORE.exe` üzerinde DLL bağımlılık taraması yap

**Beklenen kritik DLL'ler:**
- `Qt6Core.dll`, `Qt6Widgets.dll`, `Qt6Gui.dll` — release klasöründe mevcut
- `VCRUNTIME140.dll`, `MSVCP140.dll` — sistem
- `python3XX.dll` — release klasöründe mevcut (Nuitka gömer)

---

### 1.3 Font / Path Problemi

| Kontrol | Nasıl test edilir |
|---------|-------------------|
| Segoe UI fontu | Windows 10/11'de varsayılan, eksik olamaz |
| Türkçe karakter (ğ, ü, ş, ı) | Uygulama başlığı, buton metinleri gözlem |
| Dosya yolu boşluk içeriyor mu | `C:\Users\Ad Soyad\...` — boşluklu path test et |
| UNC path (`\\sunucu\klasor`) | Desteklenmez, belgelenmeli |

**Config dizini:** `%APPDATA%\ContraCore\`  
Bu dizin ilk çalışmada otomatik oluşturulur (`os.makedirs(..., exist_ok=True)` ile).

---

### 1.4 AppData Oluşturma Testi

```
Adımlar:
1. %APPDATA%\ContraCore\ klasörünü sil (varsa)
2. ContraCORE.exe çalıştır
3. Kontrol et:
   %APPDATA%\ContraCore\             ← klasör oluştu mu?
   %APPDATA%\ContraCore\crash_log.txt ← "APP START" kaydı var mı?
```

Crash log içeriği ilk çalışmada şöyle görünmeli:
```
────────────────────────────────────────────────────────────
[2026-05-25 10:30:00] APP START
────────────────────────────────────────────────────────────
Python   : 3.12.x ...
Platform : Windows-11-...
Exe      : C:\...\ContraCORE.exe
CWD      : C:\...\ContraCORE
```

---

### 1.5 License / Trial Storage Testi

**Senaryo A — İlk Açılış (lisans yok, trial başlamamış):**
```
Beklenen:
- Modüle tıklandığında trial otomatik başlar
- Sidebar: "DENEME" badge gösterir
- %APPDATA%\ContraCore\trial_xml_fatura.json oluşur
- %APPDATA%\ContraCore\trial_compare_191.json oluşur
- Registry: HKCU\SOFTWARE\ContraCore\Trials\xml-fatura kaydı oluşur
```

**Senaryo B — Trial aktif:**
```
Beklenen:
- Uygulama kapanıp açılırsa trial durumu korunur
- Kalan gün doğru hesaplanır (30 - geçen gün)
- Sidebar tooltip: "Deneme sürümü aktif — X gün kaldı"
```

**Senaryo C — Lisans aktivasyonu:**
```
Beklenen:
- %APPDATA%\ContraCore\license.json oluşur
- HWID eşleşmesi: başka bilgisayara kopyalanmış license.json çalışmaz
- Sidebar: yeşil badge, tooltip "Lisanslı — GG.AA.YYYY'e kadar"
```

---

### 1.6 Standalone Runtime Bağımlılık Testi

Nuitka build sonrası `release/ContraCORE/` klasöründe şunları doğrula:

```
ContraCORE.exe              ← var mı?
python312.dll (veya benzer) ← Nuitka koyar
Qt6Core.dll                 ← Nuitka / PySide6 plugin koyar
modules/
  xml-fatura/
    gui.py                  ← var mı?
    main.py                 ← var mı?
    adapter.py              ← var mı?
  compare-191/
    gui.py                  ← var mı?
    karsilastir.py          ← var mı?
    adapter.py              ← var mı?
Icon/                       ← var mı?
Logom/                      ← var mı?
```

**Hızlı doğrulama komutu (PowerShell):**
```powershell
$base = "release\ContraCORE"
@(
  "ContraCORE.exe",
  "modules\xml-fatura\gui.py",
  "modules\xml-fatura\main.py",
  "modules\xml-fatura\adapter.py",
  "modules\compare-191\gui.py",
  "modules\compare-191\karsilastir.py",
  "modules\compare-191\adapter.py"
) | ForEach-Object {
  $p = Join-Path $base $_
  if (Test-Path $p) { Write-Host "[OK] $_" }
  else              { Write-Host "[EKSIK] $_" -ForegroundColor Red }
}
```

---

## 2. Minimum Dosya Yapısı (Müşteriye Gidecek)

```
ContraCORE/
├── ContraCORE.exe              ← ana çalıştırılabilir
├── python312.dll               ← Python runtime (Nuitka)
├── Qt6*.dll (20+ dosya)        ← Qt runtime (Nuitka/PySide6)
├── PySide6/                    ← Qt plugin'leri
├── Icon/                       ← UI icon'ları
├── Logom/                      ← logo asset'leri
└── modules/
    ├── xml-fatura/
    │   ├── adapter.py
    │   ├── gui.py
    │   ├── main.py
    │   ├── updater.py
    │   └── Icon/               ← modül icon'ları
    └── compare-191/
        ├── adapter.py
        ├── gui.py
        └── karsilastir.py
```

**Müşteriye KESİNLİKLE gitmeyen dosyalar:**
- `tools/` klasörü (license_manager, keygen)
- `build_tools/` klasörü
- `core/license/_secret.py`, `_secret_b.py`
- `keygen.py`, `activation.py`, `license.py` (modül klasörlerindeki eski standalone dosyalar)
- `*.pyc`, `*.spec`, `*.bat`
- `Referans/`, `ÇALIŞAN/` alt klasörleri
- `docs/`, `dev_tools/`

> `create_release_zip.py` bu hariç tutmaları otomatik uygular.

---

## 3. Runtime Log Sistemi

**Konum:** `%APPDATA%\ContraCore\crash_log.txt`

**Ne zaman yazılır:**
- Uygulama her açıldığında: `APP START` kaydı (Python sürümü, platform, exe path)
- `sys.excepthook` üzerinden yakalanmamış her exception: tam traceback

**Log boyut yönetimi:**
- Max 500 KB tutulur
- Aşılırsa ilk yarı kırpılır, son yarı korunur

**Müşteri debug akışı:**
```
1. Müşteri hatayı bildiriyor
2. Müşteriden %APPDATA%\ContraCore\crash_log.txt iste
3. En son "UNHANDLED EXCEPTION" bloğuna bak
4. Traceback → hangi modül, hangi satır → fix
```

**Kapsam dışı (intentional):**
- Modül içi işlemsel hatalar (dosya işleme başarısızlıkları) bu log'a yazmaz
- Her modülün kendi hata UI'ı var (QMessageBox)
- Sadece `sys.excepthook` yakaladığı (uygulama crash'i) burada loglanır

---

## 4. ZIP Oluşturma

### Tek komut:
```powershell
python tools/create_release_zip.py --version 1.0.0
# Çıktı: release/ContraCORE_v1.0.0.zip
```

### Build + ZIP birlikte:
```powershell
python build_tools/build_contracore.py --zip --version 1.0.0
```

### Otomatik tarihli versiyon:
```powershell
python tools/create_release_zip.py
# Çıktı: release/ContraCORE_v2026.05.25.zip
```

---

## 5. İlk Müşteri Dağıtımı Akışı

```
1. Build al
   python build_tools/build_contracore.py --clean

2. Manuel test (bu checklist — en az 1.2, 1.4, 1.5)

3. ZIP oluştur
   python tools/create_release_zip.py --version 1.0.0

4. ZIP içeriğini kontrol et
   - extract edip ContraCORE.exe çalıştır
   - crash_log.txt → APP START kaydı var mı?

5. Müşteriye gönder
   - Sadece ContraCORE_v1.0.0.zip
   - License Manager, keygen, tools/ — asla gönderilmez

6. Aktivasyon
   - tools/license_manager.py (kendi makinende) ile müşteri kaydı oluştur
   - Lisans anahtarını müşteriye ilet
   - Müşteri uygulama içinden aktive eder
```
