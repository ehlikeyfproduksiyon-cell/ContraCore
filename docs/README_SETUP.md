# ContraCORE — Setup Installer Kılavuzu

Bu dosya, ContraCORE kurulum dosyası (`ContraCORE_Setup_vX.Y.Z.exe`) nasıl üretilir,
Inno Setup nasıl kurulur ve build akışı nasıl çalışır detaylı anlatır.

---

## Ön Koşullar

### 1. Inno Setup 6 Kurulumu

**İndirme:** https://jrsoftware.org/isdl.php

- **"Inno Setup 6"** → `innosetup-6.x.x.exe` indir ve kur
- Varsayılan kurulum yolu: `C:\Program Files (x86)\Inno Setup 6\`
- Kurulum sırasında **"Install Inno Setup Preprocessor (ISPP)"** seçeneğini işaretle

Kurulum tamamlandığında `ISCC.exe` şu konumda olmalıdır:
```
C:\Program Files (x86)\Inno Setup 6\ISCC.exe
```

`build_setup.py` bu yolu otomatik bulur. Farklı bir konuma kurulduysa `--iscc` parametresi kullan.

---

### 2. Türkçe Dil Dosyası Kontrolü

Inno Setup 6, Türkçe dil desteğini varsayılan kurulumda içerir.
Kontrol: `C:\Program Files (x86)\Inno Setup 6\Languages\Turkish.isl`

Bu dosya yoksa:
- Inno Setup kurulum klasöründeki `Languages/` altına `Turkish.isl` ekle
- Veya `.iss` dosyasındaki `[Languages]` bölümünü kaldır (İngilizce olarak devam eder)

---

## Dosya Yapısı

```
ContraCore/
├── installer/
│   └── ContraCORE.iss        ← Inno Setup scripti
├── build_tools/
│   ├── build_setup.py        ← Setup build otomasyonu
│   ├── build_contracore.py   ← Ana uygulama build
│   └── build_launcher.py     ← Launcher build
├── core/
│   └── version.py            ← APP_VERSION — tek gerçek kaynak
└── release/
    ├── ContraCORE/           ← build_contracore.py çıktısı (kaynak)
    └── setup/
        └── ContraCORE_Setup_v1.0.0.exe  ← setup çıktısı
```

---

## Build Akışı

### İlk Kurulum (sıfırdan build)

```powershell
# 1. Launcher'ı derle
python build_tools/build_launcher.py

# 2. Ana uygulamayı derle (Launcher ve update.json dahil)
python build_tools/build_contracore.py --clean

# 3. Setup dosyasını üret
python build_tools/build_setup.py
```

Çıktı:
```
release/setup/ContraCORE_Setup_v1.0.0.exe
```

---

### Yeni Sürüm Build Akışı (1.0.0 → 1.0.1)

```powershell
# 1. Versiyon güncelle (tek yer)
# core/version.py → APP_VERSION = '1.0.1'

# 2. Launcher yeniden derle (versiyon etiketi güncellendi mi diye)
python build_tools/build_launcher.py

# 3. Ana uygulamayı derle + update ZIP + update.json üret
python build_tools/build_contracore.py --clean --zip

# 4. Setup üret
python build_tools/build_setup.py

# 5. GitHub release
#    - update.json → main branch'e push et
#    - ContraCORE_update.zip → GitHub release'e yükle
#    - ContraCORE_Setup_v1.0.1.exe → müşterilere gönder / GitHub release'e yükle
```

---

### Sadece Setup Build (kaynak değişmedi)

Release klasörü zaten güncel ise (ContraCORE build edildi, Launcher var):

```powershell
python build_tools/build_setup.py
```

---

## Parametreler

```
python build_tools/build_setup.py [--iscc PATH]

  --iscc PATH    ISCC.exe tam yolu (otomatik bulunamazsa belirt)
```

Örnek:
```powershell
python build_tools/build_setup.py --iscc "D:\Tools\InnoSetup6\ISCC.exe"
```

---

## Kurulum Davranışı (Son Kullanıcı)

| Özellik | Değer |
|---|---|
| Varsayılan kurulum dizini | `C:\Program Files\ContraCORE\` |
| UAC | Gerekli (Program Files altına yazar) |
| Başlat Menüsü kısayolu | ✅ ContraCORE → ContraCORELauncher.exe |
| Masaüstü kısayolu | İsteğe bağlı (kurulum sihirbazında seçilir) |
| Kurulum sonrası başlat | Checkbox — "ContraCORE'u Başlat" |
| Kaldırma | Add/Remove Programs + Başlat Menüsü'nde "Kaldır" |
| Sıkıştırma | LZMA2 Ultra (en küçük boyut) |

**ÖNEMLİ:** Kısayollar `ContraCORE.exe`'ye değil, `ContraCORELauncher.exe`'ye işaret eder.
Launcher güncelleme kontrolü yapar ve `ContraCORE.exe`'yi başlatır.

---

## Sorun Giderme

### ISCC.exe bulunamadı
```
[HATA] Inno Setup Compiler (ISCC.exe) bulunamadı.
```
→ Inno Setup 6 kurul veya `--iscc` parametresi ile tam yolu belirt.

### Türkçe dil dosyası bulunamadı
```
Error: Can't open file: Turkish.isl
```
→ Inno Setup'ı yeniden kur ve dil seçeneklerini işaretle.
→ Veya `installer/ContraCORE.iss` içindeki `[Languages]` bölümünü kaldır.

### ContraCORELauncher.exe yok
```
✗ ContraCORELauncher.exe yok — önce build_launcher.py çalıştır
```
→ `python build_tools/build_launcher.py` çalıştır.
→ PyInstaller kurulu olmalı: `pip install pyinstaller`

### release/ContraCORE/ yok
```
✗ release/ContraCORE/ bulunamadı
```
→ `python build_tools/build_contracore.py --clean` çalıştır.
→ Nuitka kurulu olmalı: `pip install nuitka`

---

## .iss Script Konumu

```
installer/ContraCORE.iss
```

Inno Setup IDE'si ile açılabilir (ISCC.exe yanındaki `Compil32.exe`).
Scripti düzenleyerek kurulum davranışı özelleştirilebilir.

`MyAppVersion` define'ı build_setup.py tarafından otomatik geçirilir:
```
ISCC /DMyAppVersion=1.0.0 installer\ContraCORE.iss
```

Manuel test için aynı komutu çalıştırabilirsin.
