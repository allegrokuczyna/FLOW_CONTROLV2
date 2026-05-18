from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime

from app.db.database import get_db
from app.db.models import User, AiReportLog
from app.db.schemas import AiRequest
from app.api.deps import get_current_user

router = APIRouter(tags=["AI - Sztuczna Inteligencja"])

# ╔════════════════════════════════════════════════════════════════════════╗
# ║ 🤖 RAPORT MANAGERA AI                                                  ║
# ╚════════════════════════════════════════════════════════════════════════╝
@router.get("/ai/manager_report")
async def get_ai_report(db: AsyncSession = Depends(get_db), _user: User = Depends(get_current_user)):
    """Generuje pełną analizę strategiczną AI i wypluwa tekstowy raport dla Managera."""
    from app.services.ai_service import get_ai_warehouse_advice
    return await get_ai_warehouse_advice(db, username=_user.username)

# ╔════════════════════════════════════════════════════════════════════════╗
# ║ 📜 HISTORIA RAPORTÓW AI                                                ║
# ╚════════════════════════════════════════════════════════════════════════╝
@router.get("/ai/manager_report/history")
async def get_ai_report_history(
    limit: int = 10,
    db: AsyncSession = Depends(get_db), 
    _user: User = Depends(get_current_user)
):
    """Pobiera historię wygenerowanych raportów AI do przeglądu."""
    stmt = select(AiReportLog).order_by(AiReportLog.id.desc()).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()

# ╔════════════════════════════════════════════════════════════════════════╗
# ║ 🧠 SUGESTIE PRZYDZIAŁÓW (AI ROZDZIELA LUDZI)                           ║
# ╚════════════════════════════════════════════════════════════════════════╝
@router.post("/plan/ai_suggest")
async def suggest_plan(req: AiRequest, db: AsyncSession = Depends(get_db)):
    """Wysyła prośbę do modelu, by samoczynnie dopasował ludzi do stref."""
    from app.services.ai_service import generate_ai_assignments
    
    shift_id = str(req.shift)
    parsed_date = None
    
    if req.target_date:
        try:
            parsed_date = datetime.strptime(req.target_date, "%Y-%m-%d").date()
        except ValueError:
            parsed_date = None 
            
    return await generate_ai_assignments(db, shift_id=shift_id, target_date=parsed_date)