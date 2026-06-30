"""
Pipeline OCR — S2 InvoiceAgent
Ordre de traitement :
  1. PDF natif     → pdfplumber  (texte sélectionnable)
  2. Image / scan  → EasyOCR GPU (arabe + français)
  3. PDF scanné    → PyMuPDF page→image → EasyOCR
  4. Fallback      → Gemini Vision si confidence < OCR_MIN_CONFIDENCE
"""
from __future__ import annotations

import io
import logging
import re
import unicodedata
from dataclasses import dataclass, field

import easyocr
import fitz  # PyMuPDF
import pdfplumber

logger = logging.getLogger(__name__)

# ── Seuils ────────────────────────────────────────────────────────────────────
OCR_MIN_CONFIDENCE   = 60.0   # en dessous → fallback Gemini Vision
PDF_MIN_CHARS        = 50     # moins de N chars → considéré comme scanné

# ── Singleton EasyOCR (chargement du modèle une seule fois) ──────────────────
_reader: easyocr.Reader | None = None

def _get_reader() -> easyocr.Reader:
    global _reader
    if _reader is None:
        import os
        use_gpu = os.getenv("EASYOCR_GPU", "false").lower() == "true"
        logger.info("Chargement EasyOCR (ar + fr) gpu=%s…", use_gpu)
        _reader = easyocr.Reader(["ar", "fr"], gpu=use_gpu)
        logger.info("EasyOCR prêt.")
    return _reader


# ── Résultat OCR ──────────────────────────────────────────────────────────────
@dataclass
class OcrResult:
    text: str                        # texte brut normalisé
    language: str                    # "fr" | "ar" | "mixed" | "unknown"
    confidence: float                # 0.0 – 100.0
    method: str                      # "pdfplumber" | "easyocr" | "gemini_fallback"
    pages: int = 1
    needs_gemini_fallback: bool = False
    raw_blocks: list[dict] = field(default_factory=list)


# ── Normalisation texte ───────────────────────────────────────────────────────

# Chiffres indo-arabes → latins
_AR_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
# Chiffres persans → latins
_FA_DIGITS  = str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")

_MONTH_MAP = {
    "janvier": "01", "jan": "01", "يناير": "01", "جانفي": "01",
    "février": "02", "fév": "02", "فبراير": "02", "فيفري": "02",
    "mars": "03",    "mar": "03", "مارس": "03",
    "avril": "04",   "avr": "04", "أفريل": "04", "أبريل": "04",
    "mai": "05",     "ماي": "05", "مايو": "05",
    "juin": "06",    "جوان": "06","يونيو": "06",
    "juillet": "07", "jui": "07", "جويلية": "07","يوليو": "07",
    "août": "08",    "aoû": "08", "أوت": "08",   "أغسطس": "08",
    "septembre": "09","sep": "09","سبتمبر": "09",
    "octobre": "10", "oct": "10", "أكتوبر": "10",
    "novembre": "11","nov": "11", "نوفمبر": "11",
    "décembre": "12","déc": "12", "ديسمبر": "12",
}

def _month_to_iso(m: re.Match) -> str:
    day   = m.group(1).zfill(2)
    month = _MONTH_MAP.get(m.group(2).lower(), "01")
    year  = m.group(3)
    return f"{year}-{month}-{day}"

# Formats de date multi-locales → ISO
_DATE_PATTERNS = [
    # 15/03/2024  ou  15-03-2024  ou  15.03.2024
    (re.compile(r"\b(\d{1,2})[/\-\.](\d{1,2})[/\-\.](\d{4})\b"),
     lambda m: f"{m.group(3)}-{m.group(2).zfill(2)}-{m.group(1).zfill(2)}"),
    # 2024/03/15
    (re.compile(r"\b(\d{4})[/\-\.](\d{1,2})[/\-\.](\d{1,2})\b"),
     lambda m: f"{m.group(1)}-{m.group(2).zfill(2)}-{m.group(3).zfill(2)}"),
    # 15 mars 2024  /  15 مارس 2024
    (re.compile(
        r"\b(\d{1,2})\s+(janvier|février|mars|avril|mai|juin|juillet|août|septembre|octobre|novembre|décembre"
        r"|jan|fév|mar|avr|jui|aoû|sep|oct|nov|déc"
        r"|جانفي|فيفري|مارس|أفريل|ماي|جوان|جويلية|أوت|سبتمبر|أكتوبر|نوفمبر|ديسمبر"
        r"|يناير|فبراير|أبريل|مايو|يونيو|يوليو|أغسطس|نوفمبر|ديسمبر"
        r")\s+(\d{4})\b",
        re.IGNORECASE,
    ), _month_to_iso),
]


def normalize_text(text: str) -> str:
    """
    Normalise le texte extrait :
    - Chiffres indo-arabes / persans → latins
    - Virgule décimale arabe (٫) → point
    - Dates multi-format → ISO 8601
    - Nettoyage espaces superflus
    """
    text = text.translate(_AR_DIGITS).translate(_FA_DIGITS)
    text = text.replace("٫", ".").replace("،", ",")
    # Normalisation Unicode (décomposition puis recomposition)
    text = unicodedata.normalize("NFC", text)
    # Dates
    for pattern, replacer in _DATE_PATTERNS:
        text = pattern.sub(replacer, text)
    # Espaces multiples
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


# ── Détection langue ──────────────────────────────────────────────────────────

_AR_BLOCK = re.compile(r"[\u0600-\u06FF\u0750-\u077F\uFB50-\uFDFF\uFE70-\uFEFF]")
_FR_WORD   = re.compile(
    r"\b(facture|montant|total|tva|date|fournisseur|client|référence|numéro|bon|commande"
    r"|prix|quantité|désignation|paiement|échéance|avoir)\b",
    re.IGNORECASE,
)

