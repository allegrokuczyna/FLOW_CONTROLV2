import httpx
from datetime import date
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert
from app.core.auth import get_d365_access_token
from app.core.config import settings
from app.db.models import WorkExport, User



#===============pobieranie danych===================================
async def get_data(endpoint_url: str):
    """Pomocnicza funkcja do pobierania danych z D365 OData."""
    token = await get_d365_access_token()
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    base_url = str(settings.D365_URL).strip('/')
    url = f"{base_url}/data/{endpoint_url}"
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.get(url, headers=headers)
        if response.status_code == 200:
            return response.json().get("value", [])
        return []
#===================PRACE/OTWARTE/MAGAZYN ADM-01/ -================
async def sync_works(db: AsyncSession):
    """Główna logika synchronizacji prac magazynowych z customowymi datami Merx."""
    
    # 1. Pobieramy otwarte prace dla magazynu ADM-01
    url_works = "WarehouseWorkHeaders?cross-company=true&$filter=WarehouseId eq 'ADM-01' and WarehouseWorkStatus eq Microsoft.Dynamics.DataEntities.WHSWorkStatus'Open'&$top=2000"
    works_data = await get_data(url_works)
    
    if not works_data:
        print("ℹ️ Brak prac do synchronizacji.")
        return

    # Filtrujemy tylko te bez przypisanego kontenera
    valid_works = [w for w in works_data if str(w.get("ContainerId") or "").strip() == ""]
    
    # Pobieramy unikalne numery zamówień do celowanego zapytania o daty
    unique_orders = list(set(str(w.get("SourceOrderNumber", "")).strip() for w in valid_works if w.get("SourceOrderNumber")))
    
    # 2. Pobieramy daty wysyłki z encji customowej (batching po 40 sztuk)
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

    # 3. Zapis/Aktualizacja danych w bazie Postgres
    inserted_count = 0
    for w in valid_works:
        order_num = str(w.get("SourceOrderNumber") or "").strip()
        custom_date_str = date_map.get(order_num)
        
        final_date = None
        # Próba konwersji daty z Merx
        if custom_date_str:
            try:
                final_date = date.fromisoformat(custom_date_str)
            except ValueError:
                pass
        
        # Fallback do daty requested, jeśli merx nie dostarczył poprawnej daty
        if not final_date:
            fallback_dt = w.get("WHAShippingDateRequested", "")
            if fallback_dt:
                try:
                    final_date = date.fromisoformat(fallback_dt.split("T")[0])
                except ValueError:
                    final_date = None

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
        inserted_count += 1
        
    await db.commit()
    print(f"✅ Sync complete: {inserted_count} records processed.")

