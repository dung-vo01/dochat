from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.chroma import get_collection
from app.db.session import get_db

router = APIRouter(tags=["health"])


@router.get("/health")
async def health(db: AsyncSession = Depends(get_db)):
    """Readiness probe: can we reach Postgres and the vector store?"""
    try:
        await db.execute(text("SELECT 1"))
        get_collection().count()
    except Exception as e:  # noqa: BLE001 - report instead of crashing
        raise HTTPException(status_code=503, detail=f"unhealthy: {type(e).__name__}")
    return {"status": "ok"}
