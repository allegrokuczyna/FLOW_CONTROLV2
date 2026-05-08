from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.database import get_db
from app.db.models import WorkExport
from app.services.sync_service import sync_works, sync_users

# Inicjalizujemy router dla endpointów
router = APIRouter()

@router.post("/sync/users")
async def trigger_sync_users(db: AsyncSession = Depends(get_db)):
    """Synchronizacja pracowników magazynu (WHSWorkers)."""
    try:
        await sync_users(db)
        return {"status": "success", "message": "Lista pracowników zaktualizowana."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Błąd sync pracowników: {str(e)}")

@router.post("/sync/works")
async def trigger_sync_works(db: AsyncSession = Depends(get_db)):
    """Synchronizacja prac magazynowych wraz z datami Merx."""
    try:
        await sync_works(db)
        return {"status": "success", "message": "Lista prac zaktualizowana."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Błąd sync prac: {str(e)}")

@router.get("/data")
async def get_exported_data(db: AsyncSession = Depends(get_db)):
    """Pobiera gotowe, złączone dane z naszej bazy"""
    # Zwracamy wszystko
    result = await db.execute(select(WorkExport))
    return result.scalars().all()