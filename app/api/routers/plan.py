from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from datetime import date
from sqlalchemy import func, select, text
import asyncio
import sys
import selectors
from contextlib import asynccontextmanager


from app.db.database import get_db
from app.db.models import User, Schedule, ShiftAssignment # <-- TUTAJ: Dodano wymagane modele
from app.db.schemas import AssignmentSchema, DailyConstraintsSave, PresenceUpdate
from app.api.deps import get_current_user
from app.services.sync_service import (
    get_daily_plan, save_daily_plan, get_weekly_schedule, 
    get_all_constraints, update_or_create_constraints, ForecastIntake
)
from app.db.queries import get_active_workers, get_inactive_workers

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
# ║ 👥 OBSADA PRACOWNICZA DLA ZMIANY                                       ║
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
# ║ BOARD PODLGAD                          
# ╚════════════════════════════════════════════════════════════════════════╝
@router.get("/plan/tv-board")
async def get_tv_board_data(target_date: date = None, db: AsyncSession = Depends(get_db)):
    """
    Zwraca listę obecnych pracowników (odbitych na bramce) wraz z przypisaną 
    przez kierownika strefą z Drag&Drop, gotową do wyświetlenia na ekranie TV.
    """
    if target_date is None:
        target_date = date.today()
        

    stmt = select(Schedule, ShiftAssignment).outerjoin(
        ShiftAssignment,
        (Schedule.login == ShiftAssignment.worker_login) & 
        (Schedule.work_date == ShiftAssignment.assignment_date)
    ).where(
        Schedule.work_date == target_date,
        Schedule.is_present == True
    )
    
    result = await db.execute(stmt)
    rows = result.all()
    
    response_data = []
    for schedule_obj, assignment_obj in rows:
        
        
        assigned_task = assignment_obj.task if assignment_obj else "unassigned"
        
        response_data.append({
            "login": schedule_obj.login,
            "full_name": schedule_obj.full_name or "Pracownik",
            "task": assigned_task,
            "shift": schedule_obj.planned_shift
        })
        
    return response_data


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
    """Pobiera parametry MIN/MAX z Postgresa DLA KONKRETNEGO DNIA."""
    try:
        d = date.fromisoformat(target_date)
        constraints = await get_all_constraints(db, d) 
        return constraints
    except ValueError:
        raise HTTPException(status_code=400, detail="Nieprawidłowy format daty. Użyj YYYY-MM-DD.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/settings/constraints") 
async def save_constraints(payload: DailyConstraintsSave, db: AsyncSession = Depends(get_db)):
    """Zapisuje konfigurację stref na dany dzień."""
    try:
        await update_or_create_constraints(db, payload.target_date, payload.constraints)
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    


# ╔════════════════════════════════════════════════════════════════════════╗
# ║ Obecnosc na magazynie
# ╚════════════════════════════════════════════════════════════════════════╝



@router.post("/plan/update-presence")
async def update_worker_presence(payload: PresenceUpdate, db: AsyncSession = Depends(get_db)):
    """zmiana obecnosci pracownika w magazynie"""

    try:
        stmt = text("""
                    UPDATE schedules
                    SET is_present = :is_present
                    WHERE login = :login AND work_date = CURRENT_DATE
                    """)
        result = await db.execute(stmt, {"is_present": payload.is_present, "login": payload.login})
        await db.commit()


    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    


@router.get("/plan/active-workers")
async def get_active_workers_query(target_date: date = None, db: AsyncSession = Depends(get_db)):
    """Pobiera listę pracowników obecnych na magazynie wraz z ich sumą."""
    if target_date is None:
        target_date = date.today()
        
    try:
        workers_list = await get_active_workers(db, target_date)
        
        return {
            "count": len(workers_list),
            "workers": workers_list
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    


@router.get("/plan/inactive-workers")
async def get_inactive_workers_query(target_date: date = None, db: AsyncSession = Depends(get_db)):
    """Pobiera listę pracowników nieobecnych na magazynie wraz z ich sumą."""
    if target_date is None:
        target_date = date.today()
        
    try:
        workers_list = await get_inactive_workers(db, target_date)
        
        return {
            "count": len(workers_list),
            "workers": workers_list
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    