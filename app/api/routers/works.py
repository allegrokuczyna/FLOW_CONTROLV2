from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.db.models import User
from app.api.deps import get_current_user

# PREFIX: Automatycznie dodaje /works przed każdym endpointem
router = APIRouter(prefix="/works", tags=["Zadania Magazynowe i Filtry"])

# ╔════════════════════════════════════════════════════════════════════════╗
# ║ 📋 WSZYSTKIE AKTYWNE PRACE (W PRZEBUDOWIE)                             ║
# ╚════════════════════════════════════════════════════════════════════════╝
@router.get("/live")
async def get_live_active_works(db: AsyncSession = Depends(get_db), _user: User = Depends(get_current_user)):
    """
    Zaślepka (Placeholder) przygotowana pod nową architekturę QRDE.
    Gdy stworzysz nowy model w bazie, podepniemy tutaj szybkie zapytanie 
    odpytujące zaktualizowaną tabelę w Postgres.
    """
    
    # Na razie zwracamy pustą listę, aby aplikacja React nie wyświetlała błędów w konsoli
    return {
        "status": "success", 
        "total_count": 0, 
        "data": []
    }