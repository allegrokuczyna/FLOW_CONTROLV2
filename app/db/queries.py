from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func
from app.db.models import ActiveWork, Schedule, WorkerPerformance, AiReportLog, ForecastIntake
from datetime import date, datetime, timedelta

# ==============================================================================
# SEKCJA: LOGOWANIE I HISTORIA RAPORTÓW AI
# ==============================================================================

async def save_ai_report_log(db: AsyncSession, username: str, workers_count: int, text: str):
    """Zapisuje raport AI do dziennika w bazie danych."""
    new_log = AiReportLog(
        username=username,
        workers_count=workers_count,
        report_text=text,
        created_at=datetime.now()
    )
    db.add(new_log)
    await db.commit()
    await db.refresh(new_log)
    return new_log

async def fetch_ai_report_logs(db: AsyncSession, limit: int = 10):
    """Pobiera ostatnie logi z raportami AI (od najnowszych)."""
    stmt = select(AiReportLog).order_by(AiReportLog.created_at.desc()).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()


# ==============================================================================
# SEKCJA: PRACE OPERACYJNE (D365 ACTIVE WORK)
# ==============================================================================

async def get_replenishment_open_works(db: AsyncSession):
    """Pobieranie otwartych prac uzupełnień (Replenishment)."""
    # Lista czystych nazw z Proda
    target_pools = [
        'u_adm-01_hv', 'u_adm-01_mez', 'u_adm-01_pw', 
        'u_adm-01_std', 'u_adm-01_kartony', 'u_adm-01_wyc'
    ]
    
    stmt = (
        select(ActiveWork)
        .where(
            func.lower(func.replace(ActiveWork.workpoolid, ' ', '')).in_(target_pools),
            ActiveWork.workstatus == 'Open'
        )
        .order_by(ActiveWork.workid)
    )

    result = await db.execute(stmt)
    return result.scalars().all()

async def get_all_mezz_open_works(db: AsyncSession):
    """Pobieranie otwartych prac kompletacji ze stref mezaniny (Zone picking)."""
    # Lista czystych nazw
    target_mez = ['jedn zp', 'wiel zp']

    stmt = (
        select(ActiveWork)
        .where(
            func.lower(func.replace(ActiveWork.workpoolid, ' ', '')).in_(target_mez),
            ActiveWork.workstatus == 'Open'
        )
        .order_by(ActiveWork.workid)
    )
    
    result = await db.execute(stmt)
    return result.scalars().all()


# ==============================================================================
# SEKCJA: PROGNOZY I PLANOWANIE (FORECAST)
# ==============================================================================

async def get_upcoming_forecast(db: AsyncSession, hours_ahead: int = 2):
    """
    Pobiera prognozowany spływ zamówień (Intake) na najbliższe X godzin.
    Używa połączonego pola forecast_from (DateTime).
    """
    now = datetime.now()
    future_limit = now + timedelta(hours=hours_ahead)

    stmt = (
        select(ForecastIntake)
        .where(
            ForecastIntake.forecast_from >= now,
            ForecastIntake.forecast_from <= future_limit
        )
        .order_by(ForecastIntake.forecast_from.asc())
    )

    result = await db.execute(stmt)
    return result.scalars().all()