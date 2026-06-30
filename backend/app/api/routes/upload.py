import uuid
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.models import Invoice, LineItem, Vendor
from app.services import storage
from app.agents.graph import run_invoice_pipeline

import logging

logger = logging.getLogger(__name__)
router = APIRouter()

ALLOWED_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/png",
    "image/tiff",
    "image/webp",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}
MAX_SIZE_MB = 20


def _to_decimal(value) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError):
        return None


async def _process_invoice(invoice_id: str, file_bytes: bytes, mime_type: str):
    """Tâche de fond : extraction Gemini + mise à jour DB."""
    from app.core.database import AsyncSessionLocal
    from sqlalchemy import select

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Invoice).where(Invoice.id == invoice_id))
        invoice = result.scalar_one_or_none()
        if not invoice:
            logger.error("Invoice %s introuvable pour traitement", invoice_id)
            return

        try:
            invoice.status = "processing"
            await db.commit()

            # ── Pipeline LangGraph : Agent Parse (+ retry) → Agent Validation ──
            graph_state = run_invoice_pipeline(file_bytes, mime_type)

            if graph_state.get("extracted") is None:
                raise RuntimeError(graph_state.get("error") or "Échec extraction sans message")

            data = graph_state["extracted"]

            # ── Mise à jour des champs Invoice ────────────────────────────────
            invoice.language        = data.get("language", "unknown")
            invoice.invoice_number  = data.get("invoice_number")
            invoice.currency        = data.get("currency", "TND")
            invoice.jurisdiction    = data.get("jurisdiction", "TN")
            invoice.amount_ht       = _to_decimal(data.get("amount_ht"))
            invoice.amount_tva      = _to_decimal(data.get("amount_tva"))
            invoice.amount_ttc      = _to_decimal(data.get("amount_ttc"))
            invoice.tva_rate        = _to_decimal(data.get("tva_rate"))
            invoice.timbre_fiscal   = _to_decimal(data.get("timbre_fiscal")) or Decimal("0")
            invoice.ocr_confidence  = _to_decimal(data.get("confidence"))
            invoice.structured_data = data

            # Dates
            for field, key in [("invoice_date", "invoice_date"), ("due_date", "due_date")]:
                raw_date = data.get(key)
                if raw_date:
                    try:
                        setattr(invoice, field, datetime.fromisoformat(raw_date).replace(tzinfo=timezone.utc))
                    except ValueError:
                        pass

            # ── Vendor ────────────────────────────────────────────────────────
            vendor_data = data.get("vendor") or {}
            vendor_name = vendor_data.get("name")
            if vendor_name:
                res = await db.execute(
                    select(Vendor).where(Vendor.name == vendor_name)
                )
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

            # ── Line items ────────────────────────────────────────────────────
            for item in data.get("line_items") or []:
                line = LineItem(
                    id=uuid.uuid4(),
                    invoice_id=invoice.id,
                    line_number=item.get("line_number"),
                    description=item.get("description"),
                    quantity=_to_decimal(item.get("quantity")),
                    unit_price=_to_decimal(item.get("unit_price")),
                    tva_rate=_to_decimal(item.get("tva_rate")),
                    amount_ht=_to_decimal(item.get("amount_ht")),
                    amount_ttc=_to_decimal(item.get("amount_ttc")),
                )
                db.add(line)

            invoice.processed_at      = datetime.now(timezone.utc)
            invoice.validation_status = graph_state.get("validation_status")
            invoice.validation_delta  = graph_state.get("validation_delta")
            invoice.status = "anomaly" if graph_state.get("validation_status") == "mismatch" else "validated"
            invoice.processing_log = [{
                "step":              "langgraph_pipeline",
                "ocr_method":        data.get("_ocr_method"),
                "ocr_confidence":    data.get("_ocr_confidence"),
                "parse_attempts":    graph_state.get("attempt"),
                "validation_status": graph_state.get("validation_status"),
                "validation_reason": graph_state.get("validation_reason"),
            }]
            await db.commit()
            logger.info("Facture %s traitée (méthode=%s, tentatives=%d, validation=%s)",
                        invoice_id, data.get("_ocr_method"), graph_state.get("attempt"),
                        graph_state.get("validation_status"))

        except Exception as exc:
            logger.exception("Erreur pipeline facture %s : %s", invoice_id, exc)
            invoice.status = "anomaly"
            invoice.processing_log = [{"step": "langgraph_pipeline", "status": "error", "error": str(exc)}]
            await db.commit()


@router.post("/", status_code=201)
async def upload_invoice(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    # Validation type MIME
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(status_code=415, detail=f"Type non supporté : {file.content_type}")

    file_bytes = await file.read()

    # Validation taille
    size_mb = len(file_bytes) / (1024 * 1024)
    if size_mb > MAX_SIZE_MB:
        raise HTTPException(status_code=413, detail=f"Fichier trop grand : {size_mb:.1f} MB (max {MAX_SIZE_MB} MB)")

    # Upload MinIO
    minio_path = storage.upload_file(file_bytes, file.filename, file.content_type)

    # Enregistrement en DB
    invoice = Invoice(
        id=uuid.uuid4(),
        original_filename=file.filename,
        minio_path=minio_path,
        file_size_bytes=len(file_bytes),
        mime_type=file.content_type,
        status="pending",
    )
    db.add(invoice)
    await db.commit()
    await db.refresh(invoice)

    # Lancement extraction Gemini en arrière-plan
    background_tasks.add_task(
        _process_invoice,
        str(invoice.id),
        file_bytes,
        file.content_type,
    )

    return {
        "invoice_id": str(invoice.id),
        "filename":   invoice.original_filename,
        "status":     invoice.status,
        "minio_path": invoice.minio_path,
        "message":    "Extraction Gemini lancée en arrière-plan",
    }
