from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.models import Invoice
from app.services.storage import download_file, get_presigned_url

router = APIRouter()


@router.get("/")
async def list_invoices(
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    q = (
        select(Invoice)
        .options(selectinload(Invoice.vendor), selectinload(Invoice.line_items))
        .order_by(Invoice.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    if status:
        q = q.where(Invoice.status == status)
    result = await db.execute(q)
    invoices = result.scalars().all()
    return [_serialize(inv) for inv in invoices]


@router.get("/{invoice_id}")
async def get_invoice(invoice_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Invoice)
        .options(selectinload(Invoice.vendor), selectinload(Invoice.line_items))
        .where(Invoice.id == invoice_id)
    )
    invoice = result.scalar_one_or_none()
    if not invoice:
        raise HTTPException(status_code=404, detail="Facture introuvable")
    data = _serialize(invoice)
    data["file_url"] = get_presigned_url(invoice.minio_path)
    return data


@router.post("/{invoice_id}/process")
async def reprocess_invoice(
    invoice_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Relance l'extraction Gemini sur une facture existante (ex: après anomalie)."""
    result = await db.execute(select(Invoice).where(Invoice.id == invoice_id))
    invoice = result.scalar_one_or_none()
    if not invoice:
        raise HTTPException(status_code=404, detail="Facture introuvable")
    if invoice.status == "processing":
        raise HTTPException(status_code=409, detail="Traitement déjà en cours")

    file_bytes = download_file(invoice.minio_path)

    from app.api.routes.upload import _process_invoice
    background_tasks.add_task(_process_invoice, invoice_id, file_bytes, invoice.mime_type)

    return {"invoice_id": invoice_id, "status": "processing", "message": "Retraitement Gemini lancé"}


def _serialize(inv: Invoice) -> dict:
    vendor = inv.vendor
    line_items = [
        {
            "id":          str(li.id),
            "line_number": li.line_number,
            "description": li.description,
            "quantity":    float(li.quantity)   if li.quantity   else None,
            "unit_price":  float(li.unit_price) if li.unit_price else None,
            "tva_rate":    float(li.tva_rate)   if li.tva_rate   else None,
            "amount_ht":   float(li.amount_ht)  if li.amount_ht  else None,
            "amount_ttc":  float(li.amount_ttc) if li.amount_ttc else None,
        }
        for li in (inv.line_items or [])
    ]
    return {
        # ── Identité ──────────────────────────────────────────────────────────
        "id":               str(inv.id),
        "filename":         inv.original_filename,
        "mime_type":        inv.mime_type,
        "file_size_bytes":  inv.file_size_bytes,
        "minio_path":       inv.minio_path,
        "status":           inv.status,

        # ── Champs extraits ───────────────────────────────────────────────────
        "language":         inv.language,
        "invoice_number":   inv.invoice_number,
        "invoice_date":     inv.invoice_date.isoformat() if inv.invoice_date else None,
        "due_date":         inv.due_date.isoformat()     if inv.due_date     else None,
        "currency":         inv.currency,
        "jurisdiction":     inv.jurisdiction,

        # ── Montants ──────────────────────────────────────────────────────────
        "amount_ht":        float(inv.amount_ht)       if inv.amount_ht       else None,
        "amount_tva":       float(inv.amount_tva)      if inv.amount_tva      else None,
        "amount_ttc":       float(inv.amount_ttc)      if inv.amount_ttc      else None,
        "tva_rate":         float(inv.tva_rate)        if inv.tva_rate        else None,
        "timbre_fiscal":    float(inv.timbre_fiscal)   if inv.timbre_fiscal   else None,

        # ── Validation ────────────────────────────────────────────────────────
        "validation_status": inv.validation_status,
        "validation_delta":  float(inv.validation_delta) if inv.validation_delta else None,

        # ── Vendor ────────────────────────────────────────────────────────────
        "vendor_id":        str(inv.vendor_id) if inv.vendor_id else None,
        "vendor_name":      vendor.name          if vendor else None,
        "vendor_tax_id":    vendor.tax_id        if vendor else None,
        "vendor_address":   vendor.address       if vendor else None,
        "vendor_country":   vendor.country       if vendor else None,
        "vendor_email":     vendor.email         if vendor else None,
        "vendor_phone":     vendor.phone         if vendor else None,
        "vendor_is_known":  vendor.is_known      if vendor else None,

        # ── Line items ────────────────────────────────────────────────────────
        "line_items":       line_items,

        # ── OCR & Pipeline ────────────────────────────────────────────────────
        "confidence":       float(inv.ocr_confidence) if inv.ocr_confidence else None,
        "raw_text":         inv.raw_text,
        "structured_data":  inv.structured_data,
        "processing_log":   inv.processing_log,

        # ── Dates système ─────────────────────────────────────────────────────
        "uploaded_at":      inv.uploaded_at.isoformat(),
        "processed_at":     inv.processed_at.isoformat() if inv.processed_at else None,
        "updated_at":       inv.updated_at.isoformat()   if inv.updated_at   else None,
    }
