from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from datetime import datetime
from app.db.database import get_db
from app.db.models import User
from app.api.deps import get_current_user, get_current_admin
from app.services.sync_service import process_excel_master, sync_works, sync_active_works, get_data, sync_template_module

router = APIRouter(prefix="/sync", tags=["Synchronizacja (D365 & Excel)"])

# ==============================================================================
# 1. IMPORT DANYCH Z EXCELA (Zastępuje stare API Google Sheets)
# ==============================================================================

@router.post("/upload_excel")
async def upload_excel_endpoint(
    file: UploadFile = File(...), 
    db: AsyncSession = Depends(get_db),
    # current_user: User = Depends(get_current_user) # Opcjonalnie: odkomentuj, by zablokować dla niezalogowanych
):
    """Nowy endpoint do ładowania pliku Master Excel bezpośrednio z przeglądarki."""
    print(f"📥 Odbieram plik: {file.filename}")
    
    if not file.filename.endswith(('.xlsx', '.xls')):
        raise HTTPException(status_code=400, detail="Wymagany format pliku to .xlsx lub .xls")
        
    try:
        # Odczytujemy surowe bajty pliku (w pamięci RAM, bez zapisywania na dysku)
        contents = await file.read()
        
        # Przekazujemy bajty do naszego potężnego silnika w sync_service.py
        report = await process_excel_master(contents, db)
        
        return {"status": "success", "report": report}
        
    except Exception as e:
        print(f"🔥 Błąd routera podczas uploadu: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Błąd przetwarzania pliku: {str(e)}")


# ==============================================================================
# 2. HELPER DO D365 ORAZ ZAPIS LOGÓW
# ==============================================================================

async def execute_d365_sync(db: AsyncSession, triggered_by: str):
    """Wspólna funkcja wykonująca synchronizację D365 i zapisująca audit trail."""
    try:
        # 1. Sprawdzenie/Tworzenie tabeli historii synchronizacji
        await db.execute(text("""
            CREATE TABLE IF NOT EXISTS sync_history (
                id SERIAL PRIMARY KEY,
                sync_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                triggered_by VARCHAR(100),
                status VARCHAR(50)
            )
        """))
        
        # 2. Wykonanie obu Twoich funkcji synchronizacji D365
        await sync_active_works(db)
        await sync_works(db)
        
        # 3. Zapisanie sukcesu do bazy logów
        await db.execute(text("""
            INSERT INTO sync_history (sync_time, triggered_by, status)
            VALUES (:sync_time, :triggered_by, :status)
        """), {"sync_time": datetime.now(), "triggered_by": triggered_by, "status": "SUCCESS"})
        await db.commit()
        return True
    except Exception as e:
        await db.rollback()
        # W razie awarii próbujemy zapisać błąd, żeby kierownik wiedział, co poszło nie tak
        try:
            await db.execute(text("""
                INSERT INTO sync_history (sync_time, triggered_by, status)
                VALUES (:sync_time, :triggered_by, :status)
            """), {"sync_time": datetime.now(), "triggered_by": triggered_by, "status": f"ERROR: {str(e)[:40]}"})
            await db.commit()
        except:
            pass
        raise e


# ==============================================================================
# 3. ZINTEGROWANE ZARZĄDZANIE INTEGRACJĄ D365
# ==============================================================================

@router.post("/trigger")
async def trigger_manual_d365_sync(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Ręczne wymuszenie pełnej synchronizacji D365 przez zalogowanego użytkownika."""
    try:
        # ZABEZPIECZENIE: getattr sprawdzi atrybut, a jeśli go nie ma, zwróci None zamiast wywalić błąd
        user_label = (
            getattr(current_user, 'full_name', None) or 
            getattr(current_user, 'username', None) or 
            getattr(current_user, 'login', None) or 
            "Kierownik"
        )
        await execute_d365_sync(db, triggered_by=user_label)
        return {"status": "success", "message": "Synchronizacja D365 zakończona sukcesem!"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Błąd synchronizacji: {str(e)}")

@router.get("/status")
async def get_d365_sync_status(db: AsyncSession = Depends(get_db)):
    """Zwraca metryki ostatniej operacji synchronizacji bazy."""
    try:
        # Fail-safe na wypadek, gdyby tabela jeszcze nie powstała
        await db.execute(text("CREATE TABLE IF NOT EXISTS sync_history (id SERIAL PRIMARY KEY, sync_time TIMESTAMP, triggered_by VARCHAR, status VARCHAR)"))
        
        result = await db.execute(text("""
            SELECT sync_time, triggered_by, status 
            FROM sync_history 
            ORDER BY sync_time DESC LIMIT 1
        """))
        row = result.first()
        if row:
            return {
                "last_sync_time": row[0].strftime("%Y-%m-%d %H:%M:%S") if row[0] else None,
                "triggered_by": row[1],
                "status": row[2]
            }
        return {"last_sync_time": None, "triggered_by": "Brak", "status": "NEVER"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ==============================================================================
# 4. ENDPOINTY NARZĘDZIOWE (Kompatybilność Wsteczna / Debug)
# ==============================================================================

@router.post("/works")
async def trigger_sync_works(db: AsyncSession = Depends(get_db), _admin: User = Depends(get_current_admin)):
    try:
        await sync_works(db)
        return {"status": "success", "message": "Archiwum prac zaktualizowane."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/active_status")
async def trigger_active_sync(db: AsyncSession = Depends(get_db), _admin: User = Depends(get_current_admin)):
    try:
        await sync_active_works(db)
        return {"status": "success", "message": "Stan aktywnych prac odświeżony."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/active_orders")
async def trigger_active_orders_sync(db: AsyncSession = Depends(get_db), _admin: User = Depends(get_current_admin)):
    try:
        await sync_template_module(db)
        return {"status": "success", "message": "Stan aktywnych zamówień odświeżony."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/inspect_d365")
async def inspect_d365_fields():
    endpoint = "WarehouseWorkHeaders?cross-company=true&$top=1"
    works_data = await get_data(endpoint)
    if not works_data or len(works_data) == 0:
        return {"status": "error", "message": "Nie udało się pobrać żadnych danych z D365."}
    sample_record = works_data[0]
    available_columns = list(sample_record.keys())
    available_columns.sort()
    return {"status": "success", "total_columns": len(available_columns), "columns": available_columns, "sample_data": sample_record}

@router.get("/inspect_d365_sales")
async def inspect_d365_sales_fields(): # <--- Tutaj naprawiono konflikt nazw
    endpoint = "SalesOrderHeadersV4?cross-company=true&$top=1"
    works_data = await get_data(endpoint)
    if not works_data or len(works_data) == 0:
        return {"status": "error", "message": "Nie udało się pobrać żadnych danych z D365."}
    sample_record = works_data[0]
    available_columns = list(sample_record.keys())
    available_columns.sort()
    return {"status": "success", "total_columns": len(available_columns), "columns": available_columns, "sample_data": sample_record}