# -*- coding: utf-8 -*-
"""
Master Excel'den job listesi üretimi.
Sütun isimleri karsit_master.xlsm yapısına göre eşlenir.
"""
import os
import uuid
from dataclasses import dataclass, field

from . import karsit_db as db
from .karsit_validator import (
    validate_vkn, validate_donem, validate_word_dosya,
    normalize_telefon, validate_telefon,
)

# ── Excel sütun → iç alan eşlemesi ───────────────────────────────────────────
_COL_FIRMA        = "Karşıt Firma Adı"
_COL_KARSIT_VKN   = "Karşıt VKN"
_COL_WORD         = "Word Dosyası Adı"
_COL_TUTANAK_NO   = "Tutanak Sayısı"
_COL_MUKELLEF_VKN = "Mükellef VKN\n(Tasdik verilen firma)"
_COL_KDV_DONEM_TUR = "KDV Dönem\nTürü"
_COL_KARSIT_TUR   = "Tasdik Türü\n(KDV/TAM/HER_IKISI)"
_COL_TELEFON      = "Mükellef Telefonu"
_COL_DURUM        = "DURUM"
_COL_DONEM_KDV    = "KDV İade Başlangıç Dönemi (AA/YYYY)"
_COL_DONEM_KDV_BT = "KDV İade Bitiş Dönemi (AA/YYYY)"
_COL_DONEM_KDV_ID = "KDV İade\nDönemi (AA/YYYY)"
_COL_DONEM_TAM    = "Tam Tasdik\nBaşlangıç (AA/YYYY)"
_COL_DONEM_TAM_BT = "Tam Tasdik\nBitiş (AA/YYYY)"
_COL_KDV_SOZ_TAR  = "KDV Sözleşme\nTarihi (GG.AA.YYYY)"
_COL_KDV_SOZ_NO   = "KDV Sözleşme No"
_COL_KDV_SOZ_GIR  = "KDV Sözleşme\nGiriş Tarihi"
_COL_TAM_SOZ_TAR  = "Tam Tasdik Sözl.\nTarihi"
_COL_TAM_SOZ_NO   = "Tam Tasdik\nSözl. No"
_COL_TAM_SOZ_GIR  = "Tam Tasdik\nGiriş Tarihi"


# ── Yardımcı: Excel hücre değeri → temiz string ──────────────────────────────

def _str(val) -> str:
    """NaN, float, int, Timestamp → temiz string."""
    import math
    if val is None:
        return ""
    try:
        if isinstance(val, float) and math.isnan(val):
            return ""
    except Exception:
        pass
    return str(val).strip()


def _vkn_str(val) -> str:
    """VKN hücresini 10 haneli stringe çevirir (Excel başındaki 0'ı düşürür)."""
    s = _str(val)
    # float olarak geliyorsa ".0" sonunu kes
    if s.endswith(".0"):
        s = s[:-2]
    # Sadece rakam bırak
    s = "".join(c for c in s if c.isdigit())
    # 10 haneye sıfır ön ek
    return s.zfill(10) if s else ""


def _donem_str(val) -> str:
    """
    Dönem hücresini 'AA/YYYY' formatına çevirir.
    Excel genellikle float olarak okur: 1.2025 → '01/2025', 12.2025 → '12/2025'
    Alternatif: '01/2025' string, '01.2025' string.
    """
    import math
    import pandas as pd
    if val is None:
        return ""
    if isinstance(val, float):
        if math.isnan(val):
            return ""
        # 1.2025 → ay=1, yıl=2025
        s = f"{val:.4f}"          # '1.2025' ya da '12.2025'
        parts = s.split(".")
        if len(parts) == 2 and len(parts[1]) == 4:
            ay   = parts[0].zfill(2)
            yil  = parts[1]
            return f"{ay}/{yil}"
        return _str(val)
    if hasattr(val, 'strftime'):  # Timestamp / datetime
        return val.strftime("%m/%Y")
    s = _str(val).replace(".", "/")
    # '01/2025' ya da '1/2025'
    if "/" in s:
        p = s.split("/")
        if len(p) == 2:
            return f"{p[0].zfill(2)}/{p[1]}"
    return s


