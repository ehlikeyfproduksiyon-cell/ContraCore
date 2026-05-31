# -*- coding: utf-8 -*-
"""
VKN, TCKN, dönem ve dosya yolu doğrulama — saf Python, yan etkisiz.
"""
import os
import re
from decimal import Decimal, InvalidOperation


def validate_vkn(vkn: str) -> tuple[bool, str]:
    """10 haneli VKN veya 11 haneli TCKN doğrulama."""
    vkn = str(vkn).strip().replace(" ", "")
    if not vkn.isdigit():
        return False, "VKN yalnızca rakam içermelidir"
    if len(vkn) == 11:
        # TCKN (bireysel mükellef)
        return validate_tckn(vkn)
    if len(vkn) != 10:
        return False, f"VKN 10 haneli olmalıdır (girilen: {len(vkn)} hane)"

    # VKN checksum algoritması
    digits = [int(c) for c in vkn]
    total = 0
    for i in range(9):
        step1 = (digits[i] + (9 - i)) % 10
        step2 = (step1 * (2 ** (9 - i))) % 9
        if step2 == 0 and step1 != 0:
            step2 = 9
        total += step2
    check = (10 - (total % 10)) % 10
    if check != digits[9]:
        return False, "VKN geçersiz (checksum hatası)"
    return True, ""


def validate_tckn(tckn: str) -> tuple[bool, str]:
    """11 haneli TC Kimlik Numarası doğrulama."""
    tckn = str(tckn).strip()
    if not tckn.isdigit() or len(tckn) != 11:
        return False, "TCKN 11 haneli rakamdan oluşmalıdır"
    if tckn[0] == "0":
        return False, "TCKN 0 ile başlayamaz"
    d = [int(c) for c in tckn]
    if ((d[0]+d[2]+d[4]+d[6]+d[8])*7 - (d[1]+d[3]+d[5]+d[7])) % 10 != d[9]:
        return False, "TCKN geçersiz"
    if (sum(d[:10])) % 10 != d[10]:
        return False, "TCKN geçersiz"
    return True, ""


def validate_donem(yil: int, ay: int) -> tuple[bool, str]:
    """Dönem yılı ve ayı geçerliliği."""
    try:
        yil, ay = int(yil), int(ay)
    except (TypeError, ValueError):
        return False, "Yıl ve ay sayısal olmalıdır"
    if not (2000 <= yil <= 2100):
        return False, f"Geçersiz yıl: {yil}"
    if not (1 <= ay <= 12):
        return False, f"Geçersiz ay: {ay}"
    return True, ""


def validate_word_dosya(path: str) -> tuple[bool, str]:
    """Word dosyasının varlığını ve uzantısını kontrol eder."""
    if not path:
        return False, "Word dosya yolu boş"
    path = str(path).strip()
    if not os.path.exists(path):
        return False, f"Dosya bulunamadı: {path}"
    ext = os.path.splitext(path)[1].lower()
    if ext not in (".doc", ".docx"):
        return False, f"Geçersiz dosya uzantısı: {ext} (beklenen: .doc veya .docx)"
    return True, ""


def normalize_tutar(s: str) -> Decimal | None:
    """'83.400,00' veya '83400.00' → Decimal. Parse başarısız → None."""
    if not s:
        return None
    s = str(s).strip()
    # Türkçe format: nokta binlik ayraç, virgül ondalık
    # İngilizce format: virgül binlik ayraç, nokta ondalık
    # Önce en yaygın Türkçe formatı dene
    s_clean = re.sub(r"[^\d.,]", "", s)
    if not s_clean:
        return None
    try:
        if "," in s_clean and "." in s_clean:
            # 83.400,00 → Türkçe
            if s_clean.rindex(",") > s_clean.rindex("."):
                s_clean = s_clean.replace(".", "").replace(",", ".")
            else:
                # 83,400.00 → İngilizce
                s_clean = s_clean.replace(",", "")
        elif "," in s_clean:
            # Sadece virgül → ondalık ayraç kabul et
            s_clean = s_clean.replace(",", ".")
        return Decimal(s_clean)
    except InvalidOperation:
        return None


def validate_telefon(tel: str) -> tuple[bool, str]:
    """10 veya 11 haneli Türk telefon numarası."""
    tel = re.sub(r"[\s\-\(\)+]", "", str(tel))
    if tel.startswith("90"):
        tel = tel[2:]
    if tel.startswith("0"):
        tel = tel[1:]
    if not tel.isdigit() or len(tel) != 10:
        return False, f"Geçersiz telefon: {tel}"
    return True, ""


def normalize_telefon(tel: str) -> str:
    """Telefonu '5XXXXXXXXX' (10 hane, başında 0 yok) formatına getirir."""
    tel = re.sub(r"[\s\-\(\)+]", "", str(tel))
    if tel.startswith("90"):
        tel = tel[2:]
    if tel.startswith("0"):
        tel = tel[1:]
    return tel
