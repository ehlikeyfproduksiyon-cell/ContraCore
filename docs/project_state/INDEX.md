# ContraCore — Project State Documentation Index

**Last updated:** 2026-05-25

Yeni bir sohbet açıldığında bu dosyadan başla. Her bölüm için doğru dosyayı oku.

---

## Dosyalar

| Dosya | Soru |
|---|---|
| [STATE_CURRENT.md](STATE_CURRENT.md) | Sistem şu an nasıl çalışıyor? Mimari nedir? |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Shell, router, sidebar, adapter, signal flow detayları |
| [LICENSE_SYSTEM.md](LICENSE_SYSTEM.md) | V2 key formatı, HWID, storage, trial, restore |
| [ADMIN_PANEL.md](ADMIN_PANEL.md) | License Manager aracı, customer schema, tüm paneller |
| [BUILD_PIPELINE.md](BUILD_PIPELINE.md) | Nuitka build, release yapısı, icon, asset yönetimi |
| [KNOWN_ISSUES.md](KNOWN_ISSUES.md) | Mevcut buglar, edge case riskler |
| [ROADMAP.md](ROADMAP.md) | Gelecek planları, öncelik sırası |
| [DO_NOT_REINTRODUCE.md](DO_NOT_REINTRODUCE.md) | Kaldırılan sistemler — geri getirilmemeli |
| [DISTRIBUTION.md](DISTRIBUTION.md) | Sıfır ortam test checklist, ZIP oluşturma, müşteri dağıtım akışı |

---

## Hızlı Referans

**Yeni modül eklenecek:**
→ [ARCHITECTURE.md — Module Adapter Interface](ARCHITECTURE.md)
→ [ROADMAP.md — New Module Onboarding Checklist](ROADMAP.md)

**Lisans sorunu:**
→ [LICENSE_SYSTEM.md](LICENSE_SYSTEM.md)

**Build alınacak:**
→ [BUILD_PIPELINE.md](BUILD_PIPELINE.md)

**Müşteriye dağıtım / ZIP:**
→ [DISTRIBUTION.md](DISTRIBUTION.md)

**"Bunu neden böyle yaptık?" sorusu:**
→ [DO_NOT_REINTRODUCE.md](DO_NOT_REINTRODUCE.md)

**Admin panel değişikliği:**
→ [ADMIN_PANEL.md](ADMIN_PANEL.md)

---

## Proje Özeti (1 Sayfa)

ContraCore bir **multi-module PySide6 desktop uygulaması**dır. İki ayrı modülü (`xml-fatura`, `compare-191`) bir unified shell içinde barındırır.

**Shell:** `main.py` → `core/shell.py` (QMainWindow) → `core/sidebar.py` + `QStackedWidget`  
**Modül yükleme:** `core/router.py` (lazy, importlib, sys.modules izolasyonu)  
**Lisans:** `core/license/` — V2 HMAC-SHA256, offline, HWID bound, module bound  
**Admin panel:** `tools/license_manager.py` — müşteriye gitmez  
**Build:** `build_tools/build_contracore.py` → `release/ContraCORE/ContraCORE.exe`

**Kritik kural:** `tools/license_manager.py` ve `build_tools/` müşteri build'ine **asla dahil edilmez**.
