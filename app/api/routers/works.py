from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi.encoders import jsonable_encoder

from app.db.database import get_db
from app.db.models import ActiveWork, User
from app.api.deps import get_current_user
from app.db.queries import (
    get_replenishment_open_works,
    get_sorting_open_works,
    get_active_inbound_works,
    get_zone_pick_open_works,
    get_multi_zone_pick_open_works
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


# ╔════════════════════════════════════════════════════════════════════════╗
# ║ 📋 prace dax
# ╚════════════════════════════════════════════════════════════════════════╝


@router.get("/replenishment/open")
async def get_open_replenishment_works(db: AsyncSession = Depends(get_db)):
    """pobieranie otwartych prac uzupelnieñ"""
    try:
        works = await get_replenishment_open_works(db)
        return {"status": "success", "total_count": len(works), "data": jsonable_encoder(works)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



@router.get("/sorting/open")
async def get_open_sort_works(db: AsyncSession = Depends(get_db)):
    """pobieranie otwartych prac sortowania"""
    try:
        works = await get_sorting_open_works(db)
        return {"status": "success", "total_count": len(works), "data": jsonable_encoder(works)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    


@router.get("/inbound/inprocess")
async def get_open_inbound_works(db: AsyncSession = Depends(get_db)):
    """pobieranie otwartych prac przyjęć (inbound)"""
    try:
        works = await get_active_inbound_works(db)
        return {"status": "success", "total_count": len(works), "data": jsonable_encoder(works)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/zonepick/open")
async def get_open_zone_pick_works(db: AsyncSession = Depends(get_db)):
    """pobieranie otwartych prac zone picking"""
    try:
        works = await get_zone_pick_open_works(db)
        return {"status": "success", "total_count": len(works), "data": jsonable_encoder(works)}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    


@router.get("/multizonepick/open")
async def get_open_multi_zone_works(db: AsyncSession = Depends(get_db)):
    """pobieranie otwartych prac multi zone picking"""
    try:
        works = await get_multi_zone_pick_open_works(db)
        return {"status": "success", "total_count": len(works), "data": jsonable_encoder(works)}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))