def _tarih_str(val) -> str:
    """Tarih hücresini 'GG.AA.YYYY' formatına çevirir."""
    import math
    if val is None:
        return ""
    if isinstance(val, float) and math.isnan(val):
        return ""
    if hasattr(val, 'strftime'):
        return val.strftime("%d.%m.%Y")
    s = _str(val)
    if not s:
        return ""
    # pandas dtype=str ile okunan datetime: "2026-02-02 00:00:00" → "02.02.2026"
    import re
    m = re.match(r'^(\d{4})-(\d{2})-(\d{2})', s)
    if m:
        return f"{m.group(3)}.{m.group(2)}.{m.group(1)}"
    return s


def _tel_str(val) -> str:
    """Telefon hücresini rakam-only stringe çevirir."""
    s = _str(val)
    if s.endswith(".0"):
        s = s[:-2]
    return "".join(c for c in s if c.isdigit())


# ── Veri sınıfları ────────────────────────────────────────────────────────────

@dataclass
class ImportRow:
    excel_row:    int
    firma_adi:    str
    karsit_vkn:   str
    mukellef_vkn: str
    donem_yil:    int | None
    donem_ay:     int | None
    karsit_tur:   str
    word_dosya:   str       # tam yol
    telefon:      str
    tutanak_no:      str = ""
    kdv_donem_turu:  str = ""  # "" veya "İNDİRİMLİ ORAN"
    # Sözleşme ve dönem detayları (step_data'ya JSON olarak gider)
    kdv_bas:      str = ""
    kdv_bit:      str = ""
    kdv_iade:     str = ""
    kdv_soz_tar:  str = ""
    kdv_soz_no:   str = ""
    kdv_soz_gir:  str = ""
    tam_bas:      str = ""
    tam_bit:      str = ""
    tam_soz_tar:  str = ""
    tam_soz_no:   str = ""
    tam_soz_gir:  str = ""
    hatalar: list[str] = field(default_factory=list)

    @property
    def gecerli(self) -> bool:
        return len(self.hatalar) == 0


@dataclass
class ImportResult:
    batch_id: str
    toplam:   int
    gecerli:  int
    hatali:   int
    satirlar: list[ImportRow]


# ── Ana okuma fonksiyonu ──────────────────────────────────────────────────────

