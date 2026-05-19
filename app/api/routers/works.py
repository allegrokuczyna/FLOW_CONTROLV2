from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi.encoders import jsonable_encoder

from app.db.database import get_db
from app.db.models import ActiveWork, User
from app.api.deps import get_current_user
from app.db.queries import (
    get_replenishment_open_works
)

# PREFIX: Automatycznie dodaje /works przed każdym endpointem
router = APIRouter(prefix="/works", tags=["Zadania Magazynowe i Filtry"])

# ╔════════════════════════════════════════════════════════════════════════╗
# ║ 📋 WSZYSTKIE AKTYWNE PRACE                                             ║
# ╚════════════════════════════════════════════════════════════════════════╝
@router.get("/live")
async def get_live_active_works(db: AsyncSession = Depends(get_db), _user: User = Depends(get_current_user)):
    """Pobiera pełną listę aktywnych prac posortowaną od najwyższego priorytetu."""
    stmt = select(ActiveWork).order_by(ActiveWork.workpriority.desc())
    result = await db.execute(stmt)
    active_works = result.scalars().all()
    return {"status": "success", "total_count": len(active_works), "data": jsonable_encoder(active_works)}

