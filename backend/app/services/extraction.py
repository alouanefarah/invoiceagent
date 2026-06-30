"""
Service d'extraction — Groq (texte) + Gemini Vision (fallback images)
Pipeline :
  OCR → texte brut → Groq llama-3.3-70b → JSON structuré
  Si OCR confidence < seuil → Gemini Vision (si clé dispo) sinon Groq sur texte dégradé
"""
from __future__ import annotations

import json
import logging
import re

from app.services.llm_client import chat
from app.services.ocr import OcrResult, run_ocr

logger = logging.getLogger(__name__)


EXTRACTION_PROMPT = """Tu es un expert en comptabilité et traitement de factures tunisiennes et françaises (multilingue FR/AR).

Voici le texte brut extrait d'une facture. Analyse-le et extrais les informations.
Réponds EXCLUSIVEMENT avec un objet JSON valide, sans texte avant ni après, sans balises markdown.

{{
  "language": "fr | ar | mixed",
  "invoice_number": "string ou null",
  "invoice_date": "YYYY-MM-DD ou null",
  "due_date": "YYYY-MM-DD ou null",
  "currency": "TND | EUR | USD",
  "amount_ht": nombre ou null,
  "amount_tva": nombre ou null,
  "amount_ttc": nombre ou null,
  "tva_rate": nombre ex 19.0 ou null,
  "timbre_fiscal": nombre ou null,
  "jurisdiction": "TN | FR",
  "vendor": {{
    "name": "string ou null",
    "tax_id": "string ou null",
    "address": "string ou null",
    "country": "TN | FR ou null",
    "email": "string ou null",
    "phone": "string ou null"
  }},
  "line_items": [
    {{
      "line_number": entier ou null,
      "description": "string",
      "quantity": nombre ou null,
      "unit_price": nombre ou null,
      "tva_rate": nombre ou null,
      "amount_ht": nombre ou null,
      "amount_ttc": nombre ou null
    }}
  ],
  "confidence": nombre entre 0 et 100
}}

Règles importantes :
- Dates en ISO 8601 : YYYY-MM-DD
- Montants en nombres décimaux (pas de chaînes)
- Pour factures tunisiennes : devise TND, juridiction TN
- timbre_fiscal : le montant du timbre fiscal s'il est mentionné séparément (souvent 1.000 DT en Tunisie). Si absent du document, mets 0.
- amount_ttc doit normalement être égal à amount_ht + amount_tva + timbre_fiscal. Recopie le TTC tel qu'imprimé sur le document, ne le recalcule pas toi-même.
- tax_id = Matricule Fiscal (MF) pour TN, SIRET pour FR
- Si un champ est absent mets null
- confidence = ta confiance globale dans l'extraction

TEXTE DE LA FACTURE :
---
{text}
---"""


def _fix_invalid_escapes(raw: str) -> str:
    """Corrige les backslashes non-échappés que Groq insère parfois (chemins, codes MF avec /)."""
    return re.sub(r'\\(?!["\\/bfnrtu])', r'\\\\', raw)


def _normalize_nulls(obj):
    """Convertit récursivement les chaînes 'null'/'none'/'' que Groq renvoie parfois en vrai None."""
    if isinstance(obj, dict):
        return {k: _normalize_nulls(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_normalize_nulls(v) for v in obj]
    if isinstance(obj, str) and obj.strip().lower() in ("null", "none", ""):
        return None
    return obj


def _parse_json(raw: str) -> dict:
    clean = re.sub(r"```(?:json)?", "", raw).strip().rstrip("`").strip()
    # Cherche le premier { et dernier }
    start = clean.find("{")
    end   = clean.rfind("}") + 1
    if start >= 0 and end > start:
        clean = clean[start:end]
    try:
        parsed = json.loads(clean)
    except json.JSONDecodeError as exc:
        logger.warning("JSON invalide reçu de Groq (%s) → tentative de correction des escapes", exc)
        parsed = json.loads(_fix_invalid_escapes(clean))
    return _normalize_nulls(parsed)


def _groq_from_text(text: str) -> dict:
    """Extraction via Groq sur texte brut OCR."""
    prompt   = EXTRACTION_PROMPT.format(text=text[:6000])
    raw      = chat(prompt)
    return _parse_json(raw)


def _gemini_vision_fallback(file_bytes: bytes, mime_type: str) -> dict:
    """Fallback Gemini Vision pour scans illisibles (si clé Gemini dispo)."""
    from app.core.config import settings
    if not settings.GEMINI_API_KEY:
        raise RuntimeError("Pas de clé Gemini — fallback Vision impossible")
    import google.generativeai as genai
    import fitz, re
    genai.configure(api_key=settings.GEMINI_API_KEY)
    model = genai.GenerativeModel(settings.GEMINI_MODEL)
    if mime_type == "application/pdf":
        doc   = fitz.open(stream=file_bytes, filetype="pdf")
        parts = [EXTRACTION_PROMPT.format(text="Analyse cette image de facture et extrais les données.")]
        for i, page in enumerate(doc):
            if i >= 5: break
            pix = page.get_pixmap(dpi=150)
            parts.append({"mime_type": "image/png", "data": pix.tobytes("png")})
    else:
        parts = [EXTRACTION_PROMPT.format(text="Analyse cette image."),
                 {"mime_type": mime_type, "data": file_bytes}]
    response = model.generate_content(parts)
    return _parse_json(response.text)


def extract_invoice(file_bytes: bytes, mime_type: str) -> dict:
    """
    Pipeline complet :
    1. OCR (pdfplumber ou EasyOCR)
    2. Groq sur le texte extrait
    3. Fallback Gemini Vision si confiance trop faible (optionnel)
    """
    # ── Étape 1 : OCR ────────────────────────────────────────────────────────
    try:
        ocr: OcrResult = run_ocr(file_bytes, mime_type)
        logger.info("OCR : method=%s lang=%s confidence=%.1f%% fallback=%s",
                    ocr.method, ocr.language, ocr.confidence, ocr.needs_gemini_fallback)
    except Exception as exc:
        logger.exception("OCR échoué : %s", exc)
        ocr = OcrResult(text="", language="unknown", confidence=0.0,
                        method="failed", needs_gemini_fallback=True)

    # ── Étape 2 : Groq sur texte (chemin principal) ───────────────────────────
    if ocr.text.strip():
        try:
            data = _groq_from_text(ocr.text)
            if ocr.language != "unknown":
                data["language"] = ocr.language
            data["_ocr_method"]     = ocr.method
            data["_ocr_confidence"] = round(ocr.confidence, 1)
            data["_raw_text"]       = ocr.text
            return data
        except Exception as exc:
            logger.warning("Groq échoué (%s) → fallback Vision", exc)

    # ── Étape 3 : Fallback Gemini Vision ─────────────────────────────────────
    logger.info("Fallback Gemini Vision (confidence=%.1f%%)", ocr.confidence)
    try:
        data = _gemini_vision_fallback(file_bytes, mime_type)
        data["_ocr_method"]     = "gemini_vision_fallback"
        data["_ocr_confidence"] = round(ocr.confidence, 1)
        data["_raw_text"]       = ocr.text
        return data
    except Exception as exc:
        raise RuntimeError(f"Tous les backends ont échoué. Dernier: {exc}")
