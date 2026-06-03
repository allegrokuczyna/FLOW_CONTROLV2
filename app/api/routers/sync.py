from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from datetime import datetime

# --- IMPORTY STRUKTURALNE ---
from app.db.database import get_db
from app.db.models import User
from app.api.deps import get_current_user

# Importujemy i parser Excela i silnik QRDE
from app.services.sync_service import process_excel_master, sync_active_works_from_d365

router = APIRouter(prefix="/sync", tags=["Synchronizacja (D365 & Excel)"])

# ==============================================================================
# 1. IMPORT DANYCH Z EXCELA 
# ==============================================================================

@router.post("/upload_excel")
async def upload_excel_endpoint(file: UploadFile = File(...), db: AsyncSession = Depends(get_db)):
    """Endpoint do ładowania pliku Master Excel (Grafik i Forecast)."""
    print(f"📥 Odbieram plik: {file.filename}")
    
    if not file.filename.endswith(('.xlsx', '.xls')):
        raise HTTPException(status_code=400, detail="Wymagany format pliku to .xlsx lub .xls")
        
    try:
        contents = await file.read()
        report = await process_excel_master(contents, db)
        return {"status": "success", "report": report}
    except Exception as e:
        print(f"🔥 Błąd routera podczas uploadu: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Błąd przetwarzania pliku: {str(e)}")


# ==============================================================================
# 2. HELPER DO SYNCHRONIZACJI QRDE ORAZ ZAPIS LOGÓW HISTORII
# ==============================================================================

async def execute_d365_qrde_sync(db: AsyncSession, triggered_by: str):
    """Wspólna funkcja wykonująca synchronizację prac przez QRDE i zapisująca audit trail."""
    try:
        await db.execute(text("""
            CREATE TABLE IF NOT EXISTS sync_history (
                id SERIAL PRIMARY KEY,
                sync_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                triggered_by VARCHAR(100),
                status VARCHAR(50)
            )
        """))
        
        await sync_active_works_from_d365(db)
        
        await db.execute(text("""
            INSERT INTO sync_history (sync_time, triggered_by, status)
            VALUES (:sync_time, :triggered_by, :status)
        """), {"sync_time": datetime.now(), "triggered_by": triggered_by, "status": "SUCCESS"})
        await db.commit()
        return True
        
    except Exception as e:
        await db.rollback()
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
# 3. ENDPOINTY INTERFEJSU D365 (Dla Frontu)
# ==============================================================================

@router.post("/trigger")
async def trigger_manual_d365_sync(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    try:
        user_label = getattr(current_user, 'full_name', None) or getattr(current_user, 'username', None) or "Kierownik"
        await execute_d365_qrde_sync(db, triggered_by=user_label)
        return {"status": "success", "message": "Synchronizacja QRDE zakończona sukcesem!"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Błąd synchronizacji QRDE: {str(e)}")


@router.get("/status")
async def get_d365_sync_status(db: AsyncSession = Depends(get_db)):
    try:
        await db.execute(text("CREATE TABLE IF NOT EXISTS sync_history (id SERIAL PRIMARY KEY, sync_time TIMESTAMP, triggered_by VARCHAR, status VARCHAR)"))
        result = await db.execute(text("SELECT sync_time, triggered_by, status FROM sync_history ORDER BY sync_time DESC LIMIT 1"))
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