# ContraCore — Update Test Checklist

**Production release öncesi bu checklist eksiksiz geçilmelidir.**

---

## Ön Koşullar

- [ ] Test PC'de kurulu sürüm = `N-1` (yeni sürümden bir önceki)
- [ ] GitHub Release'de yeni ZIP yüklenmiş (`ContraCORE_update.zip`)
- [ ] GitHub main branch'te `update.json` doğru SHA256 ile push edilmiş
- [ ] `update.json` version = yeni sürüm, `zip_sha256` = ZIP'in gerçek SHA256'sı

---

## Senaryo 1 — Launcher Dialog'undan Güncelleme ("Şimdi Güncelle")

- [ ] `ContraCORELauncher.exe` açılıyor
- [ ] Güncelleme dialog'u çıkıyor (navy arka plan, gold başlık)
- [ ] "Şimdi Güncelle" tıklanıyor
- [ ] İndirme progress bar görünüyor (navy bg, mavi bar)
- [ ] İndirme tamamlanıyor (hata yoksa)
- [ ] SHA256 doğrulaması geçiyor
- [ ] ContraCORE.exe açılıyor (güncelleme tamamlanınca)
- [ ] `update.json` içinde yeni versiyon yazıyor
- [ ] "Yenilikler" / "What's New" dialog çıkıyor (eğer `notes` doluysa)
- [ ] Sidebar'da güncelleme butonu görünmüyor (pending temizlendi)

---

## Senaryo 2 — Launcher Dialog'undan "Sonra"

- [ ] "Sonra" tıklanıyor
- [ ] ContraCORE açılıyor
- [ ] Sidebar'da mavi "Güncelleme Mevcut" butonu görünüyor
- [ ] Buton üzerine gelince hover rengi değişiyor (#1a7ffd)

---

## Senaryo 3 — ContraCORE Sidebar'dan Güncelleme

- [ ] Sidebar'daki mavi güncelleme butonuna tıklanıyor
- [ ] Navy onay dialog'u çıkıyor: "Daha Sonra" / "Güncelle"
- [ ] "Güncelle" tıklanıyor
- [ ] ContraCORE kapanıyor
- [ ] İndirme progress bar görünüyor
- [ ] ContraCORE tekrar açılıyor (güncelleme sonrası)
- [ ] Yeni versiyon yüklü (sidebar title veya About'tan kontrol)

---

## Senaryo 4 — Bozuk ZIP (SHA256 Uyuşmazlığı)

- [ ] Hata dialog'u görünüyor: "Güncelleme dosyası bozuk veya değiştirilmiş"
- [ ] ContraCORE eski sürümle açılıyor (rollback çalıştı)
- [ ] `_backup/` klasörü temizlenmiş (rollback sonrası)

---

## Senaryo 5 — Güncelleme Yok

- [ ] Launcher sessizce ContraCORE'u açıyor (dialog yok)
- [ ] Sidebar'da güncelleme butonu görünmüyor

---

## Senaryo 6 — Stale Pending

- [ ] `%APPDATA%\ContraCore\pending_update.json` eski/geçersiz versiyon içeriyor
- [ ] ContraCORE açılınca otomatik temizleniyor (sidebar butonu çıkmıyor)

---

## Güvenlik Kontrolleri

- [ ] Güncelleme sonrası `%APPDATA%\ContraCore\license.json` bozulmamış
- [ ] Trial verileri (`trial_*.json`, registry) bozulmamış
- [ ] `pending_update.json` güncelleme sonrası silindi
- [ ] `last_update.json` güncelleme sonrası silindi (ContraCORE okuyunca)

---

## Bilinen Sorunlar ve Önlemler

| Sorun | Kontrol |
|---|---|
| WinError 225 | ContraCORE.exe açılıyor mu? ShellExecuteW kullanıldı mı? |
| WinError 5 | DLL'ler `rename-first` ile replace edildi mi? |
| ImportError: read_last_update | `--clean` ile build alındı mı? |
| SHA256 uyuşmazlığı | GitHub Release'e doğru ZIP yüklendi mi? |
| Program güncelleme sonrası açılmıyor | Crash log kontrol et: `%APPDATA%\ContraCore\crash_log.txt` |
| Launcher log | `%TEMP%\contracore_launcher_log.txt` |
