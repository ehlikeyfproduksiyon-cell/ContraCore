# ContraCore — Update Test Checklist

**Production release öncesi bu checklist eksiksiz geçilmelidir.**

---

## Ortam Hazırlığı

- [ ] Test makinede `1.0.0` kurulu (temiz kurulum)
- [ ] `%APPDATA%\ContraCore\` mevcut (lisans + trial verileri yazılı)
- [ ] `ContraCORELauncher.exe` masaüstü kısayolu veya doğrudan çalıştırma
- [ ] GitHub repo'da `1.0.1` release hazır: `ContraCORE_update.zip` + güncel `update.json`
- [ ] `update.json` main branch'e push edildi

---

## 1. Güncelleme Yok Senaryosu

**Durum:** Lokal versiyon = remote versiyon

- [ ] Launcher sessizce açılır, dialog gelmez
- [ ] `ContraCORE.exe` doğrudan başlar
- [ ] Banner görünmez
- [ ] `%TEMP%\contracore_launcher_log.txt` kontrol: "Güncelleme mevcut" satırı yok

---

## 2. Güncelleme Mevcut — "Şimdi Güncelle"

**Durum:** Lokal `1.0.0`, remote `1.0.1`

- [ ] Launcher Tkinter dialog açar: "Sürüm 1.0.1 hazır."
- [ ] "Şimdi Güncelle" seçilir
- [ ] ZIP indirilir (progress görünmez, beklenir)
- [ ] SHA256 doğrulanır (log'a yazılır)
- [ ] `modules/`, `Icon/`, `Logom/` replace edilir
- [ ] `ContraCORE.exe` replace edilir
- [ ] `release/ContraCORE/update.json` → `version: "1.0.1"` olur
- [ ] `ContraCORE.exe` açılır
- [ ] Banner görünmez (pending_update.json yok)
- [ ] Lokal `update.json` → version `1.0.1`
- [ ] Yeni modül veya özellik görünür (varsa)

---

## 3. Güncelleme Mevcut — "Sonra"

**Durum:** Lokal `1.0.0`, remote `1.0.1`

- [ ] Dialog açılır, "Sonra" seçilir
- [ ] `%APPDATA%\ContraCore\pending_update.json` oluşturulur
- [ ] `ContraCORE.exe` açılır
- [ ] 1-2 saniye sonra sarı banner görünür: "ContraCORE 1.0.1 hazır"
- [ ] Sidebar Lisans butonu kırmızı "Güncelleme v1.0.1" olur
- [ ] Banner "✕" ile kapatılabilir (sadece görsel, pending silinmez)
- [ ] "Güncelle" butonuna basılır → Launcher `--do-update` ile başlar → ContraCORE kapanır
- [ ] Launcher güncellemeyi yapar → ContraCORE yeni sürümle açılır
- [ ] Sonraki açılışta banner gelmez (pending_update.json silindi)

---

## 4. Rollback Testi

**Durum:** ZIP bilerek bozulur (içindeki ContraCORE.exe silinir)

- [ ] SHA256 kontrolü başarısız → "Güncelleme dosyası bozuk" hatası
- [ ] Veya: extract sonrası ContraCORE.exe yoksa → "paket geçersiz" hatası
- [ ] Rollback yapılır: `_backup/` → install_dir
- [ ] ContraCORE eski sürümle açılır
- [ ] `_backup/` temizlenir
- [ ] `_temp_apply/` kalmaz

---

## 5. İnternet Kesilme Testi

**Durum:** Ağ bağlantısı yok iken Launcher açılır

- [ ] update.json indirme timeout'a girer (10 sn)
- [ ] Hata popup gelmez — sessizce bypass
- [ ] `%TEMP%\contracore_launcher_log.txt` → hata logu var
- [ ] ContraCORE normal açılır

---

## 6. Bozuk ZIP Testi

**Durum:** ZIP indirildi ama SHA256 uyuşmuyor (farklı dosya)

- [ ] `_validate_zip()` SHA256 uyuşmazlığını tespit eder
- [ ] "Güncelleme dosyası bozuk veya değiştirilmiş" dialog gösterilir
- [ ] Mevcut kurulum bozulmaz
- [ ] ContraCORE açılır

---

## 7. Yeni Modül Ekleme Testi

**Durum:** `1.0.1` build'inde 3. modül eklendi (örn. yeni-modul)

- [ ] Update sonrası `modules/yeni-modul/` klasörü mevcut
- [ ] Sidebar'da yeni modül görünür
- [ ] Lisans ve trial akışı çalışır
- [ ] Eski modüllerin lisans/trial verisi bozulmadı

---

## 8. Eski Modül Kaldırma Testi

**Durum:** `1.0.1` build'inde bir modül kaldırıldı

- [ ] Update sonrası eski modül klasörü silinmiş (`modules/` temizlenip yenisi geldi)
- [ ] Sidebar'da eski modül görünmüyor
- [ ] ContraCORE crash etmiyor

---

## 9. Trial / Lisans Korunma Testi

**Durum:** Her iki güncelleme senaryosu (Şimdi + Sonra)

- [ ] `%APPDATA%\ContraCore\license.json` değişmedi
- [ ] `%APPDATA%\ContraCore\trial_xml-fatura.json` değişmedi
- [ ] `%APPDATA%\ContraCore\trial_compare-191.json` değişmedi
- [ ] Registry trial verileri (`HKCU\Software\ContraCore\Trial\`) korundu
- [ ] Gizli CLSID registry korundu
- [ ] Modüller lisanslı/trial/locked durumlarını korudu
- [ ] Lisans yeniden girmek gerekmedi

---

## 10. Antivirus False Positive Testi

**Durum:** Windows Defender açık, gerçek makine

- [ ] Launcher indirilip ilk açılışta SmartScreen uyarısı yönetilebilir
- [ ] Güncelleme sırasında Defender ZIP extract'i engellemiyor
- [ ] `ContraCORE.exe` replace sonrası Defender karantinaya almıyor
- [ ] Eğer false positive varsa: akış doğru, kullanıcı bilgilendirme metni hazırla

---

## 11. Launcher Lock Testi

**Durum:** Launcher iki kez aynı anda başlatılır

- [ ] İkinci Launcher `%TEMP%\contracore_update.lock` görür
- [ ] PID kontrolü: birinci hâlâ çalışıyor → ikinci sessizce çıkar
- [ ] Güncelleme çift uygulanmaz

---

## 12. ContraCORELauncher.exe Overwrite Testi

**Durum:** ZIP içinde yeni ContraCORELauncher.exe var

- [ ] Apply sırasında "skip edildi (çalışıyor)" log'u var
- [ ] Eski Launcher kalmaya devam eder
- [ ] Sonraki güncelleme paketi yeni Launcher'ı içeriyorsa, o güncelleme sırasında da aynı skip olur
- [ ] **Not:** Launcher güncellemesi için kullanıcıya zip'ten manuel replace talimatı verilebilir (nadir senaryo)

---

## Log Kontrol Noktaları

Her testten sonra kontrol edilmesi gereken log:
```
%TEMP%\contracore_launcher_log.txt
```

Beklenen satırlar (güncelleme başarılıysa):
```
[...] Launcher başladı — install_dir=...
[...] Güncelleme mevcut: 1.0.0 → 1.0.1
[...] İndiriliyor: https://github.com/.../ContraCORE_update.zip
[...] İndirme tamamlandı: XX.X MB
[...] Yedek alındı.
[...] Staging tamamlandı.
[...] Replace tamamlandı.
[...] Güncelleme başarılı: 1.0.1
[...] ContraCORE.exe başlatıldı.
```

---

## Release Onay Kriteri

Tüm zorunlu maddeler ✅ olmadan production release yapılmaz:

| Madde | Zorunlu |
|---|---|
| 1 — Güncelleme yok senaryosu | ✅ |
| 2 — Şimdi güncelle | ✅ |
| 3 — Sonra + banner | ✅ |
| 4 — Rollback | ✅ |
| 5 — İnternet kesilme | ✅ |
| 6 — Bozuk ZIP | ✅ |
| 9 — Trial/lisans korunma | ✅ |
| 10 — Antivirus | ✅ |
| 7 — Yeni modül | Varsa |
| 8 — Modül kaldırma | Varsa |
| 11 — Lock | Varsa |
| 12 — Launcher overwrite | Varsa |
