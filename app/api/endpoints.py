from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
from datetime import date

from app.db.database import get_db
from app.db.models import WorkExport, WorkerPerformance, ActiveWork, User, AiReportLog
from app.db.schemas import UserCreate, UserResponse, Token, AssignmentSchema, AiRequest
from app.api.deps import get_current_user, get_current_admin
from app.core.security import verify_password, create_access_token
from app.services import users_service
from app.services.sync_service import (
    sync_works, 
    process_full_system_sync, 
    sync_active_works,
    get_workpool_analytics,
    get_daily_plan, 
    save_daily_plan
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
# --- 3. SYNCHRONIZACJA DANYCH (GOOGLE SHEETS & D365) ---
# ==============================================================================

@router.post("/sync/full_system/")
async def full_system_sync(payload: dict, db: AsyncSession = Depends(get_db)):
    """Odbiera paczkę danych z Google Sheets (Grafik + Matryca Skilli)."""
    return await process_full_system_sync(payload, db)

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
    """Odświeża bieżący stan prac (Open/InProcess) - Live Sync."""
    try:
        await sync_active_works(db)
        return {"status": "success", "message": "Stan aktywnych prac odświeżony."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==============================================================================
# --- 4. ANALITYKA I DANE OPERACYJNE ---
# ==============================================================================

@router.get("/active_data")
async def get_active_work_data(db: AsyncSession = Depends(get_db), _user: User = Depends(get_current_user)):
    """Pobiera surową listę aktywnych prac z bazy."""
    result = await db.execute(select(ActiveWork))
    return result.scalars().all()

@router.get("/productivity")
async def get_worker_performance(db: AsyncSession = Depends(get_db), _user: User = Depends(get_current_user)):
    """Pobiera dane o wydajności/skillach wszystkich pracowników."""
    result = await db.execute(select(WorkerPerformance))
    return result.scalars().all()

@router.get("/analytics/workpools")
async def get_workpool_stats(db: AsyncSession = Depends(get_db), _user: User = Depends(get_current_user)):
    """Zwraca statystyki obciążenia stref (Picking, Packing itp.)."""
    try:
        data = await get_workpool_analytics(db)
        return {
            "status": "success",
            "timestamp": date.today().isoformat(),
            "workpools": data
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==============================================================================
# --- 5. AI STRATEGIA I LOGI ---
# ==============================================================================

@router.get("/ai/manager_report/history")
async def get_ai_report_history(db: AsyncSession = Depends(get_db), _user: User = Depends(get_current_user)):
    """Zwraca ostatnie 10 porad wygenerowanych przez AI."""
    result = await db.execute(
        select(AiReportLog).order_by(AiReportLog.created_at.desc()).limit(10)
    )
    return result.scalars().all()

@router.get("/ai/manager_report")
async def get_ai_report(db: AsyncSession = Depends(get_db), _user: User = Depends(get_current_user)):
    """Generuje nową analizę strategiczną AI i zapisuje log (kto wywołał)."""
    from app.services.ai_service import get_ai_warehouse_advice
    return await get_ai_warehouse_advice(db, username=_user.username)


# ==============================================================================
# --- 6. PLANOWANIE ZMIANY I PRZYDZIAŁY ---
# ==============================================================================

@router.post("/plan/ai_suggest")
async def suggest_plan(req: AiRequest, db: AsyncSession = Depends(get_db)):
    """Generuje automatyczny plan przydziałów pracowników dla danej zmiany."""
    from app.services.ai_service import generate_ai_assignments
    return await generate_ai_assignments(db, shift_id=req.shift)

@router.get("/plan/workers/{shift}")
async def get_workers_endpoint(shift: str, db: AsyncSession = Depends(get_db)):
    """Pobiera listę pracowników zaplanowanych na daną zmianę (lub 'all')."""
    try:
        full_plan = await get_daily_plan(db)
        if shift != 'all':
            full_plan = [w for w in full_plan if w['shift'] == shift]
        return full_plan
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/plan/save")
async def save_assignments_endpoint(assignments: List[AssignmentSchema], db: AsyncSession = Depends(get_db)):
    """Zapisuje ręczne lub wygenerowane przez AI przydziały do bazy."""
    try:
        data_dicts = [{"worker_login": a.worker_login, "shift": a.shift, "task": a.task} for a in assignments]
        result = await save_daily_plan(data_dicts, db)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))