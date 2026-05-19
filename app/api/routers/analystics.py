from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import date

from app.db.database import get_db
from app.db.models import User, WorkerPerformance
from app.api.deps import get_current_user
from app.services.sync_service import get_workpool_analytics
from app.db.queries import get_upcoming_forecast, calculate_hourly_forecast_report

router = APIRouter(tags=["Analityka, Prognozy i KPI"])

# ╔════════════════════════════════════════════════════════════════════════╗
# ║ 📊 STATYSTYKI STREF (WORKPOOLS)                                         ║
# ╚════════════════════════════════════════════════════════════════════════╝
@router.get("/analytics/workpools")
async def get_workpool_stats(db: AsyncSession = Depends(get_db), _user: User = Depends(get_current_user)):
    """Statystyki obciążenia stref (wymagane m.in. dla AI dashboard)."""
    try:
        data = await get_workpool_analytics(db)
        return {
            "status": "success",
            "timestamp": date.today().isoformat(),
            "workpools": data
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ╔════════════════════════════════════════════════════════════════════════╗
# ║ 📈 MATRYCA UMIEJĘTNOŚCI (SKILLE)                                       ║
# ╚════════════════════════════════════════════════════════════════════════╝
@router.get("/productivity")
async def get_worker_performance(db: AsyncSession = Depends(get_db), _user: User = Depends(get_current_user)):
    """Zwraca matrycę skilli (produktywność) wszystkich pracowników z bazy."""
    result = await db.execute(select(WorkerPerformance))
    return result.scalars().all()

# ╔════════════════════════════════════════════════════════════════════════╗
# ║ 🔮 FORECAST SPŁYWU (NAJBILŻSZE 2 GODZINY)                              ║
# ╚════════════════════════════════════════════════════════════════════════╝
@router.get("/works/forecast_upcoming")
async def get_upcoming_intake(db: AsyncSession = Depends(get_db)):
    """Zwraca prognozowany spływ jednostek na najbliższe 2h z modelu Forecast."""
    data = await get_upcoming_forecast(db)
    return {"status": "success", "count": len(data), "data": data}

# ╔════════════════════════════════════════════════════════════════════════╗
# ║ 📊 FORECAST GODZINOWY DLA DASHBOARDU (ZAKTUALIZOWANA ŚCIEŻKA)          ║
# ╚════════════════════════════════════════════════════════════════════════╝
@router.get("/analytics/forecast/hourly")  # <--- POPRAWIONO: Dodano /analytics/
async def get_hourly_forecast(target_date: str, db: AsyncSession = Depends(get_db)):
    """Wystawia przetworzone dane analityczne dla Dashboardu."""
    try:
        return await calculate_hourly_forecast_report(db, target_date)
    except Exception as e:
        print(f"❌ [BŁĄD API W ENDPOINTS] {str(e)}")
        return []