def excel_oku(excel_yolu: str, word_klasor: str) -> ImportResult:
    import pandas as pd
    df = pd.read_excel(
        excel_yolu, sheet_name="Karşıt Listesi",
        header=1, engine="openpyxl", dtype=str  # HEPSİNİ string oku — VKN 0 kaybolmaz
    )
    batch_id = str(uuid.uuid4())
    satirlar: list[ImportRow] = []

    for idx, row in df.iterrows():
        excel_no = idx + 3  # header=1 → başlık satır 2, veri satır 3'ten

        firma = _str(row.get(_COL_FIRMA, ""))
        if not firma or firma.lower() == "nan":
            continue

        durum = _str(row.get(_COL_DURUM, ""))
        if durum in ("Tamamlandı", "Atlandı"):
            continue

        hatalar = []

        # ── VKN ──────────────────────────────────────────────────────────────
        karsit_vkn = _vkn_str(row.get(_COL_KARSIT_VKN, ""))
        ok, msg = validate_vkn(karsit_vkn)
        if not ok:
            hatalar.append(f"Karşıt VKN: {msg}")

        mukellef_vkn = _vkn_str(row.get(_COL_MUKELLEF_VKN, ""))

        # ── Dönem ────────────────────────────────────────────────────────────
        karsit_tur     = _str(row.get(_COL_KARSIT_TUR, "")).upper()
        kdv_donem_turu = _str(row.get(_COL_KDV_DONEM_TUR, "")).strip()
        donem_yil, donem_ay = None, None

        # Başlangıç dönemi (zorunlu)
        if "TAM" in karsit_tur and "HER" not in karsit_tur:
            donem_raw = _donem_str(row.get(_COL_DONEM_TAM, ""))
        else:
            donem_raw = _donem_str(row.get(_COL_DONEM_KDV, ""))

        if donem_raw and "/" in donem_raw:
            try:
                ay_s, yil_s = donem_raw.split("/", 1)
                donem_ay  = int(ay_s)
                donem_yil = int(yil_s)
                ok2, msg2 = validate_donem(donem_yil, donem_ay)
                if not ok2:
                    hatalar.append(f"Dönem: {msg2}")
            except ValueError:
                hatalar.append(f"Dönem ayrıştırılamadı: {donem_raw}")
        # Dönem boşsa Word dosyası varsa sorun değil — engine Word'den alır

        # ── Word dosyası ──────────────────────────────────────────────────────
        word_adi = _str(row.get(_COL_WORD, ""))
        word_tam_yol = os.path.join(word_klasor, word_adi) if word_adi else ""
        if not word_adi:
            hatalar.append("Word dosyası adı boş")
        else:
            ok3, msg3 = validate_word_dosya(word_tam_yol)
            if not ok3:
                hatalar.append(f"Word dosyası: {msg3}")

        # ── Telefon ───────────────────────────────────────────────────────────
        tel_raw = _tel_str(row.get(_COL_TELEFON, ""))
        ok4, msg4 = validate_telefon(tel_raw)
        telefon = normalize_telefon(tel_raw) if ok4 else tel_raw
        if not ok4:
            hatalar.append(f"Telefon: {msg4}")

        # ── Ek dönem / sözleşme alanları (hata vermez, engine kullanır) ──────
        kdv_bas     = _donem_str(row.get(_COL_DONEM_KDV,    ""))
        kdv_bit     = _donem_str(row.get(_COL_DONEM_KDV_BT, ""))
        kdv_iade    = _donem_str(row.get(_COL_DONEM_KDV_ID, ""))
        kdv_soz_tar = _tarih_str(row.get(_COL_KDV_SOZ_TAR,  ""))
        kdv_soz_no  = _str(row.get(_COL_KDV_SOZ_NO, ""))
        kdv_soz_gir = _tarih_str(row.get(_COL_KDV_SOZ_GIR,  ""))
        tam_bas     = _donem_str(row.get(_COL_DONEM_TAM,    ""))
        tam_bit     = _donem_str(row.get(_COL_DONEM_TAM_BT, ""))
        tam_soz_tar = _tarih_str(row.get(_COL_TAM_SOZ_TAR,  ""))
        tam_soz_no  = _str(row.get(_COL_TAM_SOZ_NO, ""))
        tam_soz_gir = _tarih_str(row.get(_COL_TAM_SOZ_GIR,  ""))
        tutanak_no  = _str(row.get(_COL_TUTANAK_NO, ""))

        satirlar.append(ImportRow(
            excel_row    = excel_no,
            firma_adi    = firma,
            karsit_vkn   = karsit_vkn,
            mukellef_vkn = mukellef_vkn,
            donem_yil    = donem_yil,
            donem_ay     = donem_ay,
            karsit_tur   = karsit_tur,
            word_dosya   = word_tam_yol,
            telefon      = telefon,
            tutanak_no      = tutanak_no,
            kdv_donem_turu  = kdv_donem_turu,
            kdv_bas         = kdv_bas,
            kdv_bit      = kdv_bit,
            kdv_iade     = kdv_iade,
            kdv_soz_tar  = kdv_soz_tar,
            kdv_soz_no   = kdv_soz_no,
            kdv_soz_gir  = kdv_soz_gir,
            tam_bas      = tam_bas,
            tam_bit      = tam_bit,
            tam_soz_tar  = tam_soz_tar,
            tam_soz_no   = tam_soz_no,
            tam_soz_gir  = tam_soz_gir,
            hatalar      = hatalar,
        ))

    gecerli = sum(1 for s in satirlar if s.gecerli)
    return ImportResult(
        batch_id = batch_id,
        toplam   = len(satirlar),
        gecerli  = gecerli,
        hatali   = len(satirlar) - gecerli,
        satirlar = satirlar,
    )


