from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.models import Anomaly, Invoice

router = APIRouter()


@router.get("/")
async def dashboard_summary(db: AsyncSession = Depends(get_db)):
    """Statistiques globales pour le dashboard."""

    # Total factures par statut
    status_counts = await db.execute(
        select(Invoice.status, func.count(Invoice.id))
        .group_by(Invoice.status)
    )
    by_status = {row[0]: row[1] for row in status_counts}

    # Montant total TTC validé
    total_ttc = await db.execute(
        select(func.sum(Invoice.amount_ttc))
        .where(Invoice.status.in_(["validated", "reconciled"]))
    )
    total_amount = total_ttc.scalar() or 0

    # Anomalies non résolues
    open_anomalies = await db.execute(
        select(func.count(Anomaly.id)).where(Anomaly.is_resolved == False)
    )

    return {
        "invoices_by_status":   by_status,
        "total_amount_ttc":     float(total_amount),
        "open_anomalies":       open_anomalies.scalar() or 0,
    }
