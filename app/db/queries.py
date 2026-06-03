from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func
from app.db.models import Schedule, WorkerPerformance, AiReportLog, ForecastIntake
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
# SEKCJA: OBECNOŚĆ NA MAGAZYNIE
# ==============================================================================

async def get_active_workers(db: AsyncSession, target_date: date):
    """Pobiera listę aktywnych pracowników obecnych na magazynie."""
    stmt = select(Schedule).filter(Schedule.is_present == True, Schedule.work_date == target_date)
    result = await db.execute(stmt)
    return result.scalars().all()


async def get_inactive_workers(db: AsyncSession, target_date: date):
    """Pobiera listę nieobecnych/planowanych pracowników."""
    stmt = select(Schedule).filter(Schedule.is_present == False, Schedule.work_date == target_date)
    result = await db.execute(stmt)
    return result.scalars().all()


# ==============================================================================
# 🚀 SEKCJA: PRACE OPERACYJNE (Zoptymalizowane pod czysty silnik QRDE)
# ==============================================================================



# ==============================================================================
# SEKCJA: PROGNOZY I PLANOWANIE (FORECAST)
# ==============================================================================

async def get_upcoming_forecast(db: AsyncSession):
    """Pobiera forecast na obecną i kolejne godziny dzisiejszego oraz jutrzejszego dnia."""
    now = datetime.utcnow()
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


async def get_raw_hourly_forecast(db: AsyncSession, target_date: date):
    """Wyciąga z bazy sumy sztuk pogrupowane po godzinie i typie klienta."""
    hour_expr = func.to_char(ForecastIntake.hour_from, 'HH24:00')
    
    stmt = (
        select(
            hour_expr.label('hour'),
            ForecastIntake.client_type,
            func.sum(ForecastIntake.forecast_pcs).label('total_pcs')
        )
        .where(ForecastIntake.forecast_date == target_date)
        .group_by(hour_expr, ForecastIntake.client_type)
        .order_by(hour_expr)
    )
    
    result = await db.execute(stmt)
    return result.all()


async def calculate_hourly_forecast_report(db: AsyncSession, target_date_str: str) -> list:
    """Konwertuje surowe dane z bazy na format czytelny dla frontendu."""
    d = date.fromisoformat(target_date_str)
    raw_rows = await get_raw_hourly_forecast(db, d)
    
    hourly_map = {}
    for hour, c_type, pcs in raw_rows:
        if hour not in hourly_map:
            hourly_map[hour] = {"hour": hour, "yf": 0, "yp": 0}
        if c_type == "1F":
            hourly_map[hour]["yf"] = int(pcs or 0)
        elif c_type == "1P":
            hourly_map[hour]["yp"] = int(pcs or 0)
            
    return sorted(list(hourly_map.values()), key=lambda x: x['hour'])