# ── Word klasöründen (Excel'siz) import ──────────────────────────────────────

def _donem_parse(donem_str: str):
    """'01/2025', '01.2025', 'Ocak 2025' → (2025, 1) döndürür."""
    import re
    if not donem_str:
        return None, None
    # AA/YYYY veya AA.YYYY
    m = re.search(r'(\d{1,2})[/.](\d{4})', donem_str)
    if m:
        ay, yil = int(m.group(1)), int(m.group(2))
        if 1 <= ay <= 12 and 2000 <= yil <= 2099:
            return yil, ay
    # YYYY/AA
    m = re.search(r'(\d{4})[/.](\d{1,2})', donem_str)
    if m:
        yil, ay = int(m.group(1)), int(m.group(2))
        if 1 <= ay <= 12 and 2000 <= yil <= 2099:
            return yil, ay
    # Türkçe ay adları
    _AY = {'ocak':1,'şubat':2,'mart':3,'nisan':4,'mayıs':5,'haziran':6,
           'temmuz':7,'ağustos':8,'eylül':9,'ekim':10,'kasım':11,'aralık':12}
    low = donem_str.lower()
    for ad, no in _AY.items():
        if ad in low:
            m2 = re.search(r'(\d{4})', low)
            if m2:
                return int(m2.group(1)), no
    return None, None


def _dot_to_slash(v: str) -> str:
    """AA.YYYY (GUI formatı) → AA/YYYY (website/DB formatı)."""
    import re
    if v and re.fullmatch(r'\d{2}\.\d{4}', v):
        return v[:2] + '/' + v[3:]
    return v


def _firma_from_dosya(dosya_yolu: str) -> str:
    """Dosya adından tarih/uzantı temizlenmiş firma adını çıkarır."""
    import os, re
    adi = os.path.splitext(os.path.basename(dosya_yolu))[0]
    adi = re.sub(r'[-_]\d{2}\.\d{2}\.\d{4}.*$', '', adi).strip()
    return adi or '?'


