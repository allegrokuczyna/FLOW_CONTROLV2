from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from typing import List
from datetime import date, datetime
from fastapi.encoders import jsonable_encoder
from typing import Optional

from app.db.database import get_db
from app.db.models import WorkExport, WorkerPerformance, ActiveWork, User, AiReportLog, ForecastIntake, Schedule, ZoneConstraint
from app.db.schemas import UserCreate, UserResponse, Token, AssignmentSchema, AiRequest
from app.api.deps import get_current_user, get_current_admin
from app.core.security import verify_password, create_access_token
from app.services import users_service
from app.db.queries import get_replenishment_open_works, get_all_mezz_open_works, get_upcoming_forecast, get_inbound_works_mezz, get_multi_orders, get_one_open_pieces
from app.services.sync_service import (
    sync_works, 
    process_full_push_sync, 
    sync_active_works,
    get_workpool_analytics,
    get_daily_plan, 
    save_daily_plan,
    get_shift_number,
    get_all_constraints,
    update_or_create_constraints,
    get_weekly_schedule
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
    Z globalnym prefiksem adres to: /api/sync/full_push
    """
    try:
        
        result = await process_full_push_sync(payload, db)
        return {"status": "success", "details": result}
    except Exception as e:
        # Logujemy błąd
        print(f"❌ Critical Sync Error: {str(e)}")
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


@router.get("/sync/inspect_d365")
async def inspect_d365_fields():
    """Tymczasowy endpoint do podglądu dostępnych kolumn w D365."""
    from app.services.sync_service import get_data
    endpoint = "WarehouseWorkHeaders?cross-company=true&$top=1"
    works_data = await get_data(endpoint)
    
    if not works_data or len(works_data) == 0:
        return {"status": "error", "message": "Nie udało się pobrać żadnych danych z D365."}
        
    sample_record = works_data[0]
    available_columns = list(sample_record.keys())
    available_columns.sort()
    
    return {
        "status": "success", 
        "total_columns": len(available_columns),
        "columns": available_columns,
        "sample_data": sample_record 
    }


@router.get("/works/live")
async def get_live_active_works(
    db: AsyncSession = Depends(get_db), 
    _user: User = Depends(get_current_user)
):
    """Pobiera pełną listę aktywnych prac posortowaną od najwyższego priorytetu."""
    stmt = select(ActiveWork).order_by(ActiveWork.workpriority.desc())
    result = await db.execute(stmt)
    active_works = result.scalars().all()

    return {
        "status": "success",
        "total_count": len(active_works),
        "data": jsonable_encoder(active_works) 
    }


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
    
@router.get("/works/inbound-mezz")
async def get_inbound_mezz_query(db: AsyncSession = Depends(get_db), _user: User = Depends(get_current_user)):
    try:
        result = await get_inbound_works_mezz(db)
        data = [{
            "order": row.ordernum,
            "workid": row.workid,
            "qty": row.whasalesitemqty
        } for row in result]

        return {"status": "success", "count": len(data), "result": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/works/multi-orders")
async def get_multi_orders_query(db: AsyncSession = Depends(get_db), _user: User = Depends(get_current_user)):
    try:
        result = await get_multi_orders(db)
        data = [{
            "order": row.ordernum,
            "workid": row.workid,
            "qty": row.whasalesitemqty,
            "workpool_id": row.workpoolid,
            "work_status": row.workstatus
        } for row in result]
        return {"status": "success", "count": len(data), "result": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/works/single-orders")
async def get_single_orders_query(db: AsyncSession = Depends(get_db), _user: User = Depends(get_current_user)):
    try:
        result = await get_one_open_pieces(db)
        data = [{
            "order": row.ordernum,
            "workpool": row.workpoolid,
            "qty": row.whasalesitemqty,
            "work_status": row.workstatus
        } for row in result]
        return {"status": "success", "count": len(data), "result": data}
    except Exception as e:
        raise HTTPException (status_code=500, detail=str(e))

@router.get("/works/forecast_upcoming")
async def get_upcoming_intake(db: AsyncSession = Depends(get_db)):
    """Zwraca prognozowany spływ (Forecast) na najbliższe 2h."""
    data = await get_upcoming_forecast(db)
    return {"status": "success", "count": len(data), "data": data}

# --- KONFIGURACJA AI (CONSTRAINTS) ---

@router.get("/settings/constraints") # <-- Skróć ścieżkę tutaj
async def read_constraints(db: AsyncSession = Depends(get_db)):
    """Pobiera parametry MIN/MAX i Priorytety dla AI z Postgresa."""
    try:
        # Wywołujemy funkcję z serwisu (którą poprawiliśmy wcześniej)
        constraints = await get_all_constraints(db) 
        return constraints
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/settings/constraints") 
async def save_constraints(data: list[dict], db: AsyncSession = Depends(get_db)):
    """Zapisuje konfigurację stref."""
    try:
        # Używamy poprawionej funkcji z UPSERT
        await update_or_create_constraints(db, data)
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ==============================================================================
# --- 5. ANALITYKA I PRODUKTYWNOŚĆ ---
# ==============================================================================

@router.get("/plan/workers/{shift_id}")
async def get_workers_for_shift(
    shift_id: str, 
    target_date: date = None, 
    db: AsyncSession = Depends(get_db)
):
    """
    Pobiera pracowników i filtruje ich po zmianie (1, 2 lub 3).
    Używamy str() aby uniknąć błędów porównywania int vs string.
    """
    if target_date is None:
        target_date = date.today()
    
    # Pobieramy wszystkich pracowników na dany dzień
    daily_plan = await get_daily_plan(db, target_date)
    
    if shift_id.lower() == "all":
        return daily_plan
        
    # FILTRACJA: Porównujemy shift_id z wynikiem funkcji get_shift_number zapisanym w daily_plan
    filtered_plan = [
        worker for worker in daily_plan 
        if str(worker.get("shift")) == str(shift_id)
    ]
    
    print(f"DEBUG: Data {target_date}, Zmiana {shift_id}, Znaleziono: {len(filtered_plan)} osób")
    return filtered_plan


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
    from app.services.ai_service import generate_ai_assignments
    
    shift_id = str(req.shift)
    parsed_date = None
    
    # Bezpieczna konwersja stringa na datę
    if req.target_date:
        try:
            parsed_date = datetime.strptime(req.target_date, "%Y-%m-%d").date()
        except ValueError:
            parsed_date = None # W razie dziwnego formatu, AI weźmie "dzisiaj"
            
    # Przekazujemy gotową datę do serwisu
    return await generate_ai_assignments(db, shift_id=shift_id, target_date=parsed_date)

@router.post("/plan/save")
async def save_plan(
    assignments: List[AssignmentSchema], 
    target_date: Optional[date] = None, # <--- Odbieramy datę z URL
    db: AsyncSession = Depends(get_db)
):
    from app.services.sync_service import save_daily_plan
    data = [a.dict() for a in assignments]
    return await save_daily_plan(data, db, target_date=target_date)


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
    daily_plan = await get_daily_plan(db, target_date)
    if shift_id.lower() == "all":
        return daily_plan
    filtered_plan = [worker for worker in daily_plan if str(worker.get("shift")) == str(shift_id)]
    return filtered_plan


@router.get("/ai/manager_report/history")
async def get_ai_report_history(
    limit: int = 10,
    db: AsyncSession = Depends(get_db), 
    _user: User = Depends(get_current_user)
):
    """Pobiera historię wygenerowanych raportów AI."""
    stmt = select(AiReportLog).order_by(AiReportLog.id.desc()).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()

@router.get("/plan/weekly")
async def get_weekly_schedule_api(db: AsyncSession = Depends(get_db)):
    """Pobiera pełną macierz grafiku na najbliższe 7 dni."""
    from app.services.sync_service import get_weekly_schedule
    return await get_weekly_schedule(db)