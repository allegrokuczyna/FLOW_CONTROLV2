from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.database import get_db, AsyncSessionLocal
from app.db.models import User
from app.api.deps import get_current_admin
from app.services.sync_service import process_full_push_sync, sync_works, sync_active_works, get_data

router = APIRouter(prefix="/sync", tags=["Synchronizacja (D365 & GSheet)"])

async def background_sync_task(payload: dict):
    """To zadanie odpali się w tle, po tym jak API odeśle 'OK' do Google Sheets."""
    print("⏳ [ZADANIE W TLE] Rozpoczynam ciężką synchronizację danych z Google Sheets...")
    
    # Tworzymy całkowicie nową, niezależną sesję bazy danych dla zadania w tle
    async with AsyncSessionLocal() as db:
        try:
            await process_full_push_sync(payload, db)
            print("✅ [ZADANIE W TLE] Synchronizacja PUSH zakończona pełnym sukcesem!")
        except Exception as e:
            print(f"❌ [ZADANIE W TLE] Krytyczny błąd: {str(e)}")







# ╔════════════════════════════════════════════════════════════════════════╗
# ║ 📥 FULL PUSH (WEBHOOK Z GOOGLE SHEETS)                                 ║
# ╚════════════════════════════════════════════════════════════════════════╝
@router.post("/full_push")
async def trigger_full_push(payload: dict, background_tasks: BackgroundTasks):
    """Odbiera potężną paczkę danych i od razu zwalnia Google Apps Script."""
    try:
        
        background_tasks.add_task(background_sync_task, payload)
        
        
        return {"status": "success", "message": "Dane zostały przyjęte. Synchronizacja trwa w tle na serwerze."}
    except Exception as e:
        print(f"❌ Critical Sync Error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Błąd uruchamiania zadania w tle: {str(e)}")

# ╔════════════════════════════════════════════════════════════════════════╗
# ║ 🗄️ ARCHIWIZACJA PRAC (D365)                                            ║
# ╚════════════════════════════════════════════════════════════════════════╝
@router.post("/works")
async def trigger_sync_works(db: AsyncSession = Depends(get_db), _admin: User = Depends(get_current_admin)):
    """Pobiera i archiwizuje otwarte prace z D365 (wymaga bycia adminem)."""
    try:
        await sync_works(db)
        return {"status": "success", "message": "Archiwum prac zaktualizowane."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ╔════════════════════════════════════════════════════════════════════════╗
# ║ ⚡ LIVE SYNC AKTYWNYCH PRAC (D365)                                     ║
# ╚════════════════════════════════════════════════════════════════════════╝
@router.post("/active_status")
async def trigger_active_sync(db: AsyncSession = Depends(get_db), _admin: User = Depends(get_current_admin)):
    """Odświeża bieżący stan prac (Open/InProcess) - Live Sync z D365."""
    try:
        await sync_active_works(db)
        return {"status": "success", "message": "Stan aktywnych prac odświeżony."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ╔════════════════════════════════════════════════════════════════════════╗
# ║ 🔍 INSPEKCJA KOLUMN (DEBUG D365)                                       ║
# ╚════════════════════════════════════════════════════════════════════════╝
@router.get("/inspect_d365")
async def inspect_d365_fields():
    """Tymczasowy endpoint do podglądu dostępnych kolumn w API D365."""
    endpoint = "WarehouseWorkHeaders?cross-company=true&$top=1"
    works_data = await get_data(endpoint)
    
    if not works_data or len(works_data) == 0:
        return {"status": "error", "message": "Nie udało się pobrać żadnych danych z D365."}
        
    sample_record = works_data[0]
    available_columns = list(sample_record.keys())
    available_columns.sort()
    
    return {
        "status": "success", 
        "total_columns": len(available_columns),
        "columns": available_columns,
        "sample_data": sample_record 
    }