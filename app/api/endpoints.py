from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Request
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
@router.post("/upload/productivity_json")
async def upload_productivity_json(request: Request, db: AsyncSession = Depends(get_db)):
    """Odbiera dane produktywności i inteligentnie szuka nagłówka 'Login'."""
    try:
        body = await request.json()
        raw_data = body.get("data", [])
        
        if not raw_data:
            return {"status": "error", "message": "Brak danych z Google Sheets."}

        # 1. Tworzymy surową tabelę z tego, co przysłał Google
        df_raw = pd.DataFrame(raw_data)
        
        # 2. Szukamy, w którym wierszu jest nagłówek "Login"
        header_row_index = 0
        found = False
        for i, row in df_raw.iterrows():
            if row.astype(str).str.contains('Login', case=False).any():
                header_row_index = i
                found = True
                break
        
        if not found:
            print("❌ BŁĄD: W przesłanym arkuszu nie znaleziono kolumny 'Login'!")
            return {"status": "error", "message": "Nie znaleziono kolumny 'Login'."}

        # 3. Wycinamy dane: wiersz z nagłówkiem 
        new_header = df_raw.iloc[header_row_index]
        df = pd.DataFrame(df_raw.values[header_row_index + 1:], columns=new_header)
        
        # Czyścimy nazwy kolumn ze spacji
        df.columns = [str(c).strip() for c in df.columns]
        
        print(f"🎯 Znaleziono nagłówki w wierszu {header_row_index}. Kolumny: {df.columns.tolist()}")

        # 4. Przesyłamy do  serwisu
        count = await import_productivity_data(df, db)
        
        return {"status": "success", "message": f"Zsynchronizowano {count} rekordów."}
        
    except Exception as e:
        print(f"❌ Błąd odbiornika: {e}")
        return {"status": "error", "message": str(e)}

# --- PODGLĄD WYDAJNOŚCI ---
@router.get("/productivity")
async def get_worker_performance(db: AsyncSession = Depends(get_db)):
    """Pobiera listę wydajności wszystkich pracowników z bazy."""
    result = await db.execute(select(WorkerPerformance))
    return result.scalars().all()