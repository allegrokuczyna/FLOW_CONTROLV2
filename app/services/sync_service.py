import httpx
import pandas as pd
from datetime import date
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert
from app.core.auth import get_d365_access_token
from app.core.config import settings
from app.db.models import WorkExport, WorkerPerformance

# --- POMOCNIK: PARSOWANIE PROCENTÓW ---
def parse_percent(val):
    if pd.isna(val) or val == "":
        return 0.0
    try:
        # Zamiana "138,71%" na 1.3871
        clean_val = str(val).replace('%', '').replace(',', '.').strip()
        return float(clean_val) / 100.0
    except (ValueError, TypeError):
        return 0.0

# --- POBIERANIE DANYCH Z D365 ---
async def get_data(endpoint_url: str):
    token = await get_d365_access_token()
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    base_url = str(settings.D365_URL).strip('/')
    url = f"{base_url}/data/{endpoint_url}"
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.get(url, headers=headers)
        if response.status_code == 200:
            return response.json().get("value", [])
        return []

# --- SYNC PRAC (SNAJPER MERX) ---
async def sync_works(db: AsyncSession):
    print("🔄 Start synchronizacji prac...")
    url_works = "WarehouseWorkHeaders?cross-company=true&$filter=WarehouseId eq 'ADM-01' and WarehouseWorkStatus eq Microsoft.Dynamics.DataEntities.WHSWorkStatus'Open'&$top=2000"
    works_data = await get_data(url_works)
    
    if not works_data:
        return

    valid_works = [w for w in works_data if str(w.get("ContainerId") or "").strip() == ""]
    unique_orders = list(set(str(w.get("SourceOrderNumber", "")).strip() for w in valid_works if w.get("SourceOrderNumber")))
    
    date_map = {}
    chunk_size = 40 
    for i in range(0, len(unique_orders), chunk_size):
        chunk = unique_orders[i:i + chunk_size]
        filter_str = " or ".join([f"SalesTable_SalesId eq '{order}'" for order in chunk])
        url_dates = f"MerxWHASalesProcessingDates?cross-company=true&$filter={filter_str}"
        chunk_data = await get_data(url_dates)
        for d in chunk_data:
            order_id = str(d.get("SalesTable_SalesId") or "").strip()
            raw_date = d.get("SalesWarehouseShippingDate", "")
            if order_id and raw_date:
                date_map[order_id] = raw_date.split("T")[0]

    for w in valid_works:
        order_num = str(w.get("SourceOrderNumber") or "").strip()
        final_date = None
        custom_date_str = date_map.get(order_num)
        
        if custom_date_str:
            try: final_date = date.fromisoformat(custom_date_str)
            except: pass
        
        if not final_date:
            fallback_dt = w.get("WHAShippingDateRequested", "")
            if fallback_dt:
                try: final_date = date.fromisoformat(fallback_dt.split("T")[0])
                except: pass

        stmt = insert(WorkExport).values(
            work_id=w.get("WarehouseWorkId") or w.get("WorkId"),
            order_num=order_num,
            zone2=w.get("WHAAdditionalZone2", ""),
            item_qty=float(w.get("WHASalesItemQty") or 0),
            carrier_code=w.get("WHACarrierCode", ""),
            shipment_spec=w.get("WHAShipmentSpecId", ""),
            work_pool_id=w.get("WarehouseWorkPoolId", ""),
            shipping_date=final_date
        ).on_conflict_do_update(
            index_elements=['work_id'], 
            set_={
                "zone2": w.get("WHAAdditionalZone2", ""),
                "item_qty": float(w.get("WHASalesItemQty") or 0),
                "carrier_code": w.get("WHACarrierCode", ""),
                "shipment_spec": w.get("WHAShipmentSpecId", ""),
                "work_pool_id": w.get("WarehouseWorkPoolId", ""),
                "shipping_date": final_date 
            }
        )
        await db.execute(stmt)
        
    await db.commit()
    print("✅ Prace zsynchronizowane.")

# --- IMPORT PRODUKTYWNOŚCI (UNIWERSALNY) ---
async def import_productivity_data(df: pd.DataFrame, db: AsyncSession):
    """Zapisuje dane z tabeli Excel/Sheets do bazy danych."""
    print(f"📊 DEBUG: Kolumny jakie widzę w pliku: {df.columns.tolist()}") # To nam powie prawdę
    
    # Próbujemy znaleźć kolumnę login, ignorując wielkość liter
    login_col = next((c for c in df.columns if str(c).lower().strip() == 'login'), None)
    
    if not login_col:
        print("❌ BŁĄD: Nie znalazłem kolumny 'Login' w pliku!")
        return 0

    print(f"🔎 Używam kolumny '{login_col}' jako loginów.")
    
    for _, row in df.iterrows():
        login = str(row.get(login_col, '')).strip()
        if not login or login.lower() == 'nan':
            continue
            
        stmt = insert(WorkerPerformance).values(
            login=login,
            forklift=parse_percent(row.get('FORKLIFT')),
            packing=parse_percent(row.get('Packing')),
            picking=parse_percent(row.get('Picking')),
            putaway=parse_percent(row.get('Putaway')),
            receiving=parse_percent(row.get('Receiving')),
            returns=parse_percent(row.get('Returns')),
            sorting=parse_percent(row.get('Sorting'))
        ).on_conflict_do_update(
            index_elements=['login'],
            set_={
                "forklift": parse_percent(row.get('FORKLIFT')),
                "packing": parse_percent(row.get('Packing')),
                "picking": parse_percent(row.get('Picking')),
                "putaway": parse_percent(row.get('Putaway')),
                "receiving": parse_percent(row.get('Receiving')),
                "returns": parse_percent(row.get('Returns')),
                "sorting": parse_percent(row.get('Sorting'))
            }
        )
        await db.execute(stmt)
    
    await db.commit()
    return len(df)