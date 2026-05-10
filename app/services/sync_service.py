import httpx
import pandas as pd
from datetime import date, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert
from app.core.auth import get_d365_access_token
from app.core.config import settings
from app.db.models import WorkExport, WorkerPerformance, Schedule, ActiveWork

# --- INTELIGENTNY PARSER DATY ---
def flexible_date_parser(text):
    """Próbuje zamienić nagłówek na czystą datę."""
    try:
        ts = pd.to_datetime(text, errors='coerce')
        if pd.isna(ts):
            # Próba dla polskich skrótów (np. 01 sty)
            miesiące = {'sty': 1, 'lut': 2, 'mar': 3, 'kwi': 4, 'maj': 5, 'cze': 6,
                        'lip': 7, 'sie': 8, 'wrz': 9, 'paź': 10, 'lis': 11, 'gru': 12}
            parts = str(text).lower().strip().split(' ')
            if len(parts) == 2:
                day = int(parts[0])
                month = miesiące.get(parts[1][:3])
                if month: return date(2026, month, day)
            return None

        # Korekta strefy czasowej (UTC 23:00 -> PL 00:00 dnia następnego)
        if ts.hour == 23:
            ts = ts + timedelta(hours=1)
        return ts.date()
    except:
        return None

# --- POMOCNIK: PARSOWANIE PROCENTÓW ---
def parse_percent(val):
    if pd.isna(val) or val == "": return 0.0
    try:
        return float(str(val).replace('%', '').replace(',', '.').strip()) / 100.0
    except: return 0.0

# --- POBIERANIE DANYCH Z D365 (Helper) ---
async def get_data(endpoint_url: str):
    token = await get_d365_access_token()
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    base_url = str(settings.D365_URL).strip('/')
    url = f"{base_url}/data/{endpoint_url}"
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.get(url, headers=headers)
        return response.json().get("value", []) if response.status_code == 200 else []

# --- SYNC PRAC DYNAMICS (SNAJPER) ---
async def sync_works(db: AsyncSession):
    print("🔄 Start synchronizacji prac Dynamics...")
    url_works = "WarehouseWorkHeaders?cross-company=true&$filter=WarehouseId eq 'ADM-01' and WarehouseWorkStatus eq Microsoft.Dynamics.DataEntities.WHSWorkStatus'Open'&$top=2000"
    
    works_data = await get_data(url_works)
    if not works_data:
        print("⚠️ Brak otwartych prac w D365 dla magazynu ADM-01.")
        return

    # 1. Filtrujemy prace (pomijamy te w kontenerach)
    valid_works = [w for w in works_data if str(w.get("ContainerId") or "").strip() == ""]
    unique_orders = list(set(str(w.get("SourceOrderNumber", "")).strip() for w in valid_works if w.get("SourceOrderNumber")))
    
    # 2. Pobieramy daty wysyłki Merx w paczkach po 40 sztuk
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

    # 3. Zapis/Aktualizacja w bazie (Upsert)
    for w in valid_works:
        order_num = str(w.get("SourceOrderNumber") or "").strip()
        final_date = None
        
        # Próba uzyskania daty z Merx, potem fallback na nagłówek pracy
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
    print(f"✅ Dynamics OK. Zsynchronizowano {len(valid_works)} prac.")

# --- IMPORT WYDAJNOŚCI (MATRYCA) ---
async def import_productivity_data(df: pd.DataFrame, db: AsyncSession):
    login_col = next((c for c in df.columns if str(c).lower().strip() == 'login'), None)
    if not login_col: return 0
    for _, row in df.iterrows():
        login = str(row.get(login_col, '')).strip()
        if not login or login.lower() == 'nan': continue
        stmt = insert(WorkerPerformance).values(
            login=login, 
            forklift=parse_percent(row.get('FORKLIFT')), 
            packing=parse_percent(row.get('Packing')),
            picking=parse_percent(row.get('Picking')), 
            putaway=parse_percent(row.get('Putaway')),
            receiving=parse_percent(row.get('Receiving')), 
            returns=parse_percent(row.get('Returns')),
            sorting=parse_percent(row.get('Sorting'))
        ).on_conflict_do_update(index_elements=['login'], set_={
            "forklift": parse_percent(row.get('FORKLIFT')), 
            "packing": parse_percent(row.get('Packing')),
            "picking": parse_percent(row.get('Picking')), 
            "putaway": parse_percent(row.get('Putaway')),
            "receiving": parse_percent(row.get('Receiving')), 
            "returns": parse_percent(row.get('Returns')),
            "sorting": parse_percent(row.get('Sorting'))
        })
        await db.execute(stmt)
    await db.commit()
    return len(df)

