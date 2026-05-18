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
        'u_adm-01_ hv', 'u_adm-01_ mez', 'u_adm-01_ pw', 
        'u_adm-01_ std', 'u_adm-01_ kartony', 'u_adm-01_ wyc'
    ]
    
    stmt = (
        select(ActiveWork)
        .where(
            func.lower(ActiveWork.workpoolid).in_(target_pools),
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
            func.lower(ActiveWork.workpoolid).in_(target_mez),
            ActiveWork.workstatus == 'Open'
        )
        .order_by(ActiveWork.workid)
    )
    
    result = await db.execute(stmt)
    return result.scalars().all()



#Pobieranie otwartych prac przyjécia mezanina
async def get_inbound_works_mezz(db: AsyncSession):
    """Pobierania prac przyjecia towary"""
    target_inound = ['przyjęcie mezanina']

    s_inb = (
        select(ActiveWork)
        .where
        (func.lower(ActiveWork.workpoolid).in_(target_inound),
            ActiveWork.workstatus == 'Open'
        )
        .order_by(ActiveWork.ordernum)
    )

    result = await db.execute(s_inb)
    return result.scalars().all()


async def get_multi_orders(db: AsyncSession):
    """pobieranie wszystkich otwartych zamówien wielosztukowych"""

    target_multi = ['adm-01_wiel']

    s_multi =(
        select(ActiveWork)
        .where(func.lower(ActiveWork.workpoolid).in_(target_multi),
               ActiveWork.workstatus == 'Open').order_by(ActiveWork.ordernum)
    )

    result = await db.execute(s_multi)
    return result.scalars().all()


async def get_one_open_pieces(db: AsyncSession):
    """pobieranie jednosztukowych zamówien"""

    target_single = ['adm-01_jedn']

    s_single = (
        select(ActiveWork)
        .where(func.lower(ActiveWork.workpoolid).in_(target_single),
               ActiveWork.workstatus == 'Open').order_by(ActiveWork.ordernum)
    )

    result = await db.execute(s_single)
    return result.scalars().all()

async def get_one_inprocess_pieces(db: AsyncSession):
    """pobieranie jednosztuk w toku"""

    target_single = ['adm-01_jedn']

    s_single = (select(ActiveWork).where(func.lower(ActiveWork.workpoolid).in_(target_single),
                                         ActiveWork == 'InProcess').order_by(ActiveWork.ordernum)
    )
    result = await db.execute(s_single)
    return result.scalars().all()
 

    
    

# ==============================================================================
# SEKCJA: PROGNOZY I PLANOWANIE (FORECAST)
# ==============================================================================

async def get_upcoming_forecast(db: AsyncSession):
    """Pobiera forecast na obecną i kolejne godziny dzisiejszego oraz jutrzejszego dnia."""
    now = datetime.utcnow()
    
    # ZWIĘKSZONE OKNO CZASOWE: 
    # 4 godziny wstecz.
    start_time = now - timedelta(hours=4)
    end_time = now + timedelta(hours=24)

    stmt = select(ForecastIntake).where(
        ForecastIntake.hour_from >= start_time,
        ForecastIntake.hour_from <= end_time
    ).order_by(ForecastIntake.hour_from.asc())

    result = await db.execute(stmt)
    forecasts = result.scalars().all()

    return [{
        "forecast_date": f.forecast_date.isoformat(),
        "hour_from": f.hour_from.isoformat(),
        "forecast_pcs": f.forecast_pcs
    } for f in forecasts]