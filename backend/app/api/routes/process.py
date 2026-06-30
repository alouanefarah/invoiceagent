"""
POST /process/{invoice_id}
Lance manuellement le pipeline OCR + extraction sur une facture déjà uploadée.
Utile pour retraiter une facture ou tester le pipeline S2.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.models import Invoice, LineItem, Vendor
from app.services.storage import get_file_bytes
from app.agents.graph import run_invoice_pipeline
import uuid

logger = logging.getLogger(__name__)
router = APIRouter()


def _to_decimal(value) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError):
        return None


@router.post("/{invoice_id}", status_code=200)
async def process_invoice(invoice_id: str, db: AsyncSession = Depends(get_db)):
    """
    Relance le pipeline OCR + Gemini sur une facture existante.
    Retourne les données extraites et met à jour la DB.
    """
    # Récupérer la facture
    result  = await db.execute(select(Invoice).where(Invoice.id == invoice_id))
    invoice = result.scalar_one_or_none()
    if not invoice:
        raise HTTPException(status_code=404, detail="Facture introuvable")

    # Récupérer le fichier depuis MinIO
    try:
        file_bytes = get_file_bytes(invoice.minio_path)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Impossible de lire le fichier : {exc}")

    # Mettre le statut en processing
    invoice.status = "processing"
    await db.commit()

    try:
        # ── Pipeline LangGraph : Agent Parse (+ retry) → Agent Validation ──────
        graph_state = run_invoice_pipeline(file_bytes, invoice.mime_type)

        if graph_state.get("extracted") is None:
            raise RuntimeError(graph_state.get("error") or "Échec extraction sans message")

        data = graph_state["extracted"]

        # ── Mise à jour Invoice ───────────────────────────────────────────────
        invoice.language        = data.get("language", "unknown")
        invoice.invoice_number  = data.get("invoice_number")
        invoice.currency        = data.get("currency", "TND")
        invoice.jurisdiction    = data.get("jurisdiction", "TN")
        invoice.amount_ht       = _to_decimal(data.get("amount_ht"))
        invoice.amount_tva      = _to_decimal(data.get("amount_tva"))
        invoice.amount_ttc      = _to_decimal(data.get("amount_ttc"))
        invoice.tva_rate        = _to_decimal(data.get("tva_rate"))
        invoice.timbre_fiscal   = _to_decimal(data.get("timbre_fiscal")) or Decimal("0")
        invoice.ocr_confidence  = _to_decimal(data.get("_ocr_confidence"))
        invoice.raw_text        = data.get("_raw_text")
        invoice.structured_data = data

        for field_name, key in [("invoice_date", "invoice_date"), ("due_date", "due_date")]:
            raw_date = data.get(key)
            if raw_date:
                try:
                    setattr(invoice, field_name,
                            datetime.fromisoformat(raw_date).replace(tzinfo=timezone.utc))
                except ValueError:
                    pass

        # ── Vendor ───────────────────────────────────────────────────────────
        vendor_data = data.get("vendor") or {}
        vendor_name = vendor_data.get("name")
        if vendor_name:
            res = await db.execute(select(Vendor).where(Vendor.name == vendor_name))
            vendor = res.scalar_one_or_none()
            if not vendor:
                vendor = Vendor(
                    id=uuid.uuid4(),
                    name=vendor_name,
                    tax_id=vendor_data.get("tax_id"),
                    address=vendor_data.get("address"),
                    country=vendor_data.get("country"),
                    jurisdiction=data.get("jurisdiction", "TN"),
                    email=vendor_data.get("email"),
                    phone=vendor_data.get("phone"),
                    is_known=False,
                )
                db.add(vendor)
                await db.flush()
            invoice.vendor_id = vendor.id

        # ── Line items (reset + réinsertion) ─────────────────────────────────
        await db.execute(
            LineItem.__table__.delete().where(LineItem.invoice_id == invoice.id)
        )
        for item in data.get("line_items") or []:
            db.add(LineItem(
                id=uuid.uuid4(),
                invoice_id=invoice.id,
                line_number=item.get("line_number"),
                description=item.get("description"),
                quantity=_to_decimal(item.get("quantity")),
                unit_price=_to_decimal(item.get("unit_price")),
                tva_rate=_to_decimal(item.get("tva_rate")),
                amount_ht=_to_decimal(item.get("amount_ht")),
                amount_ttc=_to_decimal(item.get("amount_ttc")),
            ))

        # ── Résultat Agent Validation (déjà exécuté par le graphe) ─────────────
        invoice.validation_status = graph_state.get("validation_status")
        invoice.validation_delta  = graph_state.get("validation_delta")

        invoice.status       = "anomaly" if graph_state.get("validation_status") == "mismatch" else "validated"
        invoice.processed_at = datetime.now(timezone.utc)
        invoice.processing_log = [{
            "step":              "langgraph_pipeline",
            "ocr_method":        data.get("_ocr_method"),
            "ocr_confidence":    data.get("_ocr_confidence"),
            "language":          data.get("language"),
            "parse_attempts":    graph_state.get("attempt"),
            "status":            "ok",
            "validation_status": graph_state.get("validation_status"),
            "validation_reason": graph_state.get("validation_reason"),
        }]
        await db.commit()
        logger.info("Facture %s traitée (méthode=%s, tentatives=%s, validation=%s)",
                    invoice_id, data.get("_ocr_method"), graph_state.get("attempt"),
                    graph_state.get("validation_status"))

    except Exception as exc:
        logger.exception("Erreur pipeline %s : %s", invoice_id, exc)
        invoice.status = "anomaly"
        invoice.processing_log = [{"step": "langgraph_pipeline", "status": "error", "error": str(exc)}]
        await db.commit()
        raise HTTPException(status_code=500, detail=str(exc))

    return {
        "invoice_id":         invoice_id,
        "status":             invoice.status,
        "language":           invoice.language,
        "ocr_method":         data.get("_ocr_method"),
        "ocr_confidence":     data.get("_ocr_confidence"),
        "parse_attempts":     graph_state.get("attempt"),
        "invoice_number":     invoice.invoice_number,
        "amount_ht":          float(invoice.amount_ht)      if invoice.amount_ht      else None,
        "amount_tva":         float(invoice.amount_tva)     if invoice.amount_tva     else None,
        "amount_ttc":         float(invoice.amount_ttc)     if invoice.amount_ttc     else None,
        "timbre_fiscal":      float(invoice.timbre_fiscal)  if invoice.timbre_fiscal  else None,
        "validation_status":  invoice.validation_status,
        "validation_delta":   float(invoice.validation_delta) if invoice.validation_delta else None,
        "vendor":             vendor_name if vendor_name else None,
        "raw_text":           invoice.raw_text,
    }
