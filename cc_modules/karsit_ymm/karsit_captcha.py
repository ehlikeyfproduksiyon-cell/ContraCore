# -*- coding: utf-8 -*-
"""
CAPTCHA OCR — OpenCV preprocessing + Tesseract + manual fallback.
Strateji: captcha_ocr_production_strategy.md
"""
import io
import logging

log = logging.getLogger(__name__)

THRESHOLD = 1.0

def _get_pytesseract():
    import pytesseract as _pt
    _pt.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    return _pt

# Tesseract config — doc'tan birebir (karışık harfli CAPTCHA için I,O,0,1 çıkarıldı)
_TESS_CONFIG = (
    "--oem 3 "
    "--psm 7 "
    "-c tessedit_char_whitelist="
    "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghjklmnpqrstuvwxyz23456789"
)


def ocr_solve(img_bytes: bytes) -> tuple[str, float]:
    """
    1 kez OCR dene (deterministic — aynı image → aynı sonuç, retry anlamsız).
    Döner: (metin, confidence 0.0–1.0).
    """
    processed = _preprocess(img_bytes)
    return _tesseract(processed)


def _preprocess(img_bytes: bytes) -> bytes:
    """
    Doc'taki pipeline:
    1. Grayscale
    2. 2x upscale
    3. Median blur (gürültü)
    4. Otsu threshold
    5. Morphological close
    """
    try:
        import cv2
        import numpy as np

        arr = np.frombuffer(img_bytes, dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img is None:
            return img_bytes

        # 1. Grayscale
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # 2. 2x upscale
        gray = cv2.resize(gray, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)

        # 3. Median blur
        gray = cv2.medianBlur(gray, 3)

        # 4. Otsu threshold
        _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        # 5. Morphological close
        kernel = np.ones((2, 2), np.uint8)
        thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)

        ok, buf = cv2.imencode('.png', thresh)
        return bytes(buf) if ok else img_bytes

    except Exception as e:
        log.debug("Preprocessing hatası: %s", e)
        return img_bytes


def _tesseract(img_bytes: bytes) -> tuple[str, float]:
    try:
        from PIL import Image

        pytesseract = _get_pytesseract()
        img = Image.open(io.BytesIO(img_bytes))
        data = pytesseract.image_to_data(
            img,
            config=_TESS_CONFIG,
            output_type=pytesseract.Output.DICT,
        )
        texts = [t.strip() for t in data['text'] if t.strip()]
        confs = [c / 100.0 for c, t in zip(data['conf'], data['text'])
                 if t.strip() and c > 0]

        if not texts or not confs:
            log.debug("Tesseract: sonuç yok")
            return '', 0.0

        text = ''.join(texts)
        conf = sum(confs) / len(confs)
        log.debug("Tesseract: %r conf=%.2f", text, conf)
        return text, conf

    except Exception as e:
        log.debug("Tesseract hata: %s", e)
        return '', 0.0
