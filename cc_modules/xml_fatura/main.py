#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
XML Fatura Otomasyonu — Ana İşlem Motoru
e-Fatura UBL 2.1 XML → Excel
Developed by Serkan ŞAHİN © 2026
"""

import os, sys, zipfile, re, json
from datetime import datetime
from collections import defaultdict
import xml.etree.ElementTree as ET

import xlsxwriter

# ═══════════════════════════════════════════════════════════════════════════════
#  SABITLER
# ═══════════════════════════════════════════════════════════════════════════════

NS = {
    'cac': 'urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2',
    'cbc': 'urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2',
}

# Kısaltma sözlüğü — uzundan kısaya sıralı (önce uzun ifadeler eşleşsin)
ABBR = [
    ('ANONİM ŞİRKETİ',      'A.Ş.'),
    ('ANONİM SIRKETI',       'A.Ş.'),
    ('LİMİTED ŞİRKETİ',     'LTD. ŞTİ.'),
    ('LIMITED SIRKETI',      'LTD. ŞTİ.'),
    ('LİMİTED SIRKETI',      'LTD. ŞTİ.'),
    ('KOLLEKTİF ŞİRKETİ',   'KOLL. ŞTİ.'),
    ('KOMANDİT ŞİRKETİ',    'KOM. ŞTİ.'),
    ('ULUSLARARASI',         'ULUSL.'),
    ('GAYRİMENKUL',          'GAYRİM.'),
    ('TAŞIMACILIK',          'TAŞM.'),
    ('MÜHENDİSLİK',          'MÜH.'),
    ('DANIŞMANLIK',          'DAN.'),
    ('MÜŞAVİRLİK',           'MÜŞ.'),
    ('İŞLETMECİLİĞİ',        'İŞL.'),
    ('MALZEMELERİ',          'MALZ.'),
    ('SİSTEMLERİ',           'SİS.'),
    ('HİZMETLERİ',           'HİZ.'),
    ('YAYINCILIK',           'YAY.'),
    ('MADENCİLİK',           'MAD.'),
    ('ELEKTRONİK',           'ELKT.'),
    ('TEKNOLOJİ',            'TEKN.'),
    ('PAZARLAMA',            'PAZ.'),
    ('NAKLİYAT',             'NAK.'),
    ('İTHALAT',              'İTH.'),
    ('İHRACAT',              'İHR.'),
    ('TİCARET',              'TİC.'),
    ('TICARET',              'TİC.'),
    ('SANAYİ',               'SAN.'),
    ('SANAYI',               'SAN.'),
    ('İNŞAAT',               'İNŞ.'),
    ('INSAAT',               'İNŞ.'),
    ('YATIRIM',              'YAT.'),
    ('ELEKTRİK',             'ELK.'),
    ('ENERJİ',               'ENR.'),
    ('LOJİSTİK',             'LOJ.'),
    ('TURİZM',               'TUR.'),
    ('TARIM',                'TAR.'),
    ('PETROL',               'PTR.'),
    ('KİMYA',                'KİM.'),
    ('BİLİŞİM',              'BİL.'),
    ('YAZILIM',              'YAZ.'),
    ('DEPOLAMA',             'DEP.'),
    ('GIDA',                 'GID.'),
    ('SAĞLIK',               'SAĞ.'),
    ('HAYVANCILIK',          'HAYV.'),
    ('ÜRÜNLERİ',             'ÜRN.'),
    ('İHTİYAÇ',              'İHT.'),
    ('ORTAKLIĞI',            'ORT.'),
    ('ORGANİZASYON',         'ORG.'),
    ('AMBALAJ',              'AMB.'),
    ('TEKSTİL',              'TEKST.'),
    ('KONFEKSİYON',          'KONF.'),
    ('MOBİLYA',              'MOB.'),
    ('TAAHHÜT',              'TAAH.'),
    ('ZİRAAT',               'ZİR.'),
    ('DOĞALGAZ',             'D.GAZ'),
]

# Türkçe ay isimleri
MONTHS_TR = {
    1: 'OCAK', 2: 'ŞUBAT', 3: 'MART', 4: 'NİSAN',
    5: 'MAYIS', 6: 'HAZİRAN', 7: 'TEMMUZ', 8: 'AĞUSTOS',
    9: 'EYLÜL', 10: 'EKİM', 11: 'KASIM', 12: 'ARALIK',
}

# UBL birim kodu → Türkçe
UNIT_MAP = {
    'C62': 'Adet', 'NIU': 'Adet', 'EA': 'Adet', 'U': 'Adet',
    'KGM': 'Kg',   'GRM': 'Gr',   'TNE': 'Ton',
    'MTR': 'Metre','CMT': 'Cm',   'MMT': 'Mm',
    'MTK': 'm²',   'MTQ': 'm³',
    'LTR': 'Litre','MLT': 'ml',
    'HUR': 'Saat', 'DAY': 'Gün',  'MON': 'Ay',
    'KWH': 'kWh',  'KWT': 'kW',
    'BX':  'Kutu', 'CT':  'Karton','SET': 'Set',
    'PR':  'Çift', 'LS':  'Götürü',
    'ZZ':  'Diğer','D61': 'Adet',
}

# Excel renk paleti
CLR_HDR_BG   = '1E3A5F'   # lacivert — başlık bg
CLR_HDR_FG   = 'FFFFFF'   # beyaz — başlık yazı
CLR_ALT_BG   = 'EEF4FB'   # açık mavi — çift satır
CLR_TOTAL_BG = '1E3A5F'   # lacivert — toplam satırı
CLR_TITLE_BG = '0B2545'   # daha koyu — belge başlığı
CLR_BORDER   = 'C0C8D8'   # kenarlık
CLR_HDR2_BG  = '2E5D9E'   # 2. başlık bg (kalem sayfası)
CLR_SAT_BG   = '1A5C38'   # satış yeşil
CLR_SAT_ALT  = 'EBF5EF'   # satış açık yeşil

# (xlsxwriter format nesneleri workbook başına oluşturulur — modül sabiti yok)

# ── PDF parse için önceden derlenmiş regex pattern'ları ─────────────────────────
_RE_INV_ID     = re.compile(r'\b([A-Z][A-Z0-9]{0,4}\d{13,})\b')
_RE_DATE_FIND  = re.compile(r'\b(\d{2}[.\-/]\d{2}[.\-/]\d{4})\b')
_RE_DATE_PARSE = re.compile(r'(\d{2})[.\-/](\d{2})[.\-/](\d{4})')
_RE_MATRAH_PATS = tuple(re.compile(p, re.IGNORECASE) for p in (
    r'Mal\s*[/]?\s*Hizmet\s*Toplam\s*Tutar[ı]?\s*[:\s]?\s*([\d.,]+)',
    r'(?:Ara\s*)?Toplam\s*[Tt]utar[:\s]\s*([\d.,]+)',
    r'KDV\s*Hari[cç]\s*(?:Tutar|Matrah)[:\s(]+\s*([\d.,]+)',
    r'KDV\s*\(\s*Matrah\s*([\d.,]+)\)',
    r'ARA\s*TOPLAM\s*[:\s]\s*([\d.,]+)',
))
_RE_KDV_MAIN  = re.compile(r'Hesaplanan\s*KDV[^:\n]{0,40}:\s*([\d.,]+)', re.IGNORECASE)
_RE_KDV_PATS  = tuple(re.compile(p, re.IGNORECASE) for p in (
    r'Hesaplanan\s*KDV\s*\([^)]+\)\s*([\d.,]+)',
    r'Hesaplanan\s*KDV\s*%[\d,]+\s*[:\s]\s*([\d.,]+)',
))
_RE_KDV_ELEC  = re.compile(r'KDV\s*\(\s*Matrah\s*[\d.,]+\)\s*([\d.,]+)', re.IGNORECASE)
_RE_KDV_PRC   = re.compile(r'KDV\s*\(%[\d.,]+\)\s*[:\s]\s*([\d.,]+)', re.IGNORECASE)
_RE_TOPLAM_PATS = tuple(re.compile(p, re.IGNORECASE) for p in (
    r'(?:Ödenecek|Vergiler\s*Dahil)\s*Tutar[ı]?\s*[:\s]?\s*([\d.,]+)',
    r'Vergiler\s*Dahil\s*Toplam\s*Tutar[:\s]\s*([\d.,]+)',
    r'Fatura\s*Tutar[ı]?\s*([\d.,]+)',
    r'TOPLAM\s+TUTAR\s*[:\s]\s*([\d.,]+)',
    r'TOPLAM\s*[:\s]\s*([\d.,]+)',
))


# ═══════════════════════════════════════════════════════════════════════════════
#  YARDIMCI FONKSİYONLAR
# ═══════════════════════════════════════════════════════════════════════════════

def _txt(elem, path, ns=NS, default=''):
    if elem is None:
        return default
    found = elem.find(path, ns)
    return found.text.strip() if (found is not None and found.text) else default

def _float(val, default=0.0):
    try:
        return float(str(val).replace(',', '.').strip())
    except Exception:
        return default

def _parse_date(s):
    if not s:
        return None
    # Boşlukları ve zaman kısmını temizle: "21- 02- 2025 10:48:00" → "21-02-2025"
    s = re.sub(r'\s+', '', s.split()[0] if ' ' in s.strip() else s)
    for fmt in ('%Y-%m-%d', '%d.%m.%Y', '%d/%m/%Y', '%d-%m-%Y'):
        try:
            return datetime.strptime(s, fmt)
        except Exception:
            pass
    return None

def _unit_label(code):
    return UNIT_MAP.get(str(code).upper(), code)

def _shorten_name(name, max_len=72):
    """Kısaltma sözlüğü uygula → hâlâ uzunsa kelime sınırında kes + ..."""
    s = str(name).upper().strip()
    for long_word, short_word in ABBR:
        s = s.replace(long_word, short_word)
    if len(s) <= max_len:
        return s
    cut = s[:max_len]
    last_space = cut.rfind(' ')
    if last_space > max_len - 15:
        return cut[:last_space].rstrip() + '...'
    return cut.rstrip() + '...'

def _shorten_content(text, max_len=100):
    """100. karakterde direkt kes"""
    if not text:
        return ''
    return str(text)[:max_len]

def _format_qty(lines):
    """Birimlere göre miktarları topla → '16 Adet, 4 Kutu'"""
    totals = defaultdict(float)
    for line in lines:
        unit = str(line.get('unit') or 'Adet').strip()
        totals[unit] += _float(line.get('qty', 1))
    parts = []
    for unit, qty in totals.items():
        if qty == int(qty):
            qty_str = f'{int(qty):,}'.replace(',', '.')
        else:
            qty_str = f'{qty:,.3f}'.replace(',', 'X').replace('.', ',').replace('X', '.')
        parts.append(f'{qty_str} {unit}')
    return _shorten_content(', '.join(parts), 100)

def _kdv_donem(date_obj):
    if isinstance(date_obj, datetime):
        return date_obj.strftime('%Y%m')
    return ''

def _vkn_fmt(vkn):
    """VKN/TCKN — 10 veya 11 karakter, başındaki sıfır korunur"""
    v = str(vkn or '').strip()
    if v and len(v) < 10:
        v = v.zfill(10)
    return v

def _collect_files(folder, recursive=False):
    """Klasördeki XML ve ZIP→XML dosyalarını toplar"""
    files = []
    if not folder or not os.path.isdir(folder):
        return files
    walk = os.walk(folder) if recursive else [(folder, [], os.listdir(folder))]
    for dirpath, _, filenames in walk:
        for fn in sorted(filenames):
            fp = os.path.join(dirpath, fn)
            if fn.lower().endswith(('.xml', '.html', '.pdf')):
                files.append(fp)
            elif fn.lower().endswith('.zip'):
                try:
                    with zipfile.ZipFile(fp) as zf:
                        for name in zf.namelist():
                            if name.lower().endswith('.xml'):
                                files.append((fp, name))
                except Exception:
                    pass
    return files

def _display_name(src):
    if isinstance(src, tuple):
        return f"{os.path.basename(src[0])} / {src[1]}"
    return os.path.basename(src)


# ═══════════════════════════════════════════════════════════════════════════════
#  HTML / PDF PARSE
# ═══════════════════════════════════════════════════════════════════════════════

def _num(s):
    """'1.234,56' veya '1.234' (Türkçe binlik) veya '1234.56' → float"""
    s = str(s or '').strip()
    if not s or s == '-':
        return 0.0
    s = s.replace(' ', '').replace('\xa0', '')
    if ',' in s and '.' in s:
        # Türkçe format: 1.234,56 → 1234.56
        s = s.replace('.', '').replace(',', '.')
    elif ',' in s:
        # Ondalık virgül: 0,29 → 0.29
        s = s.replace(',', '.')
    elif '.' in s:
        # Sadece nokta: son parça 3 haneli ise binlik ayracı (1.234 → 1234)
        parts = s.split('.')
        if all(len(p) == 3 for p in parts[1:]):
            s = s.replace('.', '')
        # Değilse ondalık nokta: bırak (0.29 → 0.29)
    try:
        return float(re.sub(r'[^\d.\-]', '', s) or '0')
    except ValueError:
        return 0.0


def _is_company_name(s):
    """Bir metnin şirket unvanı olup olmadığını tahmin eder."""
    kw = ('A.Ş', 'LTD', 'SAN.', 'TİC.', 'İTH.', 'PAZ.', 'ENDÜSTRİ',
          'MÜHENDİSLİK', 'İNŞAAT', 'GIDA', 'TARIM', 'NAKLİYAT',
          'HİZMET', 'YAPI', 'TEKNOLOJİ', 'ELEKTRİK', 'BOYA', 'TEMİZLİK')
    s_up = s.upper()
    return any(k in s_up for k in kw)


def parse_invoice_html(path):
    """GIB e-fatura HTML → parse_invoice ile aynı dict döner.
    Şablon A: eFinans (id=malHizmetTablosu, id=toplamlar, class=partyName)
    Şablon B: Modern  (class=lineitems, class=totals, data-role=*)
    """
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        return {'ok': False, 'error': 'beautifulsoup4 kurulu değil (pip install beautifulsoup4)'}
    try:
        with open(path, encoding='utf-8', errors='replace') as f:
            html = f.read()

        # Performans: base64 gömülü veriyi ayrıştırmadan önce temizle
        html = re.sub(r'data:[a-zA-Z0-9/+\-]+;base64,[A-Za-z0-9+/=\s]{20,}', 'X', html)

        try:
            soup = BeautifulSoup(html, 'lxml')
        except Exception:
            soup = BeautifulSoup(html, 'html.parser')

        inv_id = inv_date = sup_name = sup_vkn = cus_name = cus_vkn = ''
        inv_type = 'SATIS'
        currency = 'TRY'
        matrah = kdv = toplam = tevkifat = 0.0
        lines = []

        # ── Şablon tespiti ───────────────────────────────────────────────────
        is_efinans = bool(soup.find(id='malHizmetTablosu'))
        is_modern  = bool(soup.find(class_='lineitems') or
                          soup.find(attrs={'data-role': re.compile(r'invoice')}))

        # ── QR / JSON verisi — div#qrvalue VEYA <script> içinde ────────────
        # Bazı şablonlar div#qrvalue, bazıları script etiketini kullanır
        def _extract_qr_json(raw):
            start = raw.find('{')
            end   = raw.rfind('}')
            if start < 0 or end <= start:
                return {}
            snippet = raw[start:end + 1]
            if '"vkntckn"' not in snippet and '"no"' not in snippet:
                return {}
            try:
                return json.loads(snippet)
            except Exception:
                try:
                    cleaned = re.sub(r',\s*}', '}', re.sub(r',\s*]', ']', snippet))
                    return json.loads(cleaned)
                except Exception:
                    return {}

        qr_data = {}
        # Önce div#qrvalue dene (bazı şablonlar burada)
        qr_div = soup.find(id='qrvalue')
        if qr_div:
            qr_data = _extract_qr_json(qr_div.get_text())
        # Yoksa script etiketlerini tara (modern şablonlar)
        if not qr_data:
            for script in soup.find_all('script'):
                qr_data = _extract_qr_json(script.string or '')
                if qr_data:
                    break

        if qr_data:
            inv_id   = qr_data.get('no', '')
            inv_date = qr_data.get('tarih', '')
            inv_type = qr_data.get('tip', 'SATIS')
            currency = qr_data.get('parabirimi', 'TRY')
            sup_vkn  = _vkn_fmt(qr_data.get('vkntckn', ''))
            cus_vkn  = _vkn_fmt(qr_data.get('avkntckn', ''))
            matrah   = _float(qr_data.get('malhizmettoplam', 0))
            toplam   = _float(qr_data.get('vergidahil', 0) or qr_data.get('odenecek', 0))
            for k, v in qr_data.items():
                if 'hesaplanankdv' in k.lower():
                    kdv += _float(str(v))

        # ════════════════════════════════════════════════════════════════════
        #  ŞABLON A — eFinans (id=malHizmetTablosu)
        # ════════════════════════════════════════════════════════════════════
        if is_efinans:
            # ── Fatura No / Tarih ────────────────────────────────────────────
            if not inv_id:
                for td in soup.find_all('td'):
                    if re.search(r'Fatura\s*No', td.get_text(), re.IGNORECASE):
                        sib = td.find_next_sibling('td')
                        val = sib.get_text(strip=True) if sib else ''
                        if val:
                            inv_id = val
                            break

            if not inv_date:
                for td in soup.find_all('td'):
                    txt = td.get_text(strip=True)
                    if re.search(r'Fatura\s*Tarih', txt, re.IGNORECASE):
                        sib = td.find_next_sibling('td')
                        val = sib.get_text(strip=True) if sib else ''
                        if val:
                            inv_date = val.split()[0]
                            break

            # ── Satıcı adı ──────────────────────────────────────────────────
            if not sup_name:
                el = soup.find(class_='partyName')
                if el:
                    sup_name = el.get_text(strip=True)

            # ── Müşteri adı ─────────────────────────────────────────────────
            if not cus_name:
                for cls in ('customerTitle', 'customer-title', 'customerName'):
                    el = soup.find(class_=cls)
                    if el:
                        cus_name = el.get_text(strip=True)
                        break

            # ── VKN'ler (Vergi No etiketli td'ler) ─────────────────────────
            if not sup_vkn or not cus_vkn:
                vkn_tds = []
                for td in soup.find_all('td'):
                    txt = td.get_text(strip=True)
                    if re.search(r'Vergi\s*(Kimlik\s*)?No', txt, re.IGNORECASE):
                        sib = td.find_next_sibling('td')
                        if sib:
                            m = re.search(r'\d{10,11}', sib.get_text())
                            if m:
                                vkn_tds.append(_vkn_fmt(m.group(0)))
                if not sup_vkn and vkn_tds:
                    sup_vkn = vkn_tds[0]
                if not cus_vkn and len(vkn_tds) > 1:
                    cus_vkn = vkn_tds[1]

            # ── Toplamlar — id="toplamlar" VEYA class="toplamlar" ───────────
            _tpl_found = False
            tpl_tbl = soup.find(id='toplamlar') or soup.find(class_='toplamlar')
            if tpl_tbl:
                _tpl_found = True
                _kdv_set = False
                for row in tpl_tbl.find_all('tr'):
                    cells = [c.get_text(strip=True) for c in row.find_all(['td', 'th'])]
                    if len(cells) < 2:
                        continue
                    lbl = cells[0].lower()
                    # Değer: sondaki sayı içeren hücre
                    val_str = next((c for c in reversed(cells[1:])
                                    if re.search(r'\d', c)), '')
                    if not matrah and 'mal hizmet toplam' in lbl:
                        matrah = _num(val_str)
                    elif not _kdv_set and 'hesaplanan kdv' in lbl:
                        kdv = _num(val_str)   # KDV muafiyeti 0 olabilir — geçerli değer
                        _kdv_set = True
                    elif not toplam and ('vergiler dahil' in lbl or
                                         'ödenecek' in lbl or
                                         'genel toplam' in lbl):
                        toplam = _num(val_str)

            # ── Kalemler — id="malHizmetTablosu" (dinamik kolon tespiti) ───
            mal_tbl = soup.find(id='malHizmetTablosu')
            if mal_tbl:
                rows = mal_tbl.find_all('tr')
                # Başlık satırını tespit et
                hdr_row_idx = 0
                col = {}
                for ri, row in enumerate(rows[:3]):
                    hcells = row.find_all(['th', 'td'])
                    hdrs = [c.get_text(strip=True).lower() for c in hcells]
                    hdr_str = ' '.join(hdrs)
                    if 'mal' in hdr_str or 'hizmet' in hdr_str or 'miktar' in hdr_str:
                        hdr_row_idx = ri
                        for ci, h in enumerate(hdrs):
                            if any(k in h for k in ('mal hizmet', 'ürün', 'hizmet adı')) and 'name' not in col:
                                col['name'] = ci
                            elif 'miktar' in h and 'name' in col and 'qty' not in col:
                                col['qty'] = ci
                            elif 'birim fiyat' in h and 'unit_price' not in col:
                                col['unit_price'] = ci
                            elif 'iskonto' in h and 'disc' not in col:
                                col['disc'] = ci
                            elif ('mal hizmet tutar' in h or ('tutar' in h and 'kdv' not in h)) and 'amount' not in col:
                                col['amount'] = ci
                            elif 'kdv' in h and 'oran' in h and 'kdv_rate' not in col:
                                col['kdv_rate'] = ci
                            elif 'kdv' in h and 'tutar' in h and 'kdv_amount' not in col:
                                col['kdv_amount'] = ci
                        break
                # Kolon haritası bulunamadıysa varsayılan (Sıra|Ad|Mik|BirimFiyat|İsk|Tutar|KDV%|KDVTut)
                if 'name' not in col:
                    col = {'name': 1, 'qty': 2, 'unit_price': 3,
                           'disc': 4, 'amount': 5, 'kdv_rate': 6, 'kdv_amount': 7}

                def _hgc(cells, key, default=''):
                    idx = col.get(key)
                    return cells[idx] if (idx is not None and idx < len(cells)) else default

                for row in rows[hdr_row_idx + 1:]:
                    cells = [c.get_text(separator=' ', strip=True)
                             for c in row.find_all('td')]
                    if len(cells) < 2:
                        continue
                    name_val = _hgc(cells, 'name')
                    if not name_val or re.match(r'^[\d\s%,\.]*$', name_val):
                        continue
                    qty_raw    = _hgc(cells, 'qty', '1')
                    unit_price = _num(_hgc(cells, 'unit_price', '0'))
                    amount     = _num(_hgc(cells, 'amount', '0'))
                    kdv_rate_s = _hgc(cells, 'kdv_rate', '0')
                    kdv_amt    = _num(_hgc(cells, 'kdv_amount', '0'))
                    qty_parts  = qty_raw.split()
                    qty        = _num(qty_parts[0]) if qty_parts else 1.0
                    unit       = qty_parts[1] if len(qty_parts) > 1 else 'Adet'
                    kdv_rate   = _num(re.sub(r'[%\s]', '', kdv_rate_s))
                    if not amount and unit_price:
                        amount = round(qty * unit_price, 2)
                    if not kdv_amt and amount and kdv_rate:
                        kdv_amt = round(amount * kdv_rate / 100, 2)
                    lines.append({
                        'name': name_val, 'qty': qty, 'unit': unit,
                        'unit_price': unit_price, 'amount': amount,
                        'kdv_rate': kdv_rate, 'kdv_amount': kdv_amt,
                    })

        # ════════════════════════════════════════════════════════════════════
        #  ŞABLON B — Modern (class=lineitems, data-role=*)
        # ════════════════════════════════════════════════════════════════════
        if is_modern or (not is_efinans and not lines):
            # ── Fatura No / Tarih ────────────────────────────────────────────
            if not inv_id:
                el = soup.find(attrs={'data-role': 'invoice-number'})
                if el:
                    m = re.search(r'[A-Z]{2,5}\d{13,}', el.get_text())
                    if m:
                        inv_id = m.group(0)

            if not inv_date:
                el = soup.find(attrs={'data-role': 'invoice-date'})
                if el:
                    m = re.search(r'\d{2}[.\-]\d{2}[.\-]\d{4}', el.get_text())
                    if m:
                        inv_date = m.group(0)

            # ── Satıcı / Müşteri — data-role ────────────────────────────────
            name_els = soup.find_all(attrs={'data-role': 'company-name'})
            if not sup_name and name_els:
                sup_name = name_els[0].get_text(strip=True)
            if not cus_name and len(name_els) > 1:
                cus_name = name_els[1].get_text(strip=True)

            tax_els = soup.find_all(attrs={'data-role': 'company-tax-info'})
            if not sup_vkn and tax_els:
                m = re.search(r'\d{10,11}', tax_els[0].get_text())
                if m:
                    sup_vkn = _vkn_fmt(m.group(0))
            if not cus_vkn and len(tax_els) > 1:
                m = re.search(r'\d{10,11}', tax_els[1].get_text())
                if m:
                    cus_vkn = _vkn_fmt(m.group(0))

            # ── Toplamlar — class="totals" ───────────────────────────────────
            totals_tbl = soup.find(class_='totals')
            if totals_tbl:
                _tpl_found = True
                _kdv_set = False
                for row in totals_tbl.find_all('tr'):
                    cells = [c.get_text(strip=True) for c in row.find_all(['td', 'th'])]
                    if len(cells) < 2:
                        continue
                    lbl = cells[0].lower()
                    val_str = next((c for c in reversed(cells[1:])
                                    if re.search(r'\d', c)), '')
                    if not matrah and 'mal hizmet toplam' in lbl:
                        matrah = _num(val_str)
                    elif not _kdv_set and 'hesaplanan kdv' in lbl:
                        kdv = _num(val_str)
                        _kdv_set = True
                    elif not toplam and ('vergiler dahil' in lbl or 'ödenecek' in lbl):
                        toplam = _num(val_str)

            # ── Kalemler — class="lineitems" ─────────────────────────────────
            # Kolon düzeni: No | Ad | Açıklama | Miktar | Birim Fiyat | KDV% | Toplam
            if not lines:
                li_tbl = soup.find(class_='lineitems')
                if li_tbl:
                    for row in li_tbl.find_all('tr')[1:]:
                        cells = [c.get_text(separator=' ', strip=True)
                                 for c in row.find_all('td')]
                        if len(cells) < 4:
                            continue
                        name_val = cells[1] if len(cells) > 1 else ''
                        if not name_val:
                            continue
                        qty_raw    = cells[3] if len(cells) > 3 else '1'
                        unit_price = _num(cells[4]) if len(cells) > 4 else 0.0
                        kdv_rate_s = cells[5] if len(cells) > 5 else '0'
                        amount     = _num(cells[6]) if len(cells) > 6 else 0.0
                        qty_parts  = qty_raw.split()
                        qty        = _num(qty_parts[0]) if qty_parts else 1.0
                        unit       = qty_parts[1] if len(qty_parts) > 1 else 'Adet'
                        kdv_rate   = _num(re.sub(r'[%\s]', '', kdv_rate_s))
                        kdv_amt    = round(amount * kdv_rate / 100, 2)
                        if not amount and unit_price:
                            amount = round(qty * unit_price, 2)
                            kdv_amt = round(amount * kdv_rate / 100, 2)
                        lines.append({
                            'name': name_val, 'qty': qty, 'unit': unit,
                            'unit_price': unit_price, 'amount': amount,
                            'kdv_rate': kdv_rate, 'kdv_amount': kdv_amt,
                        })

        # ════════════════════════════════════════════════════════════════════
        #  ORTAK FALLBACK — metin satırları (hiçbir şablon tutmadıysa)
        # ════════════════════════════════════════════════════════════════════
        plain_text = soup.get_text(separator='\n')
        text_lines = [l.strip() for l in plain_text.splitlines() if l.strip()]

        def _next_val(lines, label):
            for i, ln in enumerate(lines):
                if label.upper() in ln.upper():
                    for j in range(i + 1, min(i + 5, len(lines))):
                        if lines[j].strip():
                            return lines[j].strip()
            return ''

        if not inv_id:
            for ln in text_lines:
                m = re.search(r'\b([A-Z]{2,5}\d{13,})\b', ln)
                if m:
                    inv_id = m.group(1)
                    break

        if not inv_date:
            for ln in text_lines:
                m = re.search(r'\b(\d{2}[.\-]\d{2}[.\-]\d{4})\b', ln)
                if m:
                    inv_date = m.group(1)
                    break

        if not sup_name:
            el = soup.find(class_='partyName')
            if el:
                sup_name = el.get_text(strip=True)

        # Metin fallback — SAYIN öncesi satırlarda şirket adı ara
        if not sup_name:
            sayin_ti = next((i for i, l in enumerate(text_lines)
                             if l.upper().strip() == 'SAYIN'), -1)
            search_lines = text_lines[:sayin_ti] if sayin_ti > 0 else text_lines[:20]
            _skip_html = re.compile(
                r'^(Merkez|Adres|Tel|Faks|Posta|e-Posta|Web|VKN|TCKN|Vergi|Mersis|Ticaret|e-FATURA|ETTN|www\.)',
                re.IGNORECASE
            )
            for ln in search_lines:
                if _skip_html.match(ln) or not ln or len(ln) < 4:
                    continue
                if _is_company_name(ln) or len(ln) > 8:
                    sup_name = ln
                    break

        if not cus_name:
            sayin_i = next((i for i, l in enumerate(text_lines)
                            if l.upper().strip() == 'SAYIN'), -1)
            if sayin_i >= 0 and sayin_i + 1 < len(text_lines):
                cus_name = text_lines[sayin_i + 1]

        # VKN fallback: metindeki ilk iki farklı 10-11 haneli sayı
        if not sup_vkn or not cus_vkn:
            seen_vkns = []
            for v in re.findall(r'\b(\d{10,11})\b', plain_text):
                fv = _vkn_fmt(v)
                if fv not in seen_vkns:
                    seen_vkns.append(fv)
            if not sup_vkn and seen_vkns:
                sup_vkn = seen_vkns[0]
            if not cus_vkn:
                for fv in seen_vkns:
                    if fv != sup_vkn:
                        cus_vkn = fv
                        break

        # ── Metin fallback — sadece toplamlar tablosu bulunamadıysa ────────
        # (toplamlar bulunduysa KDV=0 meşru olabilir, üzerine yazma!)
        _tpl_found = _tpl_found if '_tpl_found' in dir() else False
        if not _tpl_found:
            if not matrah:
                for lbl_key in ('Mal Hizmet Toplam', 'Toplam Tutar'):
                    raw = _next_val(text_lines, lbl_key)
                    if raw:
                        v = _num(re.sub(r'[^\d.,]', '', raw.split()[0]))
                        if v:
                            matrah = v
                            break
            if not kdv:
                raw = _next_val(text_lines, 'Hesaplanan KDV') or _next_val(text_lines, 'KDV Tutarı')
                if raw:
                    v = _num(re.sub(r'[^\d.,]', '', raw.split()[0]))
                    # 351 gibi yanlış değerleri filtrele: KDV > matrah ise geçersiz
                    if v and (not matrah or v <= matrah):
                        kdv = v
            if not toplam:
                for lbl_key in ('Vergiler Dahil', 'Ödenecek Tutar', 'Genel Toplam'):
                    raw = _next_val(text_lines, lbl_key)
                    if raw:
                        v = _num(re.sub(r'[^\d.,]', '', raw.split()[0]))
                        if v:
                            toplam = v
                            break

        # Toplam hâlâ yoksa matrah + kdv'den hesapla
        if not toplam and matrah:
            toplam = round(matrah + kdv, 2)

        # Kalem bulunamadıysa html.parser ile yeniden dene (lxml bazı tabloları birleştirir)
        if not lines:
            try:
                soup2 = BeautifulSoup(html, 'html.parser')
                for tbl2 in soup2.find_all('table'):
                    rows2 = tbl2.find_all('tr')
                    if len(rows2) < 2:
                        continue
                    # Başlık satırı bul
                    hdr2 = None
                    hdr2_idx = 0
                    for ri2, row2 in enumerate(rows2[:3]):
                        hdrs2 = [c.get_text(strip=True).lower() for c in row2.find_all(['td','th'])]
                        hdr2_str = ' '.join(hdrs2)
                        if any(k in hdr2_str for k in ('malzeme', 'mal hizmet', 'miktar', 'birim fiyat')):
                            hdr2 = hdrs2
                            hdr2_idx = ri2
                            break
                    if hdr2 is None:
                        continue
                    # Kolon haritası
                    col2 = {}
                    for ci2, h2 in enumerate(hdr2):
                        if any(k in h2 for k in ('mal hizmet', 'malzeme', 'ürün adı', 'hizmet adı')) and 'name' not in col2:
                            col2['name'] = ci2
                        elif 'açıklama' in h2 and 'name' not in col2:
                            col2['name'] = ci2
                        elif 'miktar' in h2 and 'qty' not in col2:
                            col2['qty'] = ci2
                        elif 'birim' in h2 and 'fiyat' in h2 and 'unit_price' not in col2:
                            col2['unit_price'] = ci2
                        elif 'kdv' in h2 and ('oran' in h2 or '%' in h2) and 'kdv_rate' not in col2:
                            col2['kdv_rate'] = ci2
                        elif 'kdv' in h2 and 'tutar' in h2 and 'kdv_amount' not in col2:
                            col2['kdv_amount'] = ci2
                        elif ('tutar' in h2 or 'toplam' in h2) and 'kdv' not in h2 and 'amount' not in col2:
                            col2['amount'] = ci2
                    # "açıklama" sütununu name olarak tercih et
                    for ci2, h2 in enumerate(hdr2):
                        if 'açıklama' in h2 and 'name' in col2:
                            col2['name'] = ci2
                            break
                    if 'name' not in col2:
                        continue
                    for row2 in rows2[hdr2_idx + 1:]:
                        cells2 = [c.get_text(separator=' ', strip=True) for c in row2.find_all(['td','th'])]
                        if len(cells2) < 2:
                            continue
                        def _gc2(key, default=''):
                            idx2 = col2.get(key)
                            return cells2[idx2] if (idx2 is not None and idx2 < len(cells2)) else default
                        name2 = _gc2('name')
                        if not name2 or re.match(r'^[\d\s%,.\-]*$', name2):
                            continue
                        qty_raw2  = _gc2('qty', '1')
                        qty_parts2 = qty_raw2.split()
                        qty2  = _num(qty_parts2[0]) if qty_parts2 else 1.0
                        unit2 = next((p for p in qty_parts2[1:] if re.match(r'^[A-Za-zçÇşŞğĞüÜöÖıİ]+$', p)), 'Adet')
                        uprice2  = _num(re.sub(r'[^\d.,]', '', _gc2('unit_price', '0')))
                        kdvr2    = _num(re.sub(r'[%\s]', '', _gc2('kdv_rate', '0')))
                        kdvamt2  = _num(re.sub(r'[^\d.,]', '', _gc2('kdv_amount', '0')))
                        amount2  = _num(re.sub(r'[^\d.,]', '', _gc2('amount', '0')))
                        if not amount2 and uprice2:
                            amount2 = round(qty2 * uprice2, 2)
                        lines.append({
                            'name': name2, 'qty': qty2, 'unit': unit2,
                            'unit_price': uprice2, 'amount': amount2,
                            'kdv_rate': kdvr2, 'kdv_amount': kdvamt2,
                        })
                    if lines:
                        break
            except Exception:
                pass

        date_obj = _parse_date(inv_date)

        return {
            'ok': True, 'fmt': 'HTML',
            'inv_id': inv_id, 'inv_date': inv_date, 'date_obj': date_obj,
            'inv_type': inv_type, 'currency': currency,
            'sup_name': sup_name, 'sup_vkn': sup_vkn,
            'cus_name': cus_name, 'cus_vkn': cus_vkn,
            'matrah': matrah, 'kdv': kdv, 'tevkifat': tevkifat,
            'toplam': toplam, 'lines': lines,
        }
    except Exception as e:
        return {'ok': False, 'error': str(e)}


def parse_invoice_pdf(path):
    """GIB standart e-fatura PDF → parse_invoice ile aynı dict döner (Format A/B/C/D)"""
    try:
        import pdfplumber
    except ImportError:
        return {'ok': False, 'error': 'pdfplumber kurulu değil (pip install pdfplumber)'}
    try:
        with pdfplumber.open(path) as pdf:
            full_text = '\n'.join((p.extract_text() or '') for p in pdf.pages)
            all_tables = []
            for p in pdf.pages:
                all_tables.extend(p.extract_tables() or [])

        def _cv(row, idx, default=''):
            if row and idx < len(row) and row[idx] is not None:
                return str(row[idx]).strip()
            return default

        text_lines = [l.strip() for l in full_text.splitlines() if l.strip()]

        # ── Meta: Fatura No / Tarih / Tip ──────────────────────────────────
        # Her tablodan 2-sütunlu anahtar-değer satırlarını topla
        meta = {}
        for tbl in all_tables:
            for row in tbl:
                if not row or len(row) < 2:
                    continue
                k = str(row[0] or '').strip().rstrip(':').lower()
                v = str(row[1] or '').strip()
                if k and v and len(k) < 60:
                    meta[k] = v

        inv_id = (meta.get('fatura no') or meta.get('invoice number') or
                  meta.get('e-fatura no') or '')
        raw_date = meta.get('fatura tarihi') or meta.get('invoice date') or ''

        # Metin fallback
        if not inv_id:
            # Seri kodu: 1-5 alfanümerik (en az 1 büyük harf), ardından 13+ rakam
            # Örnekler: SKA2025000000579, A602025000265737, IC12025000000001
            for ln in text_lines:
                m = _RE_INV_ID.search(ln)
                if m:
                    inv_id = m.group(1)
                    break
        if not raw_date:
            for ln in text_lines:
                m = _RE_DATE_FIND.search(ln)
                if m:
                    raw_date = m.group(1)
                    break

        inv_date = ''
        if raw_date:
            # "21- 02- 2025" veya "21.02.2025" → YYYY-MM-DD
            raw_date = re.sub(r'\s+', '', raw_date)
            m2 = _RE_DATE_PARSE.match(raw_date)
            if m2:
                inv_date = f'{m2.group(3)}-{m2.group(2)}-{m2.group(1)}'
            else:
                inv_date = raw_date
        date_obj = _parse_date(inv_date)
        inv_type = meta.get('fatura tipi') or meta.get('senaryo') or 'SATIS'
        currency = 'TRY'

        # ── Satıcı adı + VKN ────────────────────────────────────────────────
        sayin_idx = full_text.upper().find('SAYIN')
        sup_block = full_text[:sayin_idx].strip() if sayin_idx > 0 else full_text[:600]
        sup_lines = [l.strip() for l in sup_block.splitlines() if l.strip()]

        # Şirket adını bul — çok satırlı unvanları da birleştir
        # Örnek: 'MNG KARGO YURTİÇİ VE YURTDIŞI TAŞIMACILIK' + 'A.Ş.'
        sup_name = ''
        _skip_pat = re.compile(
            r'^(Merkez|Adres|Tel|Faks|Posta|e-Posta|Web|qrcode|VKN|TCKN|e-Fatura|ETTN|www\.|http)'
            r'|^[0-9A-Fa-f]{4,}[-0-9A-Fa-f]*$',  # salt UUID fragmanı satırı
            re.IGNORECASE
        )
        for i, ln in enumerate(sup_lines):
            if _skip_pat.match(ln) or not ln:
                continue
            # Sonraki satır kısa ve şirket son eki mi? (A.Ş., LTD.ŞTİ., vb.)
            candidate = ln
            if i + 1 < len(sup_lines):
                nxt = sup_lines[i + 1]
                if len(nxt) <= 30 and re.match(r'^(A\.Ş|LTD|KOLL|KOM|ORT)', nxt, re.IGNORECASE):
                    candidate = ln + ' ' + nxt
            if _is_company_name(candidate) or len(candidate) > 5:
                # Şirket adına yapışan UUID/hash kısımlarını temizle
                candidate = re.sub(r'\s+[0-9A-Fa-f]{8,}$', '', candidate).strip()
                sup_name = candidate
                break
        if not sup_name and sup_lines:
            sup_name = sup_lines[0]

        # VKN çeşitli etiket formatlarında aranır: V.D., Vergi No, TCKN, VKN
        def _extract_sup_vkn(text):
            for pat in (
                r'V\.D\.[:\s]*(\d{10,11})',             # "ÜSKÜDARV.D.: 9480423762"
                r'Vergi\s*Numaras[ıi]\s*[:\s]\s*(\d{10,11})',  # BIM formatı
                r'TCKN\s*[:\s]\s*(\d{10,11})',          # "TCKN: 11216755660"
                r'\bVKN\s*[:\s]\s*(\d{10,11})',         # "VKN: 6080712084" (VKN/TCKN hariç)
            ):
                ms = re.findall(pat, text, re.IGNORECASE)
                if ms:
                    return _vkn_fmt(ms[-1])
            # Son çare: sup_block'taki ilk 10-11 haneli sayı
            ms = re.findall(r'\b(\d{10,11})\b', text)
            return _vkn_fmt(ms[0]) if ms else ''
        sup_vkn = _extract_sup_vkn(sup_block)

        # ── Müşteri adı + VKN ───────────────────────────────────────────────
        cus_name = ''
        cus_vkn  = ''

        # Tablolarda SAYIN hücresini bul
        for tbl in all_tables:
            for row in tbl:
                for cell in row:
                    cell_str = str(cell or '')
                    if 'SAYIN' not in cell_str.upper():
                        continue
                    cell_lines = [l.strip() for l in cell_str.splitlines() if l.strip()]
                    for ci, ln in enumerate(cell_lines):
                        if ln.upper() == 'SAYIN' and ci + 1 < len(cell_lines):
                            raw_cus = cell_lines[ci + 1]
                            # "Özelleştirme No" veya "TR1.2" gibi çöpü kes
                            raw_cus = re.split(r'Özelleştirme|TR\d+\.\d+|e-Fatura|VKN', raw_cus, flags=re.IGNORECASE)[0]
                            cus_name = raw_cus.strip()
                            break
                    m_vkn = re.search(r'VKN[:\s]+(\d{10,11})', cell_str)
                    if m_vkn:
                        cus_vkn = _vkn_fmt(m_vkn.group(1))
                    if cus_name:
                        break
                if cus_name:
                    break
            if cus_name:
                break

        # Fallback: metin SAYIN sonrası
        if not cus_name and sayin_idx >= 0:
            after_lines = [l.strip() for l in full_text[sayin_idx:].splitlines() if l.strip()]
            if len(after_lines) > 1:
                raw_cus = after_lines[1]
                raw_cus = re.split(r'Özelleştirme|TR\d+\.\d+|e-Fatura|VKN', raw_cus, flags=re.IGNORECASE)[0]
                cus_name = raw_cus.strip()

        if not cus_vkn:
            all_vkns = re.findall(r'VKN[:\s]+(\d{10,11})', full_text)
            for v in all_vkns:
                fv = _vkn_fmt(v)
                if fv != sup_vkn:
                    cus_vkn = fv
                    break

        # ── Toplamlar: Çok-format yaklaşımı ─────────────────────────────────
        matrah   = 0.0
        kdv      = 0.0
        toplam   = 0.0
        tevkifat = 0.0

        TOTAL_KW = {
            'mal hizmet toplam': 'matrah',
            'mal / hizmet toplam': 'matrah',
            'toplam tutar': 'matrah',
            'hesaplanan kdv': 'kdv',
            'vergiler dahil toplam': 'toplam',
            'vergiler dahil': 'toplam',
            'ödenecek tutar': 'toplam',
            'denecek tutar': 'toplam',
            'odenecek': 'toplam',
        }

        def _apply_total(label, value_str):
            nonlocal matrah, kdv, toplam
            label_lc = label.lower().replace('i̇', 'i')
            for kw, field in TOTAL_KW.items():
                if kw in label_lc:
                    # "Hesaplanan KDV Matrahı" KDV değil, matrah bilgisidir — atla
                    if kw == 'hesaplanan kdv' and 'matrah' in label_lc:
                        continue
                    v = _num(value_str)
                    if v > 0:
                        if field == 'matrah' and matrah == 0:
                            matrah = v
                        elif field == 'kdv' and kdv == 0:
                            kdv = v
                        elif field == 'toplam' and toplam == 0:
                            toplam = v
                    return True
            return False

        # Format C: 2-3 sütunlu özet tablo
        # (etiket | değer) veya (boş | etiket | değer) — BIM, A101 gibi
        for tbl in all_tables:
            if not tbl:
                continue
            col_count = max((len(r) for r in tbl if r), default=0)
            if col_count <= 3:
                for row in tbl:
                    if not row:
                        continue
                    # Dolu hücreleri sırayla al
                    non_empty = [(str(c or '').strip()) for c in row
                                 if str(c or '').strip()]
                    if len(non_empty) >= 2:
                        lbl = non_empty[0]
                        val = non_empty[-1]
                        if lbl != val:
                            _apply_total(lbl, val)

        # Format A/B/D: kalem tablosuna gömülü toplam satırları
        # (başlık satırından sonraki satırlarda etiket+değer çiftleri aranır)
        if matrah == 0:
            for tbl in all_tables:
                if not tbl:
                    continue
                # Gerçek başlık satırını bul (ilk 4 satır içinde)
                hdr_idx2 = 0
                for ri, row in enumerate(tbl[:4]):
                    rt = ' '.join(str(c or '') for c in row).lower()
                    if any(kw in rt for kw in ('mal hizmet', 'miktar', 'birim fiyat', 'tutar')):
                        hdr_idx2 = ri
                        break
                else:
                    continue
                ncols = max((len(r) for r in tbl if r), default=0)
                for row in tbl[hdr_idx2 + 1:]:
                    cells = [str(c or '').strip() for c in row]
                    if ncols >= 14:  # Format A
                        lbl_idx = 9
                    elif ncols >= 9:  # Format B
                        lbl_idx = 7
                    elif ncols >= 7:  # Format D
                        lbl_idx = 3
                    else:
                        continue
                    lbl = cells[lbl_idx] if len(cells) > lbl_idx else ''
                    # Etiket sonrası ilk dolu hücre değerdir (cells[-1] yanlış sütun okuyabilir)
                    val = next((c for c in cells[lbl_idx + 1:] if c), '')
                    if lbl:
                        _apply_total(lbl, val)

        # Fallback: tam metin regex — birden fazla format denenir
        if matrah == 0:
            for cpat in _RE_MATRAH_PATS:
                m = cpat.search(full_text)
                if m:
                    matrah = _num(m.group(1))
                    break
        if kdv == 0:
            # Önce tüm "Hesaplanan KDV ... : değer" satırlarını topla (çok oranlı KDV)
            kdv_vals = _RE_KDV_MAIN.findall(full_text)
            if kdv_vals:
                kdv = sum(_num(v) for v in kdv_vals)
            else:
                for cpat in _RE_KDV_PATS:
                    m = cpat.search(full_text)
                    if m:
                        kdv = _num(m.group(1))
                        break
            # Elektrik faturası: "KDV (Matrah X) 7.616,94"
            if kdv == 0:
                m = _RE_KDV_ELEC.search(full_text)
                if m:
                    kdv = _num(m.group(1))
            # Perakende: "KDV(%20.00): 16,50" + "KDV(%1.00): 1,35" toplamı
            if kdv == 0:
                prc_vals = _RE_KDV_PRC.findall(full_text)
                if prc_vals:
                    kdv = sum(_num(v) for v in prc_vals)
        if toplam == 0:
            for cpat in _RE_TOPLAM_PATS:
                m = cpat.search(full_text)
                if m:
                    toplam = _num(m.group(1))
                    break

        # ── Kalem satırları — başlık satırından dinamik kolon tespiti ─────────
        lines = []
        for tbl in all_tables:
            if not tbl or len(tbl) < 2:
                continue
            # Tablonun ilk 4 satırında gerçek başlık satırını ara
            # (bazı PDF'lerde row[0] şirket adı, row[1] gerçek başlık)
            hdr_row = None
            hdr_row_idx = 0
            for ri, row in enumerate(tbl[:4]):
                row_text = ' '.join(str(c or '') for c in row).lower()
                if any(kw in row_text for kw in
                       ('mal hizmet', 'miktar', 'birim fiyat', 'ürün', 'hizmet adı',
                        'malzeme', 'açıklama/description')):
                    hdr_row = row
                    hdr_row_idx = ri
                    break
            if hdr_row is None:
                continue

            # Başlık satırından kolon haritasını çıkar
            col = {}
            for ci, cell in enumerate(hdr_row):
                h = str(cell or '').lower().strip()
                if not h:
                    continue
                if any(k in h for k in ('mal hizmet', 'ürün adı', 'hizmet adı', 'ürün / hizmet')):
                    col.setdefault('name', ci)
                elif 'açıklama' in h and 'name' not in col:
                    col.setdefault('name', ci)
                elif 'miktar' in h:
                    col.setdefault('qty', ci)
                elif 'birim' in h and 'fiyat' in h:
                    col.setdefault('unit_price', ci)
                elif 'kdv' in h and ('oran' in h or '%' in h):
                    col.setdefault('kdv_rate', ci)
                elif 'kdv' in h and ('tutar' in h or 'mikt' in h):
                    col.setdefault('kdv_amount', ci)
                elif ('tutar' in h or 'toplam' in h) and 'kdv' not in h:
                    col.setdefault('amount', ci)

            # Kolon haritası bulunamadıysa ncols ile tahmin et (eski davranış)
            if 'name' not in col:
                ncols = max((len(r) for r in tbl if r), default=0)
                if ncols >= 14:
                    col = {'name': 3, 'qty': 6, 'unit_price': 7,
                           'kdv_rate': 11, 'kdv_amount': 12, 'amount': 15}
                elif ncols >= 8:
                    col = {'name': 2, 'qty': 3, 'unit_price': 4,
                           'kdv_rate': 5, 'kdv_amount': 6, 'amount': 7}
                else:
                    continue

            for row in tbl[hdr_row_idx + 1:]:
                cells = [str(c or '').strip() for c in row]
                if not any(cells):
                    continue
                # İlk hücre sıra numarası veya boş olabilir — ad sütunu 0 değilse kontrol et
                first = cells[0] if cells else ''
                name_col = col.get('name', 1)
                if name_col > 0 and first and not re.match(r'^\d+$', first.strip()):
                    continue

                def _gc(key, default=''):
                    idx = col.get(key)
                    return cells[idx] if (idx is not None and idx < len(cells)) else default

                name_val   = _gc('name')
                qty_raw    = _gc('qty', '1')
                unit_price = _num(_gc('unit_price', '0'))
                kdv_rate_s = _gc('kdv_rate', '0')
                kdv_amount = _num(_gc('kdv_amount', '0'))
                amount     = _num(_gc('amount', '0'))

                if not name_val:
                    continue
                # Toplam satırlarını atla (kalem değil)
                _nv_up = name_val.upper()
                if any(k in _nv_up for k in ('TOPLAM', 'MATRAH', 'GENEL', 'ÖDENECEK', 'YALNIZ')):
                    continue

                qty_parts = qty_raw.split()
                qty  = _num(qty_parts[0]) if qty_parts else 1.0
                unit = qty_parts[1] if len(qty_parts) > 1 else 'Adet'
                kdv_rate = _num(re.sub(r'[%\s]', '', kdv_rate_s))

                if not amount and unit_price:
                    amount = round(qty * unit_price, 2)
                if not kdv_amount and amount and kdv_rate:
                    kdv_amount = round(amount * kdv_rate / 100, 2)

                lines.append({
                    'name': name_val, 'qty': qty, 'unit': unit,
                    'unit_price': unit_price, 'amount': amount,
                    'kdv_rate': kdv_rate, 'kdv_amount': kdv_amount,
                })
            if lines:
                break  # İlk kalem tablosunu bulduktan sonra dur

        # Tablo yoksa metin satırlarından kalem parse et (A101 / perakende formatı)
        # Başlık satırını bul: "ÜRÜN AÇIKLAMASI ADET FİYAT TUTAR" gibi
        if not lines:
            hdr_li = -1
            for idx_li, ln in enumerate(text_lines):
                ln_up = ln.upper()
                if any(k in ln_up for k in ('ÜRÜN AÇIKLAMASI', 'MAL HIZMET', 'ÜRÜN ADI')):
                    if any(k in ln_up for k in ('ADET', 'MİKTAR', 'FİYAT')):
                        hdr_li = idx_li
                        break
            if hdr_li >= 0:
                stop_kw = ('ARA TOPLAM', 'TOPLAM', 'KDV', 'YALNIZ', 'ETTN', 'SAP BELGE')
                for ln in text_lines[hdr_li + 1:]:
                    if any(k in ln.upper() for k in stop_kw):
                        break
                    # "ÜRÜN ADI QTY BIRIM_FIYAT TOPLAM" — son 3 token sayısal
                    parts = ln.split()
                    if len(parts) >= 4:
                        try:
                            amount  = _num(parts[-1])
                            uprice  = _num(parts[-2])
                            qty_s   = parts[-3]
                            qty_v   = _num(qty_s)
                            if amount > 0 and qty_v > 0:
                                name_val = ' '.join(parts[:-3])
                                lines.append({
                                    'name': name_val, 'qty': qty_v, 'unit': 'Adet',
                                    'unit_price': uprice, 'amount': amount,
                                    'kdv_rate': 0, 'kdv_amount': 0,
                                })
                        except Exception:
                            pass

        # Kalem hâlâ boşsa ve elektrik/su/gaz faturasıysa sabit açıklama ekle
        if not lines:
            _sup_up = sup_name.upper()
            if any(k in _sup_up for k in ('ELEKTRİK', 'ELEKTRIK', 'DOGALGAZ', 'DOĞALGAZ', 'SU ', 'TEDAŞ', 'BEDAŞ', 'BAŞKENT')):
                lines.append({
                    'name': 'Elektrik Faturası', 'qty': 1.0, 'unit': 'Adet',
                    'unit_price': matrah, 'amount': matrah,
                    'kdv_rate': 0, 'kdv_amount': kdv,
                })
            elif any(k in full_text.upper() for k in ('ELEKTRİK TÜKETİM', 'KWH', 'ABONE NO', 'TESİSAT NO')):
                lines.append({
                    'name': 'Elektrik Faturası', 'qty': 1.0, 'unit': 'Adet',
                    'unit_price': matrah, 'amount': matrah,
                    'kdv_rate': 0, 'kdv_amount': kdv,
                })

        return {
            'ok': True, 'fmt': 'PDF',
            'inv_id': inv_id, 'inv_date': inv_date, 'date_obj': date_obj,
            'inv_type': inv_type, 'currency': currency,
            'sup_name': sup_name, 'sup_vkn': sup_vkn,
            'cus_name': cus_name, 'cus_vkn': cus_vkn,
            'matrah': matrah, 'kdv': kdv, 'tevkifat': tevkifat,
            'toplam': toplam, 'lines': lines,
        }
    except Exception as e:
        return {'ok': False, 'error': str(e)}


# ═══════════════════════════════════════════════════════════════════════════════
#  XML PARSE
# ═══════════════════════════════════════════════════════════════════════════════

def parse_invoice(src):
    if not isinstance(src, tuple):
        ext = os.path.splitext(src)[1].lower()
        if ext == '.html':
            return parse_invoice_html(src)
        if ext == '.pdf':
            return parse_invoice_pdf(src)
    try:
        if isinstance(src, tuple):
            zpath, name = src
            with zipfile.ZipFile(zpath) as zf:
                with zf.open(name) as f:
                    root = ET.parse(f).getroot()
        else:
            root = ET.parse(src).getroot()

        ns = NS
        inv_id   = _txt(root, './/cbc:ID', ns)
        inv_date = _txt(root, './/cbc:IssueDate', ns)
        inv_type = _txt(root, './/cbc:InvoiceTypeCode', ns, 'SATIS')
        currency = _txt(root, './/cbc:DocumentCurrencyCode', ns, 'TRY')
        date_obj = _parse_date(inv_date)

        # Satıcı
        sup = root.find('.//cac:AccountingSupplierParty/cac:Party', ns)
        sup_name = ''
        if sup is not None:
            sup_name = (
                _txt(sup, 'cac:PartyName/cbc:Name', ns) or
                _txt(sup, 'cac:PartyLegalEntity/cbc:RegistrationName', ns) or
                # Gerçek kişi (şahıs) — FirstName + FamilyName
                ((_txt(sup, 'cac:Person/cbc:FirstName', ns) + ' ' +
                  _txt(sup, 'cac:Person/cbc:FamilyName', ns)).strip()) or
                # Son çare: Contact/Name
                _txt(sup, 'cac:Contact/cbc:Name', ns)
            )
        sup_vkn = ''
        if sup is not None:
            sup_vkn = (_txt(sup, 'cac:PartyTaxScheme/cbc:CompanyID', ns) or
                       _txt(sup, 'cac:PartyIdentification/cbc:ID', ns))

        # Müşteri
        cus = root.find('.//cac:AccountingCustomerParty/cac:Party', ns)
        cus_name = ''
        if cus is not None:
            cus_name = (
                _txt(cus, 'cac:PartyName/cbc:Name', ns) or
                _txt(cus, 'cac:PartyLegalEntity/cbc:RegistrationName', ns) or
                ((_txt(cus, 'cac:Person/cbc:FirstName', ns) + ' ' +
                  _txt(cus, 'cac:Person/cbc:FamilyName', ns)).strip()) or
                _txt(cus, 'cac:Contact/cbc:Name', ns)
            )
        cus_vkn = ''
        if cus is not None:
            cus_vkn = (_txt(cus, 'cac:PartyTaxScheme/cbc:CompanyID', ns) or
                       _txt(cus, 'cac:PartyIdentification/cbc:ID', ns))

        # Hesaplanan toplam KDV
        kdv = _float(_txt(root, './/cac:TaxTotal/cbc:TaxAmount', ns))

        # Tevkifat
        tevkifat = 0.0
        for wh in root.findall('.//cac:WithholdingTaxTotal', ns):
            for sub in wh.findall('cac:TaxSubtotal', ns):
                tevkifat += _float(_txt(sub, 'cbc:TaxAmount', ns))

        # Matrah
        matrah = (_float(_txt(root, './/cac:LegalMonetaryTotal/cbc:TaxExclusiveAmount', ns)) or
                  _float(_txt(root, './/cac:LegalMonetaryTotal/cbc:LineExtensionAmount', ns)))

        # Genel toplam
        toplam = (_float(_txt(root, './/cac:LegalMonetaryTotal/cbc:TaxInclusiveAmount', ns)) or
                  _float(_txt(root, './/cac:LegalMonetaryTotal/cbc:PayableAmount', ns)))

        # Fatura kalemleri
        lines = []
        for line in root.findall('.//cac:InvoiceLine', ns):
            qty_el   = line.find('cbc:InvoicedQuantity', ns)
            qty      = _float(qty_el.text) if (qty_el is not None and qty_el.text) else 1.0
            unit     = _unit_label(qty_el.get('unitCode', 'C62') if qty_el is not None else 'C62')
            name_val = (_txt(line, 'cac:Item/cbc:Name', ns) or
                        _txt(line, 'cac:Item/cbc:Description', ns))
            u_price  = _float(_txt(line, 'cac:Price/cbc:PriceAmount', ns))
            l_amt    = _float(_txt(line, 'cbc:LineExtensionAmount', ns))
            l_kdv_r  = _txt(line, './/cac:TaxTotal/cac:TaxSubtotal/cac:TaxCategory/cbc:Percent', ns)
            l_kdv_a  = _float(_txt(line, './/cac:TaxTotal/cbc:TaxAmount', ns))
            lines.append({
                'name': name_val, 'qty': qty, 'unit': unit,
                'unit_price': u_price, 'amount': l_amt,
                'kdv_rate': l_kdv_r, 'kdv_amount': l_kdv_a,
            })

        return {
            'ok': True, 'src': src, 'fmt': 'XML',
            'inv_id': inv_id, 'inv_date': inv_date,
            'date_obj': date_obj, 'inv_type': inv_type,
            'currency': currency,
            'sup_name': sup_name, 'sup_vkn': sup_vkn,
            'cus_name': cus_name, 'cus_vkn': cus_vkn,
            'matrah': matrah, 'kdv': kdv,
            'tevkifat': tevkifat, 'toplam': toplam,
            'lines': lines,
        }

    except Exception as e:
        return {'ok': False, 'src': src,
                'fname': _display_name(src), 'err': str(e)}


# ═══════════════════════════════════════════════════════════════════════════════
#  EXCEL YARDIMCILARI  (xlsxwriter)
# ═══════════════════════════════════════════════════════════════════════════════

def _xls_color(hex6):
    """'1E3A5F' → '#1E3A5F'"""
    return f'#{hex6}'

def _make_formats(wb):
    """Workbook için tüm format nesnelerini bir kez oluştur, dict döner."""
    c = _xls_color
    brd = {'border': 1, 'border_color': c(CLR_BORDER)}
    brd_w = {'border': 1, 'border_color': '#FFFFFF'}

    def f(**kw):
        return wb.add_format(kw)

    return {
        # Başlık
        'title': f(bold=True, font_size=13, font_color='#FFFFFF',
                   align='center', valign='vcenter',
                   bg_color=c(CLR_TITLE_BG)),
        # Tarih satırı
        'date_row': f(italic=True, font_size=9, font_color='#666666',
                      align='center', valign='vcenter'),
        # Alış header
        'hdr_alis': f(bold=True, font_size=9, font_color='#FFFFFF',
                      align='center', valign='vcenter', text_wrap=True,
                      bg_color=c(CLR_HDR_BG), **brd_w),
        # Alış kalem header
        'hdr_alis2': f(bold=True, font_size=9, font_color='#FFFFFF',
                       align='center', valign='vcenter', text_wrap=True,
                       bg_color=c(CLR_HDR2_BG), **brd_w),
        # Satış header
        'hdr_satis': f(bold=True, font_size=9, font_color='#FFFFFF',
                       align='center', valign='vcenter', text_wrap=True,
                       bg_color=c(CLR_SAT_BG), **brd_w),
        # Veri — metin sola
        'data_left': f(font_size=9, align='left', valign='vcenter', **brd),
        'data_left_alt': f(font_size=9, align='left', valign='vcenter',
                           bg_color=c(CLR_ALT_BG), **brd),
        'data_left_sat': f(font_size=9, align='left', valign='vcenter', **brd),
        'data_left_sat_alt': f(font_size=9, align='left', valign='vcenter',
                               bg_color=c(CLR_SAT_ALT), **brd),
        # Veri — metin orta
        'data_center': f(font_size=9, align='center', valign='vcenter', **brd),
        'data_center_alt': f(font_size=9, align='center', valign='vcenter',
                             bg_color=c(CLR_ALT_BG), **brd),
        'data_center_sat': f(font_size=9, align='center', valign='vcenter', **brd),
        'data_center_sat_alt': f(font_size=9, align='center', valign='vcenter',
                                 bg_color=c(CLR_SAT_ALT), **brd),
        # Veri — sayı
        'data_num': f(font_size=9, align='right', valign='vcenter',
                      num_format='#,##0.00', **brd),
        'data_num_alt': f(font_size=9, align='right', valign='vcenter',
                          num_format='#,##0.00', bg_color=c(CLR_ALT_BG), **brd),
        'data_num_sat': f(font_size=9, align='right', valign='vcenter',
                          num_format='#,##0.00', **brd),
        'data_num_sat_alt': f(font_size=9, align='right', valign='vcenter',
                              num_format='#,##0.00', bg_color=c(CLR_SAT_ALT), **brd),
        # Veri — yüzde
        'data_pct': f(font_size=9, align='center', valign='vcenter',
                      num_format='0"%"', **brd),
        'data_pct_alt': f(font_size=9, align='center', valign='vcenter',
                          num_format='0"%"', bg_color=c(CLR_SAT_ALT), **brd),
        # Veri — tarih
        'data_date': f(font_size=9, align='center', valign='vcenter',
                       num_format='DD.MM.YYYY', **brd),
        'data_date_alt': f(font_size=9, align='center', valign='vcenter',
                           num_format='DD.MM.YYYY', bg_color=c(CLR_ALT_BG), **brd),
        'data_date_sat': f(font_size=9, align='center', valign='vcenter',
                           num_format='DD.MM.YYYY', **brd),
        'data_date_sat_alt': f(font_size=9, align='center', valign='vcenter',
                               num_format='DD.MM.YYYY', bg_color=c(CLR_SAT_ALT), **brd),
        # Toplam satırı
        'total_lbl': f(bold=True, font_size=10, font_color='#FFFFFF',
                       align='center', valign='vcenter',
                       bg_color=c(CLR_TOTAL_BG), **brd_w),
        'total_num': f(bold=True, font_size=10, font_color='#FFFFFF',
                       align='right', valign='vcenter',
                       num_format='#,##0.00',
                       bg_color=c(CLR_TOTAL_BG), **brd_w),
        'total_empty': f(bold=True, font_size=10, font_color='#FFFFFF',
                         bg_color=c(CLR_TOTAL_BG), **brd_w),
        # Toplam satırı — satış yeşil
        'total_lbl_sat': f(bold=True, font_size=10, font_color='#FFFFFF',
                           align='center', valign='vcenter',
                           bg_color=c(CLR_SAT_BG), **brd_w),
        'total_num_sat': f(bold=True, font_size=10, font_color='#FFFFFF',
                           align='right', valign='vcenter',
                           num_format='#,##0.00',
                           bg_color=c(CLR_SAT_BG), **brd_w),
        'total_empty_sat': f(bold=True, font_size=10, font_color='#FFFFFF',
                             bg_color=c(CLR_SAT_BG), **brd_w),
        # Metin olarak saklanan sayı (VKN vb.)
        'data_text': f(font_size=9, align='left', valign='vcenter',
                       num_format='@', **brd),
        'data_text_alt': f(font_size=9, align='left', valign='vcenter',
                           num_format='@', bg_color=c(CLR_ALT_BG), **brd),
        'data_text_sat': f(font_size=9, align='left', valign='vcenter',
                           num_format='@', **brd),
        'data_text_sat_alt': f(font_size=9, align='left', valign='vcenter',
                               num_format='@', bg_color=c(CLR_SAT_ALT), **brd),
    }


def _write_sheet_xls(ws, wb_fmts, headers, data_rows,
                     hdr_fmt_key, title_text, title_bg,
                     numeric_cols, text_cols, date_cols, pct_cols=None,
                     flavor='alis'):
    """
    xlsxwriter ile sayfa yazar.
    flavor: 'alis' veya 'satis' — renk setini belirler
    numeric_cols / text_cols / date_cols / pct_cols: 0-tabanlı sütun indeksleri
    (A=0 dahil, yani B=1 başlar)
    """
    is_sat = (flavor == 'satis')
    sfx    = '_sat' if is_sat else ''

    NCOLS    = len(headers)
    last_col = NCOLS      # 0-tabanlı: A=0, B=1 … son=NCOLS

    # ── Satır yükseklikleri
    ws.set_row(0, 24)   # başlık
    ws.set_row(1, 16)   # tarih
    ws.set_row(2, 6)    # boşluk
    ws.set_row(3, 40)   # header

    # ── Sütun genişlikleri  (A=0 → 2 karakter dar)
    ws.set_column(0, 0, 2)
    for ci, (_, w) in enumerate(headers):
        ws.set_column(ci + 1, ci + 1, w)

    # ── Başlık satırı (row 0, B..son birleşik)
    ws.merge_range(0, 1, 0, last_col,
                   title_text,
                   wb_fmts['title'])

    # ── Tarih satırı (row 1)
    ts = datetime.now().strftime('%d.%m.%Y %H:%M')
    ws.merge_range(1, 1, 1, last_col,
                   f'Oluşturma Tarihi: {ts}',
                   wb_fmts['date_row'])

    # row 2 boş — yükseklik zaten set

    # ── Header satırı (row 3)
    hdr_fmt = wb_fmts[hdr_fmt_key]
    for ci, (hdr_txt, _) in enumerate(headers):
        ws.write(3, ci + 1, hdr_txt, hdr_fmt)

    # ── Veri satırları (row 4'ten başlar)
    totals = defaultdict(float)

    for row_idx, row_data in enumerate(data_rows):
        r      = row_idx + 4
        alt    = (row_idx % 2 == 1)
        sfx_a  = sfx + ('_alt' if alt else '')

        ws.set_row(r, 16)
        row_data[0] = row_idx + 1  # Sıra No

        for ci, value in enumerate(row_data):
            col = ci + 1  # B=1

            if ci in date_cols:
                fmt = wb_fmts[f'data_date{sfx_a}']
                # xlsxwriter datetime için write_datetime kullan
                if isinstance(value, datetime):
                    ws.write_datetime(r, col, value, fmt)
                else:
                    ws.write(r, col, value or '', fmt)

            elif ci in text_cols:
                fmt = wb_fmts[f'data_text{sfx_a}']
                ws.write_string(r, col, str(value) if value is not None else '', fmt)

            elif ci in numeric_cols:
                v = _float(value)
                fmt = wb_fmts[f'data_num{sfx_a}']
                ws.write_number(r, col, v, fmt)
                totals[ci] += v

            elif pct_cols and ci in pct_cols:
                fmt = wb_fmts[f'data_pct{"_alt" if alt else ""}']
                ws.write_number(r, col, _float(value), fmt)

            else:
                fmt = wb_fmts[f'data_left{sfx_a}']
                ws.write(r, col, value if value is not None else '', fmt)

    # ── Toplam satırı
    total_row = len(data_rows) + 4
    ws.set_row(total_row, 20)

    lbl_key   = f'total_lbl{sfx}'
    num_key   = f'total_num{sfx}'
    empty_key = f'total_empty{sfx}'

    # B-E birleşik "TOPLAM" etiketi (col 1..4, yani B=1..E=4)
    ws.merge_range(total_row, 1, total_row, 4, 'TOPLAM', wb_fmts[lbl_key])

    # Kalan sütunlar (row_data index 4'ten sona kadar)
    for rd_ci in range(4, NCOLS):
        col = rd_ci + 1   # xlsxwriter column (B=1)
        if rd_ci in totals:
            ws.write_number(total_row, col, round(totals[rd_ci], 2), wb_fmts[num_key])
        else:
            ws.write(total_row, col, '', wb_fmts[empty_key])

    # ── Filtre (header satırı)
    ws.autofilter(3, 1, 3 + len(data_rows), last_col)

    # ── Freeze panes — header sabit kalsın
    ws.freeze_panes(4, 0)


# ═══════════════════════════════════════════════════════════════════════════════
#  İNDİRİLECEK KDV LİSTESİ
# ═══════════════════════════════════════════════════════════════════════════════

# Sütun tanımları: (başlık, genişlik)
ALIS_HEADERS = [
    ('Sıra\nNo',                          5),
    ('Alış Faturasının\nTarihi',          13),
    ('Alış Faturasının\nSerisi',           9),
    ('Alış Faturasının\nSıra No\'su',     22),
    ('Satıcının Adı Soyadı\n/ Ünvanı',   35),
    ('Satıcının Vergi\nKimlik No / TC',   14),
    ('Alınan Mal/Hizmet\nCinsi',          35),
    ('Toplam\nMiktar',                    14),
    ('Matrah',                            14),
    ('Hesaplanan\nKDV',                   13),
    ('Tevkifatsız\nİndirilen KDV',        14),
    ('2 No\'lu Bey.\nÖdenen KDV',        14),
    ('Toplam\nİndirilen KDV',             14),
    ('GGB\nTescil No',                    12),
    ('KDV\nDönemi',                       10),
    ('Dosya\nFormatı',                     9),
    ('Fatura\nTipi',                      10),
]

SATIS_HEADERS = [
    ('Sıra\nNo',                          5),
    ('Satış Faturasının\nTarihi',         13),
    ('Satış Faturasının\nSerisi',          9),
    ('Satış Faturasının\nSıra No\'su',   22),
    ('Alıcının Adı Soyadı\n/ Ünvanı',    35),
    ('Alıcının Vergi\nKimlik No / TC',    14),
    ('Satılan Mal/Hizmet\nCinsi',         35),
    ('Toplam\nMiktar',                    14),
    ('KDV Hariç\nMatrah',                 14),
    ('KDV\nOranı %',                      10),
    ('KDV\nTutarı',                       13),
    ('İade\nİşlem Türü',                  12),
    ('GÇB\nTescil No',                    12),
    ('Dosya\nFormatı',                     9),
    ('Fatura\nTipi',                      10),
]


def _inv_rows_alis(inv):
    """Birleştirilmiş satış satırı için veri üret (alış)"""
    date_obj = inv.get('date_obj')
    kdv      = inv.get('kdv', 0.0)
    tevk     = inv.get('tevkifat', 0.0)
    tevksiz  = round(kdv - tevk, 2)   # L = K - M
    toplam_i = round(tevksiz + tevk, 2)  # N = L + M

    desc = _shorten_content(
        ', '.join(l['name'] for l in inv['lines'] if l.get('name')), 100
    )
    qty  = _format_qty(inv['lines'])

    return [
        None,                           # Sıra No — dışarıdan verilecek
        date_obj,                       # C: Tarih
        '',                             # D: Seri
        inv.get('inv_id', ''),          # E: Fatura No
        _shorten_name(inv.get('sup_name', '')),   # F: Satıcı Adı
        _vkn_fmt(inv.get('sup_vkn', '')),         # G: VKN
        desc,                           # H: İçerik
        qty,                            # I: Miktar
        inv.get('matrah', 0.0),         # J: Matrah
        kdv,                            # K: Hesaplanan KDV
        tevksiz,                        # L: Tevkifatsız İndirilen
        tevk,                           # M: 2 Nolu Bey.
        toplam_i,                       # N: Toplam İndirilen
        '',                             # O: GGB Tescil
        _kdv_donem(date_obj),           # P: KDV Dönemi
        inv.get('fmt', 'XML'),          # Q: Dosya Formatı
        inv.get('inv_type', ''),        # R: Fatura Tipi
    ]


def _inv_rows_alis_kalem(inv):
    """Kalem detayı satırları (alış) — her kalem ayrı satır"""
    date_obj = inv.get('date_obj')
    rows = []
    for line in inv.get('lines', [{'name': '-', 'qty': 1,
                                   'unit': 'Adet', 'amount': inv.get('matrah', 0),
                                   'kdv_rate': '', 'kdv_amount': inv.get('kdv', 0)}]):
        kdv_k  = line.get('kdv_amount', 0.0)
        # Kalem düzeyinde tevkifat yok, fatura toplamından oran hesaplanır
        tevk_k = 0.0
        rows.append([
            None,
            date_obj,
            '',
            inv.get('inv_id', ''),
            _shorten_name(inv.get('sup_name', '')),
            _vkn_fmt(inv.get('sup_vkn', '')),
            line.get('name', ''),
            f"{line['qty']:g} {line['unit']}",
            line.get('amount', 0.0),
            kdv_k,
            round(kdv_k - tevk_k, 2),
            tevk_k,
            round(kdv_k, 2),
            '',
            _kdv_donem(date_obj),
            inv.get('fmt', 'XML'),
            inv.get('inv_type', ''),
        ])
    return rows


def _inv_rows_satis(inv):
    """Birleştirilmiş satır (satış)"""
    date_obj = inv.get('date_obj')
    kdv      = inv.get('kdv', 0.0)
    matrah   = inv.get('matrah', 0.0)
    kdv_oran = round(kdv / matrah * 100, 0) if matrah else 0

    desc = _shorten_content(
        ', '.join(l['name'] for l in inv['lines'] if l.get('name')), 100
    )
    qty = _format_qty(inv['lines'])

    return [
        None,
        date_obj,
        '',
        inv.get('inv_id', ''),
        _shorten_name(inv.get('cus_name', '')),
        _vkn_fmt(inv.get('cus_vkn', '')),
        desc,
        qty,
        matrah,
        kdv_oran,
        kdv,
        '',   # İade İşlem Türü
        '',   # GÇB Tescil
        inv.get('fmt', 'XML'),  # Dosya Formatı
        inv.get('inv_type', ''),  # Fatura Tipi
    ]


def _inv_rows_satis_kalem(inv):
    """Kalem detayı satırları (satış)"""
    date_obj = inv.get('date_obj')
    rows = []
    for line in inv.get('lines', []):
        try:
            kdv_oran = float(line.get('kdv_rate', 0) or 0)
        except Exception:
            kdv_oran = 0
        rows.append([
            None,
            date_obj,
            '',
            inv.get('inv_id', ''),
            _shorten_name(inv.get('cus_name', '')),
            _vkn_fmt(inv.get('cus_vkn', '')),
            line.get('name', ''),
            f"{line['qty']:g} {line['unit']}",
            line.get('amount', 0.0),
            kdv_oran,
            line.get('kdv_amount', 0.0),
            '',
            '',
            inv.get('fmt', 'XML'),
            inv.get('inv_type', ''),
        ])
    return rows


def _build_excel_alis(data, filepath, months_split=False):
    """İndirilecek KDV Listesi Excel dosyası oluştur (xlsxwriter)"""
    # 0-tabanlı row_data indeksleri (_inv_rows_alis döndürdüğü listenin indeksleri)
    # [0]=SıraNo [1]=Tarih [2]=Seri [3]=FatNo [4]=Satıcı [5]=VKN
    # [6]=İçerik [7]=Miktar [8]=Matrah [9]=KDV [10]=Tevksiz [11]=Tevk [12]=Toplam
    # [13]=GGB [14]=KDVDönem [15]=Fmt [16]=FaturaTipi
    DATE_C = {1}
    TEXT_C = {5, 6, 7, 14, 15, 16}
    NUM_C  = {8, 9, 10, 11, 12}

    sorted_data = sorted(data, key=lambda x: x.get('inv_date', ''))

    wb  = xlsxwriter.Workbook(filepath, {'constant_memory': False,
                                          'strings_to_numbers': False,
                                          'default_date_format': 'DD.MM.YYYY'})
    fmts = _make_formats(wb)

    # ── Sayfa 1: İndirilecek KDV Listesi ─────────────────────────────────────
    ws1   = wb.add_worksheet('İndirilecek KDV Listesi')
    rows1 = [_inv_rows_alis(inv) for inv in sorted_data]
    _write_sheet_xls(ws1, fmts, ALIS_HEADERS, rows1,
                     'hdr_alis', 'İndirilecek KDV Listesi', CLR_TITLE_BG,
                     NUM_C, TEXT_C, DATE_C, flavor='alis')

    # ── Sayfa 2: Kalem Detayı ─────────────────────────────────────────────────
    ws2   = wb.add_worksheet('Kalem Detayı')
    rows2 = []
    for inv in sorted_data:
        rows2.extend(_inv_rows_alis_kalem(inv))
    _write_sheet_xls(ws2, fmts, ALIS_HEADERS, rows2,
                     'hdr_alis2', 'Kalem Detayı', CLR_TITLE_BG,
                     NUM_C, TEXT_C, DATE_C, flavor='alis')

    # ── Aylık sayfalar ────────────────────────────────────────────────────────
    if months_split:
        by_month = defaultdict(list)
        for inv in sorted_data:
            d = inv.get('date_obj')
            if d:
                by_month[(d.year, d.month)].append(inv)
        for (yr, mo), month_data in sorted(by_month.items()):
            sname  = f'{yr} {MONTHS_TR.get(mo, str(mo))}'[:31]
            ws_m   = wb.add_worksheet(sname)
            rows_m = [_inv_rows_alis(inv) for inv in month_data]
            _write_sheet_xls(ws_m, fmts, ALIS_HEADERS, rows_m,
                             'hdr_alis', sname, CLR_TITLE_BG,
                             NUM_C, TEXT_C, DATE_C, flavor='alis')

    wb.close()


def _build_excel_satis(data, filepath, months_split=False):
    """Satış Fatura Listesi Excel dosyası oluştur (xlsxwriter)"""
    # [0]=SıraNo [1]=Tarih [2]=Seri [3]=FatNo [4]=Alıcı [5]=VKN
    # [6]=İçerik [7]=Miktar [8]=Matrah [9]=KDVOranı [10]=KDV [11]=İade [12]=GÇB [13]=Fmt [14]=FaturaTipi
    DATE_C = {1}
    TEXT_C = {5, 6, 7, 13, 14}
    NUM_C  = {8, 10}
    PCT_C  = {9}

    sorted_data = sorted(data, key=lambda x: x.get('inv_date', ''))

    wb  = xlsxwriter.Workbook(filepath, {'constant_memory': False,
                                          'strings_to_numbers': False,
                                          'default_date_format': 'DD.MM.YYYY'})
    fmts = _make_formats(wb)

    ws1   = wb.add_worksheet('Satış Fatura Listesi')
    rows1 = [_inv_rows_satis(inv) for inv in sorted_data]
    _write_sheet_xls(ws1, fmts, SATIS_HEADERS, rows1,
                     'hdr_satis', 'Satış Fatura Listesi', CLR_TITLE_BG,
                     NUM_C, TEXT_C, DATE_C, PCT_C, flavor='satis')

    ws2   = wb.add_worksheet('Kalem Detayı')
    rows2 = []
    for inv in sorted_data:
        rows2.extend(_inv_rows_satis_kalem(inv))
    _write_sheet_xls(ws2, fmts, SATIS_HEADERS, rows2,
                     'hdr_alis2', 'Kalem Detayı', CLR_TITLE_BG,
                     NUM_C, TEXT_C, DATE_C, PCT_C, flavor='alis')

    if months_split:
        by_month = defaultdict(list)
        for inv in sorted_data:
            d = inv.get('date_obj')
            if d:
                by_month[(d.year, d.month)].append(inv)
        for (yr, mo), month_data in sorted(by_month.items()):
            sname  = f'{yr} {MONTHS_TR.get(mo, str(mo))}'[:31]
            ws_m   = wb.add_worksheet(sname)
            rows_m = [_inv_rows_satis(inv) for inv in month_data]
            _write_sheet_xls(ws_m, fmts, SATIS_HEADERS, rows_m,
                             'hdr_satis', sname, CLR_TITLE_BG,
                             NUM_C, TEXT_C, DATE_C, PCT_C, flavor='satis')

    wb.close()


# ═══════════════════════════════════════════════════════════════════════════════
#  ANA FONKSİYON — GUI tarafından çağrılır
# ═══════════════════════════════════════════════════════════════════════════════

def process_all(alis_folder, satis_folder, cikti_folder,
                stop_flag, cb_log, cb_progress,
                cb_stats, cb_status, cb_current,
                pause_flag=None, cb_eta=None, cb_done=None,
                cb_totals=None,
                cb_error_file=None, cb_duplicate_file=None,
                alis_start=0, satis_start=0,
                months_split=False, recursive=False, max_files=None):
    """
    GUI'den çağrılan ana işlem fonksiyonu.
    alis_start / satis_start: önceki durmadan devam için başlangıç indeksleri.
    months_split: True ise Excel'e aylık sayfa ekler.
    cb_error_file(fname, err): hatalı dosya bildirimi.
    """
    import time as _time
    from datetime import datetime as _dt, timedelta as _td
    from concurrent.futures import ThreadPoolExecutor as _TPE

    _WORKERS = min(8, ((__import__('os').cpu_count()) or 4))
    _CHUNK   = _WORKERS * 4   # her turda bu kadar dosyayı paralel parse et

    with _TPE(max_workers=2) as _ex:
        _fa = _ex.submit(_collect_files, alis_folder,  recursive=recursive)
        _fs = _ex.submit(_collect_files, satis_folder, recursive=recursive)
        alis_files  = _fa.result()
        satis_files = _fs.result()
    total       = len(alis_files) + len(satis_files)

    resuming = (alis_start > 0 or satis_start > 0)
    if resuming:
        cb_log(f'  ↩  Kaldığı yerden devam ediliyor  '
               f'(Alış: {alis_start}/{len(alis_files)}, '
               f'Satış: {satis_start}/{len(satis_files)})', 'warn')
    else:
        cb_log(f'  Alış  klasörü : {len(alis_files)} XML dosyası', 'info')
        cb_log(f'  Satış klasörü : {len(satis_files)} XML dosyası', 'info')
        cb_log(f'  Toplam        : {total} dosya', 'info')
    cb_log('─' * 50, 'head')

    if total == 0:
        cb_log('❌  Hiç XML dosyası bulunamadı!', 'err')
        cb_status('Hata — XML dosyası bulunamadı')
        return

    _start_time = _time.time()
    import threading as _threading
    _lock = _threading.Lock()

    # Paylaşılan sayaçlar — her iki thread lock ile günceller
    _S = {
        'processed':     alis_start + satis_start,
        'hata':          0,
        'mukerrer':      0,
        'processed_new': 0,
        'trial_cap_hit': False,
        'stopped':       False,   # stop_flag veya trial limiti
        'alis_done':     alis_start,   # GUI sayacı için gerçek anlık alış ilerlemesi
        'satis_done':    satis_start,  # GUI sayacı için gerçek anlık satış ilerlemesi
    }

    alis_data  = []
    satis_data = []

    def _calc_eta():
        p = _S['processed']
        if p <= 0:
            return
        elapsed = _time.time() - _start_time
        if elapsed <= 0:
            return
        speed     = p / (elapsed / 60)
        remaining = total - p
        eta_sec   = (remaining / (speed / 60)) if speed > 0 else 0
        eta_time  = (_dt.now() + _td(seconds=eta_sec)).strftime('%H:%M')
        m, s      = divmod(int(eta_sec), 60)
        if cb_eta:
            cb_eta(speed, f'{m:02d}dk {s:02d}sn', eta_time)

    cb_log('  ALIŞ ve SATIŞ faturalar aynı anda işleniyor...', 'head')
    cb_status('Faturalar işleniyor...')

    def _run_alis():
        seen_ids = set()
        _slice   = alis_files[alis_start:]
        cp       = 0
        while cp < len(_slice):
            if stop_flag.is_set() or _S['stopped']:
                break
            if pause_flag:
                while pause_flag.is_set():
                    if stop_flag.is_set():
                        return
                    _time.sleep(0.1)

            chunk      = _slice[cp:cp + _CHUNK]
            chunk_base = alis_start + cp
            with _TPE(max_workers=_WORKERS) as ex:
                results = list(ex.map(parse_invoice, chunk))

            for j, (src, result) in enumerate(zip(chunk, results)):
                if stop_flag.is_set() or _S['stopped']:
                    return
                with _lock:
                    if max_files is not None and _S['processed_new'] >= max_files:
                        _S['trial_cap_hit'] = True
                        _S['stopped']       = True
                        cb_log(f'⏸  Deneme limiti: {max_files} dosya işlendi, durduruluyor.', 'warn')
                        return
                    _S['processed']     += 1
                    _S['processed_new'] += 1
                    _S['alis_done']     += 1
                    p_now  = _S['processed']
                    h_now  = _S['hata']
                    m_now  = _S['mukerrer']
                    ad_now = _S['alis_done']
                    sd_now = _S['satis_done']

                i     = chunk_base + j
                fname = _display_name(src)
                cb_current(fname)
                _calc_eta()

                if result['ok']:
                    inv_id = result.get('inv_id', '')
                    if inv_id and inv_id in seen_ids:
                        with _lock:
                            _S['mukerrer'] += 1
                            m_now = _S['mukerrer']
                        cb_log(f'  ⚠ MÜKERRER: {fname}  (Fatura No: {inv_id})', 'warn')
                        if cb_duplicate_file:
                            cb_duplicate_file(fname, inv_id)
                    else:
                        if inv_id:
                            seen_ids.add(inv_id)
                        alis_data.append(result)
                        cb_log(f'  ✓ [A] {fname}', 'ok')
                else:
                    with _lock:
                        _S['hata'] += 1
                        h_now = _S['hata']
                    cb_log(f'  ✗ [A] {fname}  →  {result["err"]}', 'err')
                    if cb_error_file:
                        cb_error_file(fname, result['err'])

                cb_progress(p_now / total * 0.8)
                cb_stats(ad_now, len(alis_files), sd_now, len(satis_files), h_now, m_now)
            cp += _CHUNK

    def _run_satis():
        seen_ids = set()
        _slice   = satis_files[satis_start:]
        cp       = 0
        while cp < len(_slice):
            if stop_flag.is_set() or _S['stopped']:
                break
            if pause_flag:
                while pause_flag.is_set():
                    if stop_flag.is_set():
                        return
                    _time.sleep(0.1)

            chunk      = _slice[cp:cp + _CHUNK]
            chunk_base = satis_start + cp
            with _TPE(max_workers=_WORKERS) as ex:
                results = list(ex.map(parse_invoice, chunk))

            for j, (src, result) in enumerate(zip(chunk, results)):
                if stop_flag.is_set() or _S['stopped']:
                    return
                with _lock:
                    if max_files is not None and _S['processed_new'] >= max_files:
                        _S['trial_cap_hit'] = True
                        _S['stopped']       = True
                        cb_log(f'⏸  Deneme limiti: {max_files} dosya işlendi, durduruluyor.', 'warn')
                        return
                    _S['processed']     += 1
                    _S['processed_new'] += 1
                    _S['satis_done']    += 1
                    p_now  = _S['processed']
                    h_now  = _S['hata']
                    m_now  = _S['mukerrer']
                    ad_now = _S['alis_done']
                    sd_now = _S['satis_done']

                i     = chunk_base + j
                fname = _display_name(src)
                cb_current(fname)
                _calc_eta()

                if result['ok']:
                    inv_id = result.get('inv_id', '')
                    if inv_id and inv_id in seen_ids:
                        with _lock:
                            _S['mukerrer'] += 1
                            m_now = _S['mukerrer']
                        cb_log(f'  ⚠ MÜKERRER: {fname}  (Fatura No: {inv_id})', 'warn')
                        if cb_duplicate_file:
                            cb_duplicate_file(fname, inv_id)
                    else:
                        if inv_id:
                            seen_ids.add(inv_id)
                        satis_data.append(result)
                        cb_log(f'  ✓ [S] {fname}', 'ok')
                else:
                    with _lock:
                        _S['hata'] += 1
                        h_now = _S['hata']
                    cb_log(f'  ✗ [S] {fname}  →  {result["err"]}', 'err')
                    if cb_error_file:
                        cb_error_file(fname, result['err'])

                cb_progress(p_now / total * 0.8)
                cb_stats(ad_now, len(alis_files), sd_now, len(satis_files), h_now, m_now)
            cp += _CHUNK

    # ── Alış + Satış aynı anda çalıştır ──────────────────────────────────────
    with _TPE(max_workers=2) as _pool:
        _f_alis  = _pool.submit(_run_alis)
        _f_satis = _pool.submit(_run_satis)
        _f_alis.result()
        _f_satis.result()

    processed      = _S['processed']
    hata           = _S['hata']
    mukerrer       = _S['mukerrer']
    _processed_new = _S['processed_new']
    trial_cap_hit  = _S['trial_cap_hit']

    if stop_flag.is_set():
        cb_log('⏹  İşlem durduruldu.', 'warn')
        if cb_done:
            cb_done(len(alis_data), len(satis_data), hata,
                    len(alis_files), len(satis_files), _processed_new, mukerrer)
        return

    # ── Tutar özeti hesapla ───────────────────────────────────────────────────
    if cb_totals:
        _alis_matrah  = sum(r.get('matrah', 0) or 0 for r in alis_data)
        _alis_kdv     = sum(r.get('kdv',    0) or 0 for r in alis_data)
        _satis_matrah = sum(r.get('matrah', 0) or 0 for r in satis_data)
        _satis_kdv    = sum(r.get('kdv',    0) or 0 for r in satis_data)
        cb_totals(
            round(_alis_matrah, 2),          round(_alis_matrah  + _alis_kdv,  2),
            round(_satis_matrah, 2),         round(_satis_matrah + _satis_kdv, 2),
        )

    # ── Excel oluştur ─────────────────────────────────────────────────────────
    cb_log('─' * 50, 'head')
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')

    if alis_data:
        cb_status('İndirilecek KDV Listesi oluşturuluyor...')
        cb_log('  📊  İndirilecek KDV Listesi Excel yazılıyor...', 'info')
        alis_path = os.path.join(
            cikti_folder, f'Indirilecek_KDV_Listesi_{ts}.xlsx'
        )
        try:
            _build_excel_alis(alis_data, alis_path, months_split=months_split)
            cb_log(f'  ✓ Alış Excel kaydedildi:', 'ok')
            cb_log(f'    {alis_path}', 'info')
        except Exception as e:
            cb_log(f'  ✗ Alış Excel hatası: {e}', 'err')
            hata += 1
    else:
        cb_log('  ⚠  Alış verisi yok — Excel oluşturulmadı.', 'warn')

    cb_progress(0.9)

    if satis_data:
        cb_status('Satış Fatura Listesi oluşturuluyor...')
        cb_log('  📊  Satış Fatura Listesi Excel yazılıyor...', 'info')
        satis_path = os.path.join(
            cikti_folder, f'Satis_Fatura_Listesi_{ts}.xlsx'
        )
        try:
            _build_excel_satis(satis_data, satis_path, months_split=months_split)
            cb_log(f'  ✓ Satış Excel kaydedildi:', 'ok')
            cb_log(f'    {satis_path}', 'info')
        except Exception as e:
            cb_log(f'  ✗ Satış Excel hatası: {e}', 'err')
            hata += 1
    else:
        cb_log('  ⚠  Satış verisi yok — Excel oluşturulmadı.', 'warn')

    cb_progress(1.0)

    # ── Özet ──────────────────────────────────────────────────────────────────
    elapsed_total = _time.time() - _start_time
    em, es = divmod(int(elapsed_total), 60)
    cb_log('─' * 50, 'head')
    cb_log(f'  Alış  : {len(alis_data)} fatura işlendi', 'ok')
    if alis_data:
        _am  = sum(r.get('matrah', 0) or 0 for r in alis_data)
        _ak  = sum(r.get('kdv',    0) or 0 for r in alis_data)
        cb_log(f'    Matrah: {_am:,.2f} ₺  |  KDV: {_ak:,.2f} ₺  |  Toplam: {_am+_ak:,.2f} ₺'.replace(',', '.'), 'info')
    cb_log(f'  Satış : {len(satis_data)} fatura işlendi', 'ok')
    if satis_data:
        _sm  = sum(r.get('matrah', 0) or 0 for r in satis_data)
        _sk  = sum(r.get('kdv',    0) or 0 for r in satis_data)
        cb_log(f'    Matrah: {_sm:,.2f} ₺  |  KDV: {_sk:,.2f} ₺  |  Toplam: {_sm+_sk:,.2f} ₺'.replace(',', '.'), 'info')
    if mukerrer:
        cb_log(f'  Mükerrer: {mukerrer} fatura atlandı', 'warn')
    if hata:
        cb_log(f'  Hata  : {hata} dosya', 'err')
    cb_log(f'  Süre  : {em:02d}dk {es:02d}sn', 'info')
    cb_stats(len(alis_files), len(alis_files),
             len(satis_files), len(satis_files), hata, mukerrer)
    cb_status('Tamamlandı')
    if cb_done:
        cb_done(len(alis_data), len(satis_data), hata,
                len(alis_files), len(satis_files),
                _processed_new, mukerrer)