# --- ZBIORCZA SYNCHRONIZACJA (FULL SYSTEM) ---
async def process_full_system_sync(payload: dict, db: AsyncSession):
    try:
        today = date.today()
        tomorrow = today + timedelta(days=1)
        target_dates = [today, tomorrow]
        
        print(f"📅 Cel synchronizacji grafiku: {today} oraz {tomorrow}")

        # 1. Przetwarzanie Matrycy
        raw_m = payload.get("matryca", [])
        if raw_m:
            df_m = pd.DataFrame(raw_m)
            idx = next((i for i, r in df_m.iterrows() if r.astype(str).str.contains('Login', case=False).any()), 0)
            headers_m = [str(c).strip() for c in df_m.iloc[idx]]
            df_m = pd.DataFrame(df_m.values[idx+1:], columns=headers_m)
            await import_productivity_data(df_m, db)
            print("📊 Matryca zaktualizowana.")

        # 2. Przetwarzanie Grafiku
        raw_g = payload.get("grafik_2026", [])
        if not raw_g: return {"status": "error", "message": "Brak danych grafik_2026"}
        
        df_g = pd.DataFrame(raw_g)
        h_idx = next((i for i, r in df_g.iterrows() if r.astype(str).str.contains('Numer Pracownika', case=False).any()), 0)
        headers_g = [str(c).strip() for c in df_g.iloc[h_idx]]
        df_g = pd.DataFrame(df_g.values[h_idx+1:], columns=headers_g)
        
        # Filtr: tylko pracownicy ze statusem "pracuje"
        if 'Status' in df_g.columns:
            df_g = df_g[df_g['Status'].astype(str).str.strip().str.lower() == 'pracuje']
            print(f"👥 Pracowników do przetworzenia: {len(df_g)}")

        count_sched = 0
        for _, row in df_g.iterrows():
            login = str(row.get('Numer Pracownika', '')).strip()
            if not login or login.lower() == 'nan': continue

            for col_name in headers_g:
                work_date = flexible_date_parser(col_name)
                
                # Zapisujemy tylko jeśli kolumna to data i mieści się w zakresie dziś/jutro
                if work_date and work_date in target_dates:
                    shift = str(row.get(col_name, '')).strip()
                    if shift and shift.lower() != 'nan' and shift != "":
                        stmt = insert(Schedule).values(
                            login=login, work_date=work_date, planned_shift=shift
                        ).on_conflict_do_update(
                            index_elements=['login', 'work_date'], 
                            set_={"planned_shift": shift}
                        )
                        await db.execute(stmt)
                        count_sched += 1
        
        await db.commit()
        print(f"🚀 Sukces! Zapisano {count_sched} wpisów grafiku.")
        return {"status": "success", "message": f"Sync OK! Zapisano {count_sched} rekordów grafiku."}

    except Exception as e:
        print(f"❌ Krytyczny błąd podczas sync: {e}")
        return {"status": "error", "message": str(e)}
    
# --- POBRANIE WSYZSTKICH PRAC 1 I 2, OTWÓRZ I W TOKU. ---


async def sync_active_works(db: AsyncSession):
    print("📡 Rozpoczynam pełny zrzut WHSWorkTable (Open/InProcess)...")
    
    # Twoje zapytanie SQL: workstatus in (0,1) -> Open, InProcess
    filter_query = (
        "WarehouseId eq 'ADM-01' and ("
        "WarehouseWorkStatus eq Microsoft.Dynamics.DataEntities.WHSWorkStatus'Open' or "
        "WarehouseWorkStatus eq Microsoft.Dynamics.DataEntities.WHSWorkStatus'InProcess'"
        ")"
    )
    endpoint = f"WarehouseWorkHeaders?cross-company=true&$filter={filter_query}"
    works_data = await get_data(endpoint)
    
    if not works_data:
        print("ℹ️ Brak aktywnych prac.")
        return

    for w in works_data:
        # Konwersja dat ISO na obiekty datetime
        def p_date(val):
            if not val: return None
            try: return pd.to_datetime(val)
            except: return None

        #  dane do bazy (Upsert)
        stmt = insert(ActiveWork).values(
            workid=w.get("WarehouseWorkId"),
            ordernum=w.get("SourceOrderNumber"),
            shipmentid=w.get("WHAShipmentId"),
            loadid=w.get("WHALoadId"),
            waveid=w.get("WHAWaveId"),
            workpoolid=w.get("WarehouseWorkPoolId"),
            workstatus=str(w.get("WarehouseWorkStatus")),
            worktranstype=w.get("WorkTransactionType"),
            whasalesitemqty=float(w.get("WHASalesItemQty") or 0),
            whasalesitemcount=int(w.get("WHASalesItemCount") or 0),
            whashippingdaterequested=p_date(w.get("WHAShippingDateRequested")),
            whasaleswarehouseshippingdate=p_date(w.get("WHASalesWarehouseShippingDate")),
            workcreateddatetime=p_date(w.get("CreatedDateTime")),
            lockeduser=w.get("UserId"),
            whaadditionalzone2=w.get("WHAAdditionalZone2"),
            whacarriercode=w.get("WHACarrierCode"),
            whashipmentspecid=w.get("WHAShipmentSpecId"),
            targetlicenseplateid=w.get("TargetLicensePlateId"),
            inventlocationid=w.get("WarehouseId"),
            inventsiteid=w.get("SiteId"),
            workpriority=int(w.get("WorkPriority") or 0),
            worktemplatecode=w.get("WorkTemplateCode"),
            dataareaid=w.get("dataAreaId")
        ).on_conflict_do_update(
            index_elements=['workid'],
            set_={
                "workstatus": str(w.get("WarehouseWorkStatus")),
                "lockeduser": w.get("UserId"),
                "whasalesitemqty": float(w.get("WHASalesItemQty") or 0),
                "whasaleswarehouseshippingdate": p_date(w.get("WHASalesWarehouseShippingDate")),
                "whaadditionalzone2": w.get("WHAAdditionalZone2"),
                "whacarriercode": w.get("WHACarrierCode")
            }
        )
        await db.execute(stmt)
    
    await db.commit()
    print(f"🚀 Baza zsynchronizowana. Mamy {len(works_data)} aktywnych rekordów.")