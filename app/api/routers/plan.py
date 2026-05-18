from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from datetime import date

from app.db.database import get_db
from app.db.models import User
from app.db.schemas import AssignmentSchema, DailyConstraintsSave
from app.api.deps import get_current_user
from app.services.sync_service import (
    get_daily_plan, save_daily_plan, get_weekly_schedule, 
    get_all_constraints, update_or_create_constraints
)

router = APIRouter(tags=["Planowanie i Konfiguracja (Constraints)"])

# ╔════════════════════════════════════════════════════════════════════════╗
# ║ 📅 GRAFIK DZIENNY I TYGODNIOWY                                         ║
# ╚════════════════════════════════════════════════════════════════════════╝
@router.get("/plan/daily")
async def get_daily_schedule(target_date: date = None, db: AsyncSession = Depends(get_db), _user: User = Depends(get_current_user)):
    """Zwraca plan przydziałów (grafik) na wybrany dzień. Domyślnie na dzisiaj."""
    return await get_daily_plan(db, target_date)

@router.get("/plan/weekly")
async def get_weekly_schedule_api(db: AsyncSession = Depends(get_db)):
    """Pobiera pełną macierz grafiku na najbliższe 7 dni."""
    return await get_weekly_schedule(db)

# ╔════════════════════════════════════════════════════════════════════════╗
# ║ 👥 OBSADA PRACOWNICZA DLA ZMIANY             ║
# ╚════════════════════════════════════════════════════════════════════════╝
@router.get("/plan/workers/{shift_id}")
async def get_workers_for_shift(shift_id: str, target_date: date = None, db: AsyncSession = Depends(get_db)):
    """Pobiera pracowników i filtruje ich po zmianie (1, 2, 3 lub 'all')."""
    if target_date is None:
        target_date = date.today()
    
    daily_plan = await get_daily_plan(db, target_date)
    
    if shift_id.lower() == "all":
        return daily_plan
        
    filtered_plan = [worker for worker in daily_plan if str(worker.get("shift")) == str(shift_id)]
    return filtered_plan

# ╔════════════════════════════════════════════════════════════════════════╗
# ║ 💾 ZAPIS PRZYDZIAŁÓW (GRAFIKU)                                         ║
# ╚════════════════════════════════════════════════════════════════════════╝
@router.post("/plan/save")
async def save_plan(
    assignments: List[AssignmentSchema], 
    target_date: Optional[date] = None,
    db: AsyncSession = Depends(get_db)
):
    """Zapisuje przydziały ludzi do stref zrobione przez Managera / AI."""
    data = [a.dict() for a in assignments]
    return await save_daily_plan(data, db, target_date=target_date)

# ╔════════════════════════════════════════════════════════════════════════╗
# ║ ⚙️ POBIERANIE I ZAPIS LIMITÓW AI (CONSTRAINTS MANAGER)                 ║
# ╚════════════════════════════════════════════════════════════════════════╝
@router.get("/settings/constraints/{target_date}")
async def read_constraints(target_date: str, db: AsyncSession = Depends(get_db)):
    """Pobiera parametry MIN/MAX. Ignoruje target_date dla bazy, bo limity są globalne."""
    try:
        
        date.fromisoformat(target_date)
        
       
        constraints = await get_all_constraints(db) 
        return constraints
    except ValueError:
        raise HTTPException(status_code=400, detail="Nieprawidłowy format daty. Użyj YYYY-MM-DD.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/settings/constraints") 
async def save_constraints(payload: DailyConstraintsSave, db: AsyncSession = Depends(get_db)):
    """Zapisuje konfigurację stref. Ignoruje payload.target_date dla bazy."""
    try:
    
        await update_or_create_constraints(db, payload.constraints)
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))