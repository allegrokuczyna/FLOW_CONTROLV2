import httpx
import pandas as pd
from datetime import date, timedelta, datetime, time  
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert
from app.core.auth import get_d365_access_token
from app.core.config import settings
from app.db.models import WorkExport, WorkerPerformance, Schedule, ActiveWork, ShiftAssignment 
from sqlalchemy import func, select

# ==============================================================================
# 1. FUNKCJE POMOCNICZE (Parsery i Narzędzia)
# ==============================================================================

def flexible_date_parser(text):
    """Próbuje zamienić nagłówek z Excela na czystą datę."""
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


def parse_skill_level(value):
    """Zamienia dane z matrycy (nawet jeśli to surowe ilości z D365) na poziomy skilli 0-6."""
    # Zabezpieczenie przed duplikatami kolumn
    if isinstance(value, pd.Series):
        value = value.iloc[0]
        
    if pd.isna(value) or value is None or str(value).strip().lower() in ['nan', '', 'none']:
        return 0
        
    try:
        val = float(value)
        
        # --- AUTOMATYCZNY KALKULATOR LEVELI (0-6) ---
        if val == 0: 
            return 0
        elif val <= 6: 
            return int(val)  
        elif val <= 50: 
            return 1         
        elif val <= 250: 
            return 2         
        elif val <= 600: 
            return 3         
        elif val <= 1000: 
            return 4         
        elif val <= 1500: 
            return 5         
        else: 
            return 6         
            
    except Exception as e:
        print(f"⚠️ Błąd parsowania skilla: {value} -> {e}")
        return 0


async def get_data(endpoint_url: str):
    """Uniwersalny helper do odpytywania API D365."""
    token = await get_d365_access_token()
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    base_url = str(settings.D365_URL).strip('/')
    url = f"{base_url}/data/{endpoint_url}"
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.get(url, headers=headers)
        return response.json().get("value", []) if response.status_code == 200 else []


def is_worker_on_shift(shift_str: str, current_time: time) -> bool:
    """Sprawdza, czy aktualna godzina mieści się w widełkach zmiany (np. '06:00-14:00')."""
    try:
        if not shift_str or '-' not in str(shift_str):
            return False
        
        clean_shift = str(shift_str).replace(' ', '')
        start_str, end_str = clean_shift.split('-')
        
        def parse_time(t_str):
            parts = t_str.split(':')
            h = int(parts[0])
            m = int(parts[1]) if len(parts) > 1 else 0
            return time(h, m)

        start_time = parse_time(start_str)
        end_time = parse_time(end_str)

        if start_time <= end_time:
            return start_time <= current_time <= end_time
        else:
            return current_time >= start_time or current_time <= end_time
    except:
        return False


def get_shift_number(hours_str: str) -> str:
    """Mapuje formaty np. '06-14', '14-22' na numery zmian 1, 2, 3."""
    if not hours_str: 
        return "0"
    
    h = str(hours_str).lower().replace(" ", "").strip()
    
    if "06-14" in h or "6-14" in h or "08-16" in h or "06-16" in h: return "1"
    if "14-22" in h or "12-22" in h: return "2"
    if "22-06" in h or "22-6" in h: return "3"
    
    if h in ["1", "i", "zmianai"]: return "1"
    if h in ["2", "ii", "zmianaii"]: return "2"
    if h in ["3", "iii", "zmianaiii"]: return "3"

    return "0"


# ==============================================================================
# 2. SYNCHRONIZACJA Z GOOGLE SHEETS (Matryca Skilli i Grafik)
# ==============================================================================

async def import_productivity_data(df: pd.DataFrame, db: AsyncSession):
    """Importuje i tłumaczy Matrycę Skilli (Poziomy 0-6)."""
    df_cols = {str(c).lower().strip(): c for c in df.columns}
    
    def get_val(current_row, col_name):
        actual_col = df_cols.get(col_name.lower())
        return parse_skill_level(current_row.get(actual_col)) if actual_col else 0

    # Szukamy kolumny 'login' (jak widać na screenie, kolumna A)
    login_col = df_cols.get('login')
    if not login_col: 
        print("⚠️ Błąd: Nie znaleziono kolumny 'Login' w matrycy skilli!")
        return 0

    import_count = 0
    for _, row in df.iterrows():
        # --- ZABEZPIECZENIE LOGONU PRZED ZDUPLIKOWANYMI KOLUMNAMI ---
        raw_login = row.get(login_col, '')
        if isinstance(raw_login, pd.Series):
            raw_login = raw_login.iloc[0]
            
        login = str(raw_login).strip()
        if not login or login.lower() == 'nan': continue
            
        # Tłumaczymy angielskie nagłówki z arkusza na bazę danych
        vals = {
            "receiving": get_val(row, 'receiving'),
            "putaway": get_val(row, 'putaway'),
            "picking": get_val(row, 'picking'),
            "packing": get_val(row, 'packing'),
            "sorting": get_val(row, 'sorting'),
            "forklift": get_val(row, 'forklift'),
            "returns": get_val(row, 'returns')
        }
        
        stmt = insert(WorkerPerformance).values(login=login, **vals).on_conflict_do_update(
            index_elements=['login'], set_=vals
        )
        await db.execute(stmt)
        import_count += 1
        
    await db.commit()
    print(f"✅ Zaktualizowano matrycę skilli (0-6) dla {import_count} pracowników.")
    return import_count


