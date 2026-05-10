from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.database import get_db
from app.db.models import WorkExport, WorkerPerformance, ActiveWork
from app.services.sync_service import (
    sync_works, 
    process_full_system_sync, 
    sync_active_works
)
import pandas as pd

# Inicjalizujemy router
router = APIRouter()

# --- 1. SYNCHRONIZACJA PRAC (DYNAMICS 365 - ARCHIWUM/GŁÓWNE) ---
@router.post("/sync/works")
async def trigger_sync_works(db: AsyncSession = Depends(get_db)):
    """Pobiera otwarte prace i zapisuje w głównym eksporcie."""
    try:
        await sync_works(db)
        return {"status": "success", "message": "Główna lista prac zaktualizowana."}
    except Exception as e:
        print(f"❌ Błąd sync_works: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# --- 2. LIVE SYNC: WHSWorkTable (STAN AKTYWNY 0,1) ---
@router.post("/sync/active_status")
async def trigger_active_sync(db: AsyncSession = Depends(get_db)):
    """
    Kluczowy endpoint operacyjny. 
    Pobiera wszystkie kolumny dla prac Open (0) i InProcess (1).
    """
    try:
        await sync_active_works(db)
        return {"status": "success", "message": "Stan aktywnych prac (WHSWorkTable) odświeżony."}
    except Exception as e:
        print(f"❌ Błąd active_sync: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# --- 3. POBIERANIE DANYCH DLA DASHBOARDU ---
@router.get("/active_data")
async def get_active_work_data(db: AsyncSession = Depends(get_db)):
    """Zwraca 'żywe' dane o pracach Open/InProcess do wyświetlenia na stronie."""
    result = await db.execute(select(ActiveWork))
    return result.scalars().all()

@router.get("/data")
async def get_exported_data(db: AsyncSession = Depends(get_db)):
    """Pobiera dane z głównej tabeli eksportu."""
    result = await db.execute(select(WorkExport))
    return result.scalars().all()

@router.get("/productivity")
async def get_worker_performance(db: AsyncSession = Depends(get_db)):
    """Zwraca wydajność pracowników (Matryca)."""
    result = await db.execute(select(WorkerPerformance))
    return result.scalars().all()

# --- 4. GŁÓWNA SYNCHRONIZACJA (GOOGLE SHEETS: GRAFIK + MATRYCA) ---
@router.post("/sync/full_system/")
async def full_system_sync(payload: dict, db: AsyncSession = Depends(get_db)):
    """Odbiera paczkę z Google i aktualizuje Grafik oraz Matrycę."""
    return await process_full_system_sync(payload, db)

# --- 5. LEGACY UPLOAD (SAMODZIELNA MATRYCA) ---
@router.post("/upload/productivity_json")
async def upload_productivity_json(request: Request, db: AsyncSession = Depends(get_db)):
    """Dla kompatybilności - przesyła samą matrycę."""
    try:
        body = await request.json()
        raw_data = body.get("data", [])
        payload = {"matryca": raw_data, "grafik_2026": []}
        return await process_full_system_sync(payload, db)
    except Exception as e:
        return {"status": "error", "message": str(e)}