def word_klasor_oku(word_klasor: str, ayarlar: dict) -> ImportResult:
    """
    Word klasöründeki dosyaları ve GUI ayarlarını kullanarak ImportResult üretir.
    Excel'e ihtiyaç duymaz — veriler Word parser + GUI paneli'nden gelir.

    ayarlar dict anahtarları (_get_tasdik_ayarlari() çıktısı):
      tasdik_turu, kdv_donem_turu, kdv_bas, kdv_bit, kdv_iade,
      kdv_soz_tarih, kdv_soz_no, kdv_soz_giris,
      tam_bas, tam_bit, tam_soz_tarih, tam_soz_no, tam_soz_giris,
      mukellef_tel, tutanak_baslangic
    """
    from .karsit_parser import klasor_tara

    sonuclar = klasor_tara(word_klasor)
    batch_id = str(uuid.uuid4())

    tasdik_turu = ayarlar.get('tasdik_turu', 'KDV')
    kdv_tur     = ayarlar.get('kdv_donem_turu', '')
    telefon     = ayarlar.get('mukellef_tel', '')

    # GUI'den gelen ortak sözleşme bilgileri (nokta→slash dönüşümü)
    kdv_bas     = _dot_to_slash(ayarlar.get('kdv_bas', ''))
    kdv_bit     = _dot_to_slash(ayarlar.get('kdv_bit', ''))
    kdv_iade    = _dot_to_slash(ayarlar.get('kdv_iade', ''))
    kdv_soz_tar = ayarlar.get('kdv_soz_tarih', '')
    kdv_soz_no  = ayarlar.get('kdv_soz_no', '')
    kdv_soz_gir = ayarlar.get('kdv_soz_giris', '')
    tam_bas     = _dot_to_slash(ayarlar.get('tam_bas', ''))
    tam_bit     = _dot_to_slash(ayarlar.get('tam_bit', ''))
    tam_soz_tar = ayarlar.get('tam_soz_tarih', '')
    tam_soz_no  = ayarlar.get('tam_soz_no', '')
    tam_soz_gir = ayarlar.get('tam_soz_giris', '')

    satirlar: list[ImportRow] = []

    for i, s in enumerate(sonuclar):
        if s.get('bilgi_istem'):
            # Bilgi İsteme belgeleri atlanır — geçersiz satır olarak kaydet
            row = ImportRow(
                excel_row    = i,
                firma_adi    = s.get('karsit_firma_adi') or _firma_from_dosya(s.get('dosya_yolu', '')),
                karsit_vkn   = s.get('karsit_vkn', ''),
                mukellef_vkn = s.get('mukellef_vkn', ''),
                donem_yil    = None,
                donem_ay     = None,
                karsit_tur   = 'KDV',
                word_dosya   = s.get('dosya_yolu', ''),
                telefon      = telefon,
                hatalar      = ['Bilgi İsteme belgesi — atlandı'],
            )
            satirlar.append(row)
            continue

        # Dönem: önce Word header'ından dene, yoksa fatura tarihlerinden çıkar
        donem_yil, donem_ay = _donem_parse(s.get('inceleme_donemi', ''))

        if donem_yil is None:
            # Fatura tarihlerinden dönem al (en erken ay)
            try:
                from .karsit_parser import faturalari_cek, fatura_aylarini_al
                faturalar = faturalari_cek(s.get('dosya_yolu', ''))
                aylar = fatura_aylarini_al(faturalar)
                if aylar:
                    # '03.2025' → ay=3, yil=2025
                    ilk = aylar[0]
                    donem_ay  = int(ilk[:2])
                    donem_yil = int(ilk[3:])
            except Exception:
                pass

        # Son çare: dosya adındaki tarih (FIRMA-22.01.2026.docx)
        if donem_yil is None:
            m = re.search(r'[-_\s](\d{2})\.(\d{2})\.(\d{4})',
                          os.path.basename(s.get('dosya_yolu', '')))
            if m:
                donem_ay  = int(m.group(2))
                donem_yil = int(m.group(3))

        # Word'den gelen sözleşme tarihleri GUI değerlerini override edebilir
        row_kdv_soz_tar = s.get('kdv_soz_tarih') or kdv_soz_tar
        row_tam_soz_tar = (s.get('tam_soz_tarih') or tam_soz_tar) if tasdik_turu == 'HER_IKISI' else ''
        row_tam_soz_no  = (s.get('tam_soz_no')  or tam_soz_no)  if tasdik_turu == 'HER_IKISI' else ''

        hatalar = []
        if not s.get('karsit_vkn'):
            hatalar.append('Karşıt VKN bulunamadı')
        if donem_yil is None:
            raw = s.get('inceleme_donemi', '')
            hatalar.append(f'Dönem parse edilemedi → "{raw}" (beklenen: "AA/YYYY" veya "Ocak 2026")')

        karsit_adi  = s.get('karsit_firma_adi') or _firma_from_dosya(s.get('dosya_yolu', ''))
        mukellef_adi = s.get('mukellef_adi', '')
        # Önizleme ve log için "Mükellef / Karşıt" formatı
        if mukellef_adi and mukellef_adi.upper() != karsit_adi.upper():
            firma_adi = f'{mukellef_adi}  /  {karsit_adi}'
        else:
            firma_adi = karsit_adi

        row = ImportRow(
            excel_row    = i,
            firma_adi    = firma_adi,
            karsit_vkn   = s.get('karsit_vkn', ''),
            mukellef_vkn = s.get('mukellef_vkn', ''),
            donem_yil    = donem_yil,
            donem_ay     = donem_ay,
            karsit_tur   = tasdik_turu,
            word_dosya   = s.get('dosya_yolu', ''),
            telefon      = telefon,
            kdv_donem_turu = kdv_tur,
            kdv_bas      = kdv_bas,
            kdv_bit      = kdv_bit,
            kdv_iade     = kdv_iade,
            kdv_soz_tar  = row_kdv_soz_tar,
            kdv_soz_no   = kdv_soz_no,
            kdv_soz_gir  = kdv_soz_gir,
            tam_bas      = tam_bas     if tasdik_turu == 'HER_IKISI' else '',
            tam_bit      = tam_bit     if tasdik_turu == 'HER_IKISI' else '',
            tam_soz_tar  = row_tam_soz_tar,
            tam_soz_no   = row_tam_soz_no,
            tam_soz_gir  = tam_soz_gir if tasdik_turu == 'HER_IKISI' else '',
            hatalar      = hatalar,
        )
        satirlar.append(row)

    gecerli = sum(1 for r in satirlar if r.gecerli)
    return ImportResult(
        batch_id = batch_id,
        toplam   = len(satirlar),
        gecerli  = gecerli,
        hatali   = len(satirlar) - gecerli,
        satirlar = satirlar,
    )


