from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.services import metrics

router = APIRouter(prefix="/api/metrics", tags=["metrics"])


@router.get("/summary")
async def metrics_summary_api(
    hours: int = Query(24, ge=1, le=24 * 30),
    source: str = Query("app", pattern="^(app|eval)$"),
    db: AsyncSession = Depends(get_db),
):
    return await metrics.summary(db, hours=hours, source=source)


@router.get("/recent")
async def metrics_recent_api(
    limit: int = Query(20, ge=1, le=100),
    source: str = Query("app", pattern="^(app|eval)$"),
    db: AsyncSession = Depends(get_db),
):
    return await metrics.recent(db, limit=limit, source=source)
