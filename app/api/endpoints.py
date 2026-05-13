from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from typing import List
from datetime import date, datetime

from app.db.database import get_db
from app.db.models import WorkExport, WorkerPerformance, ActiveWork, User, AiReportLog, ForecastIntake, Schedule
from app.db.schemas import UserCreate, UserResponse, Token, AssignmentSchema, AiRequest
from app.api.deps import get_current_user, get_current_admin
from app.core.security import verify_password, create_access_token
from app.services import users_service
from app.db.queries import get_replenishment_open_works, get_all_mezz_open_works, get_upcoming_forecast
from app.services.sync_service import (
    sync_works, 
    process_full_push_sync,  # <--- Zmieniono z PULL na PUSH
    sync_active_works,
    get_workpool_analytics,
    get_daily_plan, 
    save_daily_plan,
    get_shift_number
)

router = APIRouter()

# ==============================================================================
# --- 1. AUTORYZACJA I LOGOWANIE ---
# ==============================================================================

@router.post("/auth/login", response_model=Token)
async def login_for_access_token(
    db: AsyncSession = Depends(get_db),
    form_data: OAuth2PasswordRequestForm = Depends()
):
    """Wydaje token JWT po weryfikacji loginu i hasła."""
    result = await db.execute(select(User).where(User.username == form_data.username))
    user = result.scalar_one_or_none()
    
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Niepoprawny login lub hasło",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token = create_access_token(data={"sub": user.username})
    return {"access_token": access_token, "token_type": "bearer"}


# ==============================================================================
# --- 2. ZARZĄDZANIE UŻYTKOWNIKAMI ---
# ==============================================================================

@router.get("/users/me", response_model=UserResponse)
async def read_users_me(current_user: User = Depends(get_current_user)):
    """Zwraca profil aktualnie zalogowanego użytkownika."""
    return current_user

@router.post("/users/register", response_model=UserResponse)
async def register_new_user(
    user_data: UserCreate, 
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(get_current_admin)
):
    """Rejestracja nowego użytkownika - dostępna tylko dla ADMINA."""
    return await users_service.register_new_user(db, user_data)


# ==============================================================================
# --- 3. SYNCHRONIZACJA DANYCH (MODEL PUSH - PRZEZ NGROK) ---
# ==============================================================================