def _tutanak_uret(baslangic: str, idx: int) -> str:
    """'2026/0012' formatından idx adım sonrasını üretir: '2026/0014' gibi."""
    if not baslangic or '/' not in baslangic:
        return baslangic
    parca = baslangic.split('/', 1)
    try:
        yil = parca[0].strip()
        no  = int(parca[1].strip())
        pad = len(parca[1].strip())
        return f"{yil}/{str(no + idx).zfill(pad)}"
    except (ValueError, IndexError):
        return baslangic


def kaydet_db(result: ImportResult, ymm_profil: dict, kullanici: str,
              tutanak_baslangic: str = "", kdv_soz_no_override: str = "") -> str:
    import json
    gecerli_satirlar = [s for s in result.satirlar if s.gecerli]
    db.create_batch(result.batch_id, json.dumps(ymm_profil, ensure_ascii=False), kullanici, len(gecerli_satirlar))

    for idx, s in enumerate(gecerli_satirlar):
        tutanak = (_tutanak_uret(tutanak_baslangic, idx)
                   if tutanak_baslangic else s.tutanak_no)
        kdv_soz = kdv_soz_no_override if kdv_soz_no_override else s.kdv_soz_no

        step_data = json.dumps({
            "mukellef_vkn":    s.mukellef_vkn,
            "tutanak_sayisi":  tutanak,
            "kdv_donem_turu":  s.kdv_donem_turu,
            "kdv_bas":         s.kdv_bas,
            "kdv_bit":      s.kdv_bit,
            "kdv_iade":     s.kdv_iade,
            "kdv_soz_tarih": s.kdv_soz_tar,
            "kdv_soz_no":   kdv_soz,
            "kdv_soz_giris": s.kdv_soz_gir,
            "tam_bas":      s.tam_bas,
            "tam_bit":      s.tam_bit,
            "tam_soz_tarih": s.tam_soz_tar,
            "tam_soz_no":   s.tam_soz_no,
            "tam_soz_giris": s.tam_soz_gir,
        }, ensure_ascii=False)

        db.create_job(result.batch_id, {
            "firma_adi":  s.firma_adi,
            "vkn":        s.karsit_vkn,
            "donem_yil":  s.donem_yil,
            "donem_ay":   s.donem_ay,
            "karsit_tur": s.karsit_tur,
            "word_dosya": s.word_dosya,
            "telefon":    s.telefon,
            "excel_row":  s.excel_row,
            "step_data":  step_data,
        })

    return result.batch_id