async def process_full_system_sync(payload: dict, db: AsyncSession):
    """Główny silnik odbierający payload z Ngroka. Przetwarza Matrycę, a potem Grafik."""
    try:
        today = date.today()
        tomorrow = today + timedelta(days=1)
        target_dates = [today, tomorrow]
        
        print(f"🚀 START ZBIORCZEJ SYNCHRONIZACJI. Szukam dat: {target_dates}")

        # --- 2.1 IMPORT MATRYCY SKILLI ---
        raw_m = payload.get("matryca", [])
        if raw_m and len(raw_m) > 1:
            print(f"🧠 Znaleziono zakładkę Matrycy. Przetwarzam {len(raw_m)} wierszy...")
            df_m = pd.DataFrame(raw_m)
            
            # NOWOŚĆ: Szukamy właściwego wiersza nagłówkowego (tego z napisem "Login")
            h_idx_m = next((i for i, r in df_m.iterrows() if r.astype(str).str.contains('login', case=False).any()), 0)
            headers_m = [str(c).strip() for c in df_m.iloc[h_idx_m]]
            df_m = pd.DataFrame(df_m.values[h_idx_m+1:], columns=headers_m)
            
            await import_productivity_data(df_m, db)
        else:
            print("⚠️ Brak danych Matrycy Skilli w payloadzie.")

        # --- 2.2 IMPORT GRAFIKU PRACY ---
        raw_g = payload.get("grafik_2026", [])
        if not raw_g: 
            return {"status": "error", "message": "Brak danych grafiku (grafik_2026)."}
        
        print(f"📥 Znaleziono dane Grafiku. Przetwarzam {len(raw_g)} wierszy...")
        df_g = pd.DataFrame(raw_g)
        
        # Szukamy wiersza nagłówkowego
        h_idx = next((i for i, r in df_g.iterrows() if r.astype(str).str.contains('Numer Pracownika', case=False).any()), 0)
        headers_g = [str(c).strip() for c in df_g.iloc[h_idx]]
        df_g = pd.DataFrame(df_g.values[h_idx+1:], columns=headers_g)

        # Filtrowanie po statusie "Pracuje"
        if 'Status' in df_g.columns:
            initial_count = len(df_g)
            df_g = df_g[df_g['Status'].astype(str).str.lower().str.contains('pracuje', na=False)]
            print(f"✂️ Po filtrze 'Pracuje': zostało {len(df_g)} z {initial_count} wierszy")

        prefix_col_name = next((c for c in df_g.columns if 'Prefiks Grupy' in str(c)), None)
        count_sched = 0
        
        # Pętla po wierszach grafiku
        for _, row in df_g.iterrows():
            login = str(row.get('Numer Pracownika', '')).strip()
            if not login or login.lower() == 'nan': continue
            
            group_prefix = str(row.get(prefix_col_name, '')).strip() if prefix_col_name else ""

            # Szukamy dzisiejszej i jutrzejszej daty w kolumnach
            for col_name in headers_g:
                work_date = flexible_date_parser(col_name)
                if work_date and work_date in target_dates:
                    shift = str(row.get(col_name, '')).strip()
                    if shift and shift.lower() != 'nan' and shift != "":
                        stmt = insert(Schedule).values(
                            login=login, work_date=work_date, planned_shift=shift, group_prefix=group_prefix
                        ).on_conflict_do_update(
                            index_elements=['login', 'work_date'], 
                            set_={"planned_shift": shift, "group_prefix": group_prefix}
                        )
                        await db.execute(stmt)
                        count_sched += 1
                   
        await db.commit()
        print(f"✅ SUKCES! Zapisałem {count_sched} rekordów do tabeli grafiku (schedules).")
        return {"status": "success", "message": f"Sync OK! Zapisano {count_sched} zmian w grafiku."}

    except Exception as e:
        print(f"❌ BŁĄD SYNC: {str(e)}")
        return {"status": "error", "message": str(e)}


# ==============================================================================
# 3. SYNCHRONIZACJA Z SYSTEMEM D365 (Prace Magazynowe)
# ==============================================================================