@router.post("/sync/full_push")
async def trigger_full_push(payload: dict, db: AsyncSession = Depends(get_db)):
    """
    Główny endpoint dla Apps Script. Przyjmuje paczkę: Matryca, Grafik i Forecast.
    Zamiast bić się z uprawnieniami Google, przyjmujemy to co wyśle nam skrypt.
    """
    try:
        result = await process_full_push_sync(payload, db)
        return {"status": "success", "details": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Błąd synchronizacji PUSH: {str(e)}")

@router.post("/sync/works")
async def trigger_sync_works(db: AsyncSession = Depends(get_db), _admin: User = Depends(get_current_admin)):
    """Pobiera i archiwizuje otwarte prace z D365 (ADM-01)."""
    try:
        await sync_works(db)
        return {"status": "success", "message": "Archiwum prac zaktualizowane."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/sync/active_status")
async def trigger_active_sync(db: AsyncSession = Depends(get_db), _admin: User = Depends(get_current_admin)):
    """Odświeża bieżący stan prac (Open/InProcess) - Live Sync z D365."""
    try:
        await sync_active_works(db)
        return {"status": "success", "message": "Stan aktywnych prac odświeżony."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==============================================================================
# --- 4. DANE OPERACYJNE I FILTRY (QUERIES) ---
# ==============================================================================

@router.get("/works/replenishments")
async def get_replenishments_query(db: AsyncSession = Depends(get_db), _user: User = Depends(get_current_user)):
    """Pobiera przefiltrowane prace uzupełnień (tylko Open)."""
    try:
        result = await get_replenishment_open_works(db)
        data = [{
            "priority": row.workpriority,
            "workid": row.workid,
            "workpool": row.workpoolid
        } for row in result]
        
        return {"status": "success", "count": len(data), "results": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/works/zone_pick")
async def get_zone_pick_query(db: AsyncSession = Depends(get_db), _user: User = Depends(get_current_user)):
    """Pobiera otwarte prace z mezaniny (Mezzanine Picking)."""
    try:
        result = await get_all_mezz_open_works(db)
        data = [{
            "order": row.ordernum,
            "workid": row.workid,
            "zone": row.whaadditionalzone2,
            "qty": row.whasalesitemqty,
            "carrier": row.whacarriercode,
            "priority": row.workpriority
        } for row in result]
        
        return {"status": "success", "count": len(data), "result": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/works/forecast_upcoming")
async def get_upcoming_intake(db: AsyncSession = Depends(get_db)):
    """Zwraca prognozowany spływ (Forecast) na najbliższe 2h."""
    data = await get_upcoming_forecast(db)
    return {"status": "success", "count": len(data), "data": data}


# ==============================================================================
# --- 5. ANALITYKA I PRODUKTYWNOŚĆ ---
# ==============================================================================

@router.get("/analytics/workpools")
async def get_workpool_stats(db: AsyncSession = Depends(get_db), _user: User = Depends(get_current_user)):
    """Statystyki obciążenia stref (AI dashboard)."""
    try:
        data = await get_workpool_analytics(db)
        return {
            "status": "success",
            "timestamp": date.today().isoformat(),
            "workpools": data
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/productivity")
async def get_worker_performance(db: AsyncSession = Depends(get_db), _user: User = Depends(get_current_user)):
    """Zwraca matrycę skilli wszystkich pracowników."""
    result = await db.execute(select(WorkerPerformance))
    return result.scalars().all()


# ==============================================================================
# --- 6. AI STRATEGIA I PLANOWANIE ---
# ==============================================================================

@router.get("/ai/manager_report")
async def get_ai_report(db: AsyncSession = Depends(get_db), _user: User = Depends(get_current_user)):
    """Generuje analizę strategiczną AI (Raport dla Managera)."""
    from app.services.ai_service import get_ai_warehouse_advice
    return await get_ai_warehouse_advice(db, username=_user.username)

@router.post("/plan/ai_suggest")
async def suggest_plan(req: AiRequest, db: AsyncSession = Depends(get_db)):
    """Generuje automatyczny plan przydziałów pracowników przez AI."""
    from app.services.ai_service import generate_ai_assignments
    return await generate_ai_assignments(db, shift_id=req.shift)

@router.post("/plan/save")
async def save_assignments_endpoint(assignments: List[AssignmentSchema], db: AsyncSession = Depends(get_db)):
    """Zapisuje przydziały (ręczne lub AI) do bazy danych."""
    try:
        data_dicts = [{"worker_login": a.worker_login, "shift": a.shift, "task": a.task} for a in assignments]
        return await save_daily_plan(data_dicts, db)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/plan/daily")
async def get_daily_schedule(
    target_date: date = None, 
    db: AsyncSession = Depends(get_db), 
    _user: User = Depends(get_current_user)
):
    """Zwraca plan przydziałów (grafik) na wybrany dzień. Domyślnie na dzisiaj."""
    return await get_daily_plan(db, target_date)

@router.get("/plan/workers/{shift_id}")
async def get_workers_for_shift(
    shift_id: str, 
    target_date: date = None, 
    db: AsyncSession = Depends(get_db), 
    _user: User = Depends(get_current_user)
):
    """Zwraca pracowników dla konkretnej zmiany (1, 2, 3) lub wszystkich ('all')."""
    
    # 1. Pobieramy cały plan na dany dzień (z matrycą skilli)
    daily_plan = await get_daily_plan(db, target_date)
    
    # 2. Jeśli frontend prosi o 'all', zwracamy wszystkich z tego dnia
    if shift_id.lower() == "all":
        return daily_plan
        
    # 3. Jeśli prosi o konkretną zmianę (np. '1', '2', '3'), filtrujemy listę
    filtered_plan = [worker for worker in daily_plan if str(worker.get("shift")) == str(shift_id)]
    
    return filtered_plan




# ==============================================================================
# --- DODATKOWE FUNKCJE POMOCNICZE (AI) ---
# ==============================================================================

async def is_worker_on_shift(login: str, shift_id: str, db: AsyncSession, target_date: date = None) -> bool:
    """
    Sprawdza, czy dany pracownik ma zaplanowaną konkretną zmianę danego dnia.
    Wykorzystywane głównie przez AI do filtrowania dostępnych rąk do pracy.
    """
    if target_date is None: 
        target_date = date.today()
        
    stmt = select(Schedule).where(Schedule.login == login, Schedule.work_date == target_date)
    result = await db.execute(stmt)
    sched = result.scalar_one_or_none()
    
    if not sched:
        return False
        
    # Pobieramy godziny z grafiku (np. "06-14") i zmieniamy na numer zmiany (1, 2 lub 3)
    actual_shift = get_shift_number(str(sched.planned_shift))
    
    # Zwraca True, jeśli numer zmiany w grafiku zgadza się z tą, o którą pyta AI
    return actual_shift == str(shift_id)


@router.get("/ai/manager_report/history")
async def get_ai_report_history(
    limit: int = 10,
    db: AsyncSession = Depends(get_db), 
    _user: User = Depends(get_current_user)
):
    """Pobiera historię wygenerowanych raportów AI (domyślnie 10 ostatnich)."""
    # Sortujemy malejąco po ID (najnowsze na górze) i ucinamy do 'limit'
    stmt = select(AiReportLog).order_by(AiReportLog.id.desc()).limit(limit)
    result = await db.execute(stmt)
    
    return result.scalars().all()