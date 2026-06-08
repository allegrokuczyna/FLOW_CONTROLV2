from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, select
from datetime import datetime

# --- IMPORTY STRUKTURALNE ---
from app.db.database import get_db
from app.db.models import User, InboundMezzanineWorks, PackingWork, SortWork
from app.api.deps import get_current_user
from app.db.models import User, InboundMezzanineWorks, InventoryQty, OutboundWork

# Importujemy i parser Excela i silnik QRDE
from app.services.sync_service import process_excel_master, sync_active_works_from_d365, InboundMezzanineWorks, fetch_and_save_inventory_qty, fetch_and_save_outbound_works, fetch_and_save_packing_qty, fetch_and_save_sort_qty
from sqlalchemy.dialects.postgresql import insert
import httpx
from app.core.config import settings
from app.core.auth import get_d365_access_token
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
    





@router.post("/debug-mezzanine")
async def debug_mezzanine_sync(db: AsyncSession = Depends(get_db)):

    token = await get_d365_access_token()
    base_url = settings.D365_URL.rstrip('/')
    d365_endpoint = f"{base_url}/api/services/IWSQRDE/QRDE/GetRows"

    payload = {
        "_request": {
            "Message": {
                "RequestID": "fastapi-sandbox-sync-debug",
                "RequestType": "GetRows",
                "RequestService": "QRDE",
                "RequestSource": "FastAPI-Test"
            },
            "EndpointParamName": "InboundFlowQuery", 
            "QueryValues": []
        }
    }

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    }

    # 1. Pobranie danych
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(d365_endpoint, json=payload, headers=headers)
        response.raise_for_status() 
        raw_data = response.json()

    rows = raw_data.get("Rows") or []
    
    # 2. Parsowanie
    parsed_values = []
    for row in rows:
        columns = row.get("Columns", [])
        row_dict = {col.get("FieldName"): col.get("Value") for col in columns if "FieldName" in col}
        
        workpool_id = row_dict.get("workpoolid") or row_dict.get("WorkPoolId")
        if workpool_id:
            parsed_values.append({
                "work_pool_id": str(workpool_id),
                "work_count": int(row_dict.get("IloscPrac", 0)),
                "item_qty": float(row_dict.get("IloscSztuk", 0.0))
            })

    # 3. Zapis
    db_saved = False
    if parsed_values:
        stmt = insert(InboundMezzanineWorks).values(parsed_values)
        stmt = stmt.on_conflict_do_update(
            index_elements=['work_pool_id'], 
            set_={
                "work_count": stmt.excluded.work_count,
                "item_qty": stmt.excluded.item_qty,
                "updated_at": datetime.utcnow()
            }
        )
        await db.execute(stmt)
        await db.commit()
        db_saved = True

    return {
        "krok_1_surowa_odpowiedz_d365": raw_data,
        "krok_2_sparsowane_wartosci": parsed_values,
        "krok_3_czy_zapisano_do_bazy": db_saved
    }



@router.post("/inventory-qty")
async def trigger_inventory_sync(db: AsyncSession = Depends(get_db)):
    """Pobiera ilość sztuk na lokacjach technicznych i zapisuje w bazie."""
    try:
        saved = await fetch_and_save_inventory_qty(db)
        return {
            "status": "success", 
            "message": "Zaktualizowano stan inventory", 
            "updated": saved
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Błąd synchronizacji: {str(e)}")
    



@router.post("/outbound-works")
async def trigger_outbound_sync(db: AsyncSession = Depends(get_db)):
    """Pobiera wolumeny prac z procesów wychodzących i nadpisuje stan w bazie."""
    try:
        saved_count = await fetch_and_save_outbound_works(db)
        return {
            "status": "success", 
            "message": "Zaktualizowano wolumeny Outbound", 
            "records_processed": saved_count
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Błąd synchronizacji Outbound: {str(e)}")
    

@router.post("/packing-qty")
async def trigger_packing_sync(db: AsyncSession = Depends(get_db)):
    """Pobiera wolumeny prac dla procesu pakowania i nadpisuje stan w bazie."""
    try:
        saved_count = await fetch_and_save_packing_qty(db)
        return {
            "status": "success", 
            "message": "Zaktualizowano wolumeny pakowania", 
            "records_processed": saved_count
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Błąd synchronizacji pakowania: {str(e)}")
    



@router.post("/sort-qty")
async def trigger_sort_sync(db: AsyncSession = Depends(get_db)):
    """Pobiera ilości do sortowania i zapisuje w bazie."""
    try:
        saved = await fetch_and_save_sort_qty(db)
        return {"status": "success", "message": "Zaktualizowano sortowanie", "updated": saved}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Błąd synchronizacji: {str(e)}")





@router.get("/live-view")
async def get_live_warehouse_view(db: AsyncSession = Depends(get_db)):
    # 1. Inbound
    inbound_res = await db.execute(select(InboundMezzanineWorks))
    inbound = inbound_res.scalars().all()
    inbound_works = sum(i.work_count for i in inbound)
    inbound_qty = sum(i.item_qty for i in inbound)

    # 2. Putaway
    inv_res = await db.execute(select(InventoryQty).where(InventoryQty.id == 1))
    inventory = inv_res.scalar_one_or_none()
    putaway_qty = inventory.available_physical if inventory else 0

    # 3. Picking
    outbound_res = await db.execute(select(OutboundWork))
    outbound = outbound_res.scalars().all()
    outbound_qty = sum(o.work_qty for o in outbound)

    # 4. Packing
    packing_res = await db.execute(select(PackingWork).where(PackingWork.id == 1))
    packing_row = packing_res.scalar_one_or_none()
    packing_qty = int(packing_row.value) if packing_row else 0

    # 5. Sorting (NOWOŚĆ!)
    sort_res = await db.execute(select(SortWork).where(SortWork.id == 1))
    sort_row = sort_res.scalar_one_or_none()
    sort_qty = int(sort_row.qty) if sort_row else 0

    return {
        "status": "success",
        "timestamp": datetime.now().strftime("%H:%M:%S"),
        "data": {
            "receiving": {"works": inbound_works, "qty": inbound_qty},
            "putaway": {"works": "-", "qty": putaway_qty},
            "picking": {"works": len(outbound), "qty": outbound_qty},
            "packing": {"works": "-", "qty": packing_qty},
            "sorting": {"works": "-", "qty": sort_qty}  # <-- Wszystko żyje!
        }
    }