async def sync_works(db: AsyncSession):
    """Pobieranie pełnego archiwum prac otwartych (SNAJPER)."""
    print("🔄 Start synchronizacji prac Dynamics...")
    url_works = "WarehouseWorkHeaders?cross-company=true&$filter=WarehouseId eq 'ADM-01' and WarehouseWorkStatus eq Microsoft.Dynamics.DataEntities.WHSWorkStatus'Open'&$top=2000"
    
    works_data = await get_data(url_works)
    if not works_data:
        print("⚠️ Brak otwartych prac w D365 dla magazynu ADM-01.")
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
    print(f"✅ Dynamics OK. Zsynchronizowano {len(valid_works)} prac archiwalnych.")


async def sync_active_works(db: AsyncSession):
    """Odświeża tabelę prac Open i InProcess w locie (LIVE SYNC)."""
    filter_query = "WarehouseId eq 'ADM-01' and (WarehouseWorkStatus eq Microsoft.Dynamics.DataEntities.WHSWorkStatus'Open' or WarehouseWorkStatus eq Microsoft.Dynamics.DataEntities.WHSWorkStatus'InProcess')"
    endpoint = f"WarehouseWorkHeaders?cross-company=true&$filter={filter_query}"
    works_data = await get_data(endpoint)
    if not works_data: return

    for w in works_data:
        def p_date(val):
            if not val: return None
            try: return pd.to_datetime(val)
            except: return None

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


# ==============================================================================
# 4. ANALITYKA I OBSŁUGA GRAFIKU DLA FRONTENDU
# ==============================================================================

async def get_workpool_analytics(db: AsyncSession):
    """Tłumaczy żargon D365 na zrozumiałe strefy dla Frontendu i Mózgu AI."""
    stmt = select(ActiveWork).where(
        ActiveWork.workstatus.in_(['0', '1', 'Open', 'InProcess', '0.0', '1.0'])
    )
    result = await db.execute(stmt)
    active_works = result.scalars().all()

    stats = {
        "picking": 0,
        "packing": 0,
        "inbound": 0,
        "putaway": 0,
        "sorting": 0
    }

    for work in active_works:
        qty = work.whasalesitemqty if work.whasalesitemqty else 1 
        
        w_type = str(work.worktranstype).lower() if work.worktranstype else ""
        w_template = str(work.worktemplatecode).lower() if work.worktemplatecode else ""
        w_pool = str(work.workpoolid).lower() if work.workpoolid else ""

        # A) Sales / Wychodzące
        if 'sales' in w_type or 'issue' in w_type:
            if 'pack' in w_template or 'pack' in w_pool:
                stats['packing'] += qty
            elif 'sort' in w_template or 'sort' in w_pool:
                stats['sorting'] += qty
            else:
                stats['picking'] += qty
                
        # B) Purch / Przychodzące
        elif 'purch' in w_type or 'receipt' in w_type:
            if 'put' in w_template:
                stats['putaway'] += qty
            else:
                stats['inbound'] += qty
                
        # C) Fallback
        else:
            stats['picking'] += qty

    return stats


async def get_daily_plan(db: AsyncSession, target_date: date = None):
    """Pobiera i scala grafik z ręcznymi przydziałami, przygotowując dane dla UI."""
    try:
        if target_date is None:
            target_date = date.today()

        sched_stmt = select(Schedule).where(Schedule.work_date == target_date)
        sched_res = await db.execute(sched_stmt)
        schedules = sched_res.scalars().all()

        assign_stmt = select(ShiftAssignment).where(ShiftAssignment.assignment_date == target_date)
        assign_res = await db.execute(assign_stmt)
        
        assignments = {}
        for a in assign_res.scalars().all():
            assignments[a.worker_login] = a.task

        plan_data = []
        for s in schedules:
            hours = str(s.planned_shift).strip()
            
            if not hours or hours.lower() in ['nan', 'none', '', 'zw', 'urlop']:
                continue

            shift_id = get_shift_number(hours)
            current_task = assignments.get(s.login, 'unassigned')

            plan_data.append({
                "login": str(s.login),
                "shift": str(shift_id),
                "hours": hours,
                "task": str(current_task)
            })

        return plan_data
    except Exception as e:
        print(f"❌ KRYTYCZNY BŁĄD W GET_DAILY_PLAN: {str(e)}")
        raise e 


async def save_daily_plan(assignments: list, db: AsyncSession, target_date: date = None):
    """Zapisuje przydziały do stref przeciągnięte przez użytkownika."""
    try:
        if target_date is None:
            target_date = date.today()

        count = 0
        for item in assignments:
            stmt = insert(ShiftAssignment).values(
                worker_login=item['worker_login'],
                shift=item['shift'],
                task=item['task'],
                assignment_date=target_date
            ).on_conflict_do_update(
                index_elements=['worker_login', 'assignment_date'],
                set_={
                    "task": item['task'], 
                    "shift": item['shift'] 
                } 
            )
            await db.execute(stmt)
            count += 1
            
        await db.commit()
        return {"status": "success", "message": f"Zapisano {count} przypisań."}
    except Exception as e:
        await db.rollback()
        print(f"❌ KRYTYCZNY BŁĄD W ZAPISIE: {str(e)}")
        raise e