def detect_language(text: str) -> str:
    ar_chars = len(_AR_BLOCK.findall(text))
    fr_words = len(_FR_WORD.findall(text))
    total    = max(len(text), 1)
    ar_ratio = ar_chars / total

    if ar_ratio > 0.3 and fr_words > 2:
        return "mixed"
    if ar_ratio > 0.2:
        return "ar"
    if fr_words > 0 or ar_ratio < 0.05:
        return "fr"
    return "unknown"


# ── Stratégie 1 : pdfplumber (PDF natif) ─────────────────────────────────────

def _extract_pdf_native(file_bytes: bytes) -> tuple[str, int]:
    """Extrait le texte d'un PDF natif avec pdfplumber. Retourne (texte, nb_pages)."""
    text_parts = []
    n_pages = 0
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        n_pages = len(pdf.pages)
        for page in pdf.pages:
            # Texte brut
            t = page.extract_text(x_tolerance=3, y_tolerance=3) or ""
            text_parts.append(t)
            # Tableaux → ajoutés comme lignes TSV
            for table in page.extract_tables():
                for row in table:
                    line = "\t".join(cell or "" for cell in row)
                    text_parts.append(line)
    return "\n".join(text_parts), n_pages


# ── Stratégie 2 : EasyOCR (images et PDFs scannés) ───────────────────────────

def _pdf_to_images_bytes(file_bytes: bytes, dpi: int = 200) -> list[bytes]:
    """Convertit chaque page PDF en PNG bytes (résolution adaptée à l'OCR)."""
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    images = []
    mat = fitz.Matrix(dpi / 72, dpi / 72)
    for page in doc:
        pix = page.get_pixmap(matrix=mat, colorspace=fitz.csRGB)
        images.append(pix.tobytes("png"))
    return images


def _run_easyocr(image_bytes_list: list[bytes]) -> tuple[str, float, list[dict]]:
    """
    Lance EasyOCR sur une liste d'images.
    Retourne (texte_complet, confidence_moyenne, blocs_bruts).
    """
    reader = _get_reader()
    all_lines = []
    all_conf  = []
    raw_blocks = []

    for img_bytes in image_bytes_list:
        results = reader.readtext(img_bytes, detail=1, paragraph=False)
        for bbox, text, conf in results:
            all_lines.append(text)
            all_conf.append(conf * 100)
            raw_blocks.append({"text": text, "confidence": round(conf * 100, 1), "bbox": bbox})

    full_text  = "\n".join(all_lines)
    avg_conf   = sum(all_conf) / len(all_conf) if all_conf else 0.0
    return full_text, avg_conf, raw_blocks


# ── Fonction principale ───────────────────────────────────────────────────────

def run_ocr(file_bytes: bytes, mime_type: str) -> OcrResult:
    """
    Pipeline OCR complet.
    Retourne un OcrResult avec texte normalisé, langue, confiance et méthode utilisée.
    Si needs_gemini_fallback=True, l'appelant doit relancer avec Gemini Vision.
    """

    # ── PDF ──────────────────────────────────────────────────────────────────
    if mime_type == "application/pdf":
        raw_text, n_pages = _extract_pdf_native(file_bytes)

        # PDF natif avec suffisamment de texte
        if len(raw_text.strip()) >= PDF_MIN_CHARS:
            text       = normalize_text(raw_text)
            language   = detect_language(text)
            confidence = 95.0  # texte natif = haute confiance
            logger.info("PDF natif extrait : %d pages, %d chars", n_pages, len(text))
            return OcrResult(
                text=text, language=language, confidence=confidence,
                method="pdfplumber", pages=n_pages,
            )

        # PDF scanné → convertir en images → EasyOCR
        logger.info("PDF scanné détecté (%d chars) → EasyOCR", len(raw_text.strip()))
        images = _pdf_to_images_bytes(file_bytes, dpi=200)
        raw_ocr, confidence, blocks = _run_easyocr(images)
        text     = normalize_text(raw_ocr)
        language = detect_language(text)
        logger.info("EasyOCR PDF scanné : confidence=%.1f%%", confidence)

        if confidence < OCR_MIN_CONFIDENCE:
            logger.warning("Confidence trop faible (%.1f%%) → fallback Gemini", confidence)
            return OcrResult(
                text=text, language=language, confidence=confidence,
                method="easyocr", pages=n_pages,
                needs_gemini_fallback=True, raw_blocks=blocks,
            )
        return OcrResult(
            text=text, language=language, confidence=confidence,
            method="easyocr", pages=n_pages, raw_blocks=blocks,
        )

    # ── Image native (JPEG, PNG, TIFF, WEBP) ─────────────────────────────────
    elif mime_type in ("image/jpeg", "image/png", "image/tiff", "image/webp"):
        raw_ocr, confidence, blocks = _run_easyocr([file_bytes])
        text     = normalize_text(raw_ocr)
        language = detect_language(text)
        logger.info("EasyOCR image : confidence=%.1f%%", confidence)

        if confidence < OCR_MIN_CONFIDENCE:
            logger.warning("Confidence trop faible (%.1f%%) → fallback Gemini", confidence)
            return OcrResult(
                text=text, language=language, confidence=confidence,
                method="easyocr", pages=1,
                needs_gemini_fallback=True, raw_blocks=blocks,
            )
        return OcrResult(
            text=text, language=language, confidence=confidence,
            method="easyocr", pages=1, raw_blocks=blocks,
        )

    # ── DOCX ──────────────────────────────────────────────────────────────────
    elif mime_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        raise NotImplementedError("DOCX : convertir en PDF d'abord.")

    else:
        raise ValueError(f"Type MIME non supporté : {mime_type}")
