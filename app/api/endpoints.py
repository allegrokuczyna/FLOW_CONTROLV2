from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.database import get_db
from app.db.models import WorkExport, WorkerPerformance  # Dodano WorkerPerformance
from app.services.sync_service import sync_works, import_productivity_data
import io
import pandas as pd

# Inicjalizujemy router dla endpointów
router = APIRouter()

# --- SYNC DANYCH Z DYNAMICS 365 ---
@router.post("/sync/works")
async def trigger_sync_works(db: AsyncSession = Depends(get_db)):
    """Synchronizacja prac magazynowych wraz z datami Merx."""
    try:
        await sync_works(db)
        return {"status": "success", "message": "Lista prac zaktualizowana pomyślnie."}
    except Exception as e:
        print(f"❌ Błąd podczas synchronizacji: {e}")
        raise HTTPException(status_code=500, detail=f"Błąd sync prac: {str(e)}")

# --- POBIERANIE PRAC (DLA DASHBOARDU) ---
@router.get("/data")
async def get_exported_data(db: AsyncSession = Depends(get_db)):
    """Pobiera zsynchronizowane prace z naszej bazy."""
    result = await db.execute(select(WorkExport))
    return result.scalars().all()

# --- IMPORT WYDAJNOŚCI Z PLIKU ---
@router.post("/upload/productivity")
async def upload_productivity(file: UploadFile = File(...), db: AsyncSession = Depends(get_db)):
    if not file.filename.endswith(('.xlsx', '.xls')):
        raise HTTPException(status_code=400, detail="To nie jest plik Excela!")
    
    try:
        content = await file.read()
        
        # 1. Najpierw czytamy plik bez nagłówków, żeby go przeszukać
        df_raw = pd.read_excel(io.BytesIO(content), header=None)
        
        # 2. Szukamy, w którym wierszu jest słowo "Login"
        header_row = 0
        for i, row in df_raw.iterrows():
            if row.astype(str).str.contains('Login', case=False).any():
                header_row = i
                break
        
        print(f"🎯 Znaleziono nagłówki w wierszu: {header_row}")

        # 3. Wczytujemy ponownie, startując od znalezionego wiersza
        df = pd.read_excel(io.BytesIO(content), header=header_row)
        
        # Przetwarzamy dane
        count = await import_productivity_data(df, db)
        return {"status": "success", "message": f"Zaimportowano {count} rekordów."}
        
    except Exception as e:
        print(f"❌ Błąd: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# --- PODGLĄD WYDAJNOŚCI ---
@router.get("/productivity")
async def get_worker_performance(db: AsyncSession = Depends(get_db)):
    """Pobiera listę wydajności wszystkich pracowników z bazy."""
    result = await db.execute(select(WorkerPerformance))
    return result.scalars().all()