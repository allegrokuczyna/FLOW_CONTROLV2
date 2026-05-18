import httpx
import pandas as pd
from io import StringIO
from datetime import date, timedelta, datetime, time
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import delete, insert, cast, Date, select, func
from sqlalchemy.dialects.postgresql import insert  # Wyłącznie Postgres
from app.core.auth import get_d365_access_token
from app.core.config import settings
from app.db.models import WorkExport, WorkerPerformance, Schedule, ActiveWork, ShiftAssignment, ForecastIntake, ZoneConstraint
from dateutil.parser import parse as parse_date
import logging



# ==============================================================================
# 1. FUNKCJE POMOCNICZE (Parsery i Narzędzia)
# ==============================================================================

def flexible_date_parser(text):
    """Próbuje zamienić nagłówek z Excela na czystą datę."""
    try:
        ts = pd.to_datetime(text, errors='coerce')
        if pd.isna(ts):
            miesiące = {'sty': 1, 'lut': 2, 'mar': 3, 'kwi': 4, 'maj': 5, 'cze': 6,
                        'lip': 7, 'sie': 8, 'wrz': 9, 'paź': 10, 'lis': 11, 'gru': 12}
            parts = str(text).lower().strip().split(' ')
            if len(parts) == 2:
                day = int(parts[0])
                month = miesiące.get(parts[1][:3])
                if month: return date(2026, month, day)
            return None
        if ts.hour == 23:
            ts = ts + timedelta(hours=1)
        return ts.date()
    except:
        return None

def parse_skill_level(value):
    """Zamienia dane z matrycy na poziomy skilli 0-6."""
    if isinstance(value, pd.Series): value = value.iloc[0]
    if pd.isna(value) or value is None or str(value).strip().lower() in ['nan', '', 'none']:
        return 0
    try:
        val = float(value)
        if val == 0: return 0
        elif val <= 6: return int(val)
        elif val <= 50: return 1
        elif val <= 250: return 2
        elif val <= 600: return 3
        elif val <= 1000: return 4
        elif val <= 1500: return 5
        else: return 6
    except:
        return 0



async def get_data(endpoint_url: str):
    """Uniwersalny helper do API D365."""
    token = await get_d365_access_token()
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    base_url = str(settings.D365_URL).strip('/')
    url = f"{base_url}/data/{endpoint_url}"
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.get(url, headers=headers)
        return response.json().get("value", []) if response.status_code == 200 else []

# ==============================================================================
# 2. GŁÓWNY SILNIK SYNCHRONIZACJI (MODEL PUSH)
# ==============================================================================

async def process_full_push_sync(payload: dict, db: AsyncSession):
    report = {}
    today = date.today()
    # Pobieramy dane na 7 dni
    target_dates = [today + timedelta(days=i) for i in range(7)]

    # --- 2.1 MATRYCA SKILLI ---
    try:
        raw_m = payload.get("matryca", [])
        if raw_m and len(raw_m) > 1:
            header_idx = 0
            for i, row in enumerate(raw_m[:10]):
                row_str = [str(cell).lower() for cell in row]
                if any("login" in cell or "numer" in cell or "id" in cell for cell in row_str):
                    header_idx = i
                    break
            headers = [str(c).strip().lower() for c in raw_m[header_idx]]
            data = raw_m[header_idx + 1:]
            df_m = pd.DataFrame(data, columns=headers)
            count_m = await import_productivity_data(df_m, db)
            report["matrix"] = f"Success ({count_m} workers)"
    except Exception as e:
        report["matrix"] = f"Error: {str(e)}"

    # --- 2.2 GRAFIK PRACY ---
    try:
        raw_g = payload.get("grafik", [])
        if raw_g and len(raw_g) > 1:
            header_idx = 0
            for i, row in enumerate(raw_g[:10]):
                row_str = [str(cell).lower() for cell in row]
                if any("numer" in cell or "status" in cell for cell in row_str):
                    header_idx = i
                    break
            
            headers = [str(c).strip() for c in raw_g[header_idx]]
            data = raw_g[header_idx + 1:]
            df_g = pd.DataFrame(data, columns=headers)
            
            # --- FILTR 1: Status (tylko "pracuje") ---
            if 'Status' in df_g.columns:
                df_g = df_g[df_g['Status'].astype(str).str.lower().str.strip() == 'pracuje']
            
            # --- FILTR 2: Grupa (Tylko operacyjne) ---
            if 'Grupa' in df_g.columns:
                allowed_groups = ['operacja', 'operacja apt']
                df_g = df_g[df_g['Grupa'].astype(str).str.lower().str.strip().isin(allowed_groups)]
            
            count_g = 0
            
            # Definiujemy standardowe formaty zmian, które bezwzględnie zapisujemy
            valid_shifts = ['06-16', '12-22', '06-14', '6-14', '14-22', '22-6', '22-06', '16-24']
            
            # Definiujemy śmieci i nieobecności, które ignorujemy (w małych literach)
            ignored_values = ['nan', '', 'null', '0', 'zw', 'nn', 'ub', 'uw']

            for _, row in df_g.iterrows():
                login = str(row.get('Numer Pracownika', '')).strip()
                full_name = str(row.get('Imię i Nazwisko', '')).strip()
                prefix = str(row.get('Prefiks Grupy', '')).strip() 
                
                if not login or login == 'nan' or login == '': 
                    continue
                
                for col in df_g.columns:
                    work_date = flexible_date_parser(col)
                    if work_date in target_dates:
                        
                        raw_val = row.get(col)
                        if hasattr(raw_val, 'iloc'):
                            raw_val = raw_val.iloc[0]
                            
                        shift_val = str(raw_val).strip()
                        
                        # Fix dla biblioteki Pandas ("1.0" -> "1")
                        if shift_val.endswith('.0'):
                            shift_val = shift_val[:-2]
                        
                        # Pomijamy puste dni oraz zdefiniowane wyżej nieobecności (zw, nn, ub)
                        if not shift_val or shift_val.lower() in ignored_values:
                            continue
                            
                        # --- FILTR WARTOSCI ZMIAN ---
                        if shift_val.lower() not in valid_shifts:
                            try:
                                # Sprawdzamy czy to czysta liczba (np. "8" godzin). Jeśli tak - odrzucamy.
                                float(shift_val.replace(',', '.'))
                                continue 
                            except ValueError:
                                # Inne teksty (np. "uw", "szkolenie") - przepuszczamy
                                pass 

                        # Zapis do bazy
                        stmt = insert(Schedule).values(
                            login=login,
                            full_name=full_name if full_name != 'nan' else None,
                            work_date=work_date,
                            planned_shift=shift_val,
                            group_prefix=prefix
                        ).on_conflict_do_update(
                            index_elements=['login', 'work_date'],
                            set_={
                                "planned_shift": shift_val,
                                "full_name": full_name if full_name != 'nan' else None,
                                "group_prefix": prefix
                            }
                        )
                        await db.execute(stmt)
                        count_g += 1

            report["schedule"] = f"Success ({count_g} shifts for valid workers)"
            print(f"✅ [SYNC] Pomyślnie zaktualizowano grafik na najbliższe 7 dni.")
        else:
            report["schedule"] = "No data in grafik"
    except Exception as e:
        report["schedule"] = f"Error: {str(e)}"

    # --- 2.3 FORECAST (bez zmian) ---
    try:
        raw_f = payload.get("forecast", [])
        if raw_f:
            await db.execute(delete(ForecastIntake).where(ForecastIntake.forecast_date.in_(target_dates)))
            new_forecasts = []
            for item in raw_f:
                dt_obj = datetime.fromisoformat(item['dt'].replace('Z', '+00:00'))
                if dt_obj.date() in target_dates:
                    new_forecasts.append(ForecastIntake(
                        forecast_date=dt_obj.date(),      
                        hour_from=dt_obj,                 
                        forecast_pcs=int(item['pcs'])     
                    ))
            if new_forecasts:
                db.add_all(new_forecasts)
            report["forecast"] = f"Success ({len(new_forecasts)} lines)"
    except Exception as e:
        report["forecast"] = f"Error: {str(e)}"

    await db.commit()
    return report


#odczyt z bazy
async def get_weekly_schedule(db: AsyncSession):
    today = date.today()
    days = [today + timedelta(days=i) for i in range(7)]
    
    # Pobieramy wszystkie grafiki na te 7 dni
    stmt = select(Schedule).where(Schedule.work_date.in_(days))
    res = await db.execute(stmt)
    all_schedules = res.scalars().all()

    # Budujemy strukturę: { login: { "full_name": "...", "dates": { "2026-05-15": "6-14", ... } } }
    matrix = {}
    for s in all_schedules:
        if s.login not in matrix:
            matrix[s.login] = {
                "login": s.login,
                "full_name": s.full_name or "Brak danych",
                "days": {}
            }
        matrix[s.login]["days"][str(s.work_date)] = s.planned_shift

    
    return {
        "dates": [str(d) for d in days],
        "workers": list(matrix.values())
    }

# ==============================================================================
# 3. IMPORT PRODUKTYWNOŚCI (Logika 0-6)
# ==============================================================================

async def import_productivity_data(df: pd.DataFrame, db: AsyncSession):
    """
    Importuje matrycę skilli stosując UPSERT w Postgresie.
    Automatycznie czyści nagłówki i mapuje dane.
    """
    df.columns = [str(c).strip().lower() for c in df.columns]
    
    login_col = None
    possible_login_names = ['login', 'nr pracownika', 'numer pracownika', 'id']
    for candidate in possible_login_names:
        if candidate in df.columns:
            login_col = candidate
            break

    if not login_col:
        print("❌ BŁĄD: Nie znaleziono kolumny 'login' w przesłanych danych matrycy!")
        return 0

    def get_val(row, col_name):
        if col_name in df.columns:
            return parse_skill_level(row.get(col_name))
        return 0

    import_count = 0
    
    for _, row in df.iterrows():
        raw_login = str(row.get(login_col, '')).strip()
        
        if not raw_login or raw_login.lower() in ['nan', 'login', 'none', '']:
            continue
            
        login = raw_login

        vals = {
            "receiving": get_val(row, 'receiving'),
            "putaway": get_val(row, 'putaway'),
            "picking": get_val(row, 'picking'),
            "packing": get_val(row, 'packing'),
            "sorting": get_val(row, 'sorting'),
            "forklift": get_val(row, 'forklift'),
            "returns": get_val(row, 'returns')
        }
        
        stmt = insert(WorkerPerformance).values(
            login=login, 
            **vals,
            updated_at=datetime.utcnow() 
        ).on_conflict_do_update(
            index_elements=['login'], 
            set_=vals
        )
        
        await db.execute(stmt)
        import_count += 1
    
    print(f"✅ Przetworzono matrycę: zapisano/zaktualizowano {import_count} pracowników.")
    return import_count




# ==============================================================================
# 4. ANALITYKA I D365
# ==============================================================================

async def sync_works(db: AsyncSession):
    """Pobieranie archiwum prac z D365."""
    url_works = "WarehouseWorkHeaders?cross-company=true&$filter=WarehouseId eq 'ADM-01' and WarehouseWorkStatus eq Microsoft.Dynamics.DataEntities.WHSWorkStatus'Open'&$top=2000"
    works_data = await get_data(url_works)
    if not works_data: return

    for w in works_data:
        if str(w.get("ContainerId") or "").strip() != "": continue
        
        stmt = insert(WorkExport).values(
            work_id=w.get("WarehouseWorkId") or w.get("WorkId"),
            order_num=str(w.get("SourceOrderNumber", "")).strip(),
            item_qty=float(w.get("WHASalesItemQty") or 0),
            work_pool_id=w.get("WarehouseWorkPoolId", "")
        ).on_conflict_do_update(
            index_elements=['work_id'],
            set_={"item_qty": float(w.get("WHASalesItemQty") or 0)}
        )
        await db.execute(stmt)
    await db.commit()

async def sync_active_works(db: AsyncSession):
    """Live Sync prac Open/InProcess - Wersja Transactional Replace z Paczkowaniem (Batches)."""
    print("🚀 START SYNC (Transactional Replace): Pobieram dane z D365...")
    
    filter_query = "WarehouseId eq 'ADM-01' and (WarehouseWorkStatus eq Microsoft.Dynamics.DataEntities.WHSWorkStatus'Open' or WarehouseWorkStatus eq Microsoft.Dynamics.DataEntities.WHSWorkStatus'InProcess')"
    endpoint = f"WarehouseWorkHeaders?cross-company=true&$filter={filter_query}"
    
    try:
        works_data = await get_data(endpoint)
        
        if not works_data:
            print("⚠️ Brak danych z D365 lub błąd połączenia. Przerywam, nie czyszczę bazy (fail-safe).")
            return

        print(f"📦 Pobrano {len(works_data)} rekordów z D365. Przygotowuję dane dla bazy...")

        # Natywny, bezpieczny parser dat z D365 (radzi sobie z "Z" na końcu)
        def safe_date(date_str):
            if not date_str or str(date_str).startswith("1900"): 
                return None
            try:
                return datetime.fromisoformat(str(date_str).replace("Z", "+00:00"))
            except Exception:
                return None

        # 1. Zamiast zapisu wiersz po wierszu, zbieramy wszystko do jednej listy RAM
        to_insert = []
        sync_time = datetime.utcnow()
        
        for w in works_data:
            to_insert.append({
                "workid": w.get("WarehouseWorkId") or w.get("WorkId") or "UNKNOWN",
                "ordernum": w.get("SourceOrderNumber", ""),
                "shipmentid": w.get("ShipmentId", ""),
                "loadid": w.get("LoadId", ""),
                "waveid": w.get("WaveId", ""),
                "workpoolid": w.get("WarehouseWorkPoolId", ""),
                
                "workstatus": w.get("WarehouseWorkStatus", ""),
                "worktranstype": w.get("WarehouseWorkOrderType", ""),
                
                "whasalesitemqty": float(w.get("WHASalesItemQty") or 0.0),
                "whasalesitemcount": int(w.get("WHASalesItemCount") or 0),
                "whaworkitemsvolume": 0.0, # Brak w D365, wstawiamy domyślne 0
                "whaworkitemsweight": 0.0, # Brak w D365, wstawiamy domyślne 0
                
                "whashippingdaterequested": safe_date(w.get("WHAShippingDateRequested")),
                "workcreateddatetime": safe_date(w.get("WarehouseWorkProcessingStartDateTime")), 
                
                "lockeduser": w.get("WarehouseWorkLockingWarehouseMobileDeviceUserId", ""),
                "whaadditionalzone2": w.get("WHAAdditionalZone2", ""),
                "whacarriercode": w.get("WHACarrierCode", ""),
                "whashipmentspecid": w.get("WHAShipmentSpecId", ""),
                "targetlicenseplateid": w.get("TargetLicensePlateNumber", ""),
                "inventlocationid": w.get("WarehouseId", ""),
                "inventsiteid": w.get("InventorySiteId", ""),
                
                "workismultisku": w.get("IsWarehouseWorkBlocked", "No"),
                "frozen": "No",
                
                "workpriority": int(w.get("WorkPriority") or w.get("WarehouseWorkPriority") or 0),
                "worktemplatecode": "",
                "containerid": w.get("ContainerId", ""),
                "clusterid": "",
                "dataareaid": w.get("dataAreaId", ""),
                "lastprocessedchange_datetime": sync_time # Oznaczamy świeżą datą
            })

        # 2. ROZPOCZYNAMY OSTATECZNĄ TRANSAKCJĘ
        if len(to_insert) > 0:
            print(f"🧹 Usuwam stare 'duchy' z bazy i ładuję nową paczkę ({len(to_insert)} wierszy)...")
            
            # Krok A: Usuwamy całkowicie stare dane
            await db.execute(delete(ActiveWork))
            
            # Krok B: Wrzucamy w PACZKACH (Batch Insert)
            chunk_size = 1000 # Rozmiar paczki
            for i in range(0, len(to_insert), chunk_size):
                chunk = to_insert[i:i + chunk_size]
                await db.execute(insert(ActiveWork), chunk)
                print(f"📦 Wstawiono paczkę do bazy: {i + len(chunk)} / {len(to_insert)}...")
        
            await db.commit()
            print(f"✅ SYNC ZAKOŃCZONY: Baza zaktualizowana bez zająknięcia!")
        else:
            print("⚠️ Paczka do zapisu jest pusta. Nie modyfikuję bazy.")

    except Exception as e:
    
        await db.rollback() 
        print(f"🔥 KRYTYCZNY BŁĄD PODCZAS PODMIANY DANYCH: {str(e)}")



async def get_workpool_analytics(db: AsyncSession):
    """Analityka stref dla AI."""
    stmt = select(ActiveWork).where(ActiveWork.workstatus.in_(['Open', 'InProcess', '0', '1']))
    result = await db.execute(stmt)
    active_works = result.scalars().all()
    stats = {"picking": 0, "packing": 0, "inbound": 0, "putaway": 0, "sorting": 0}
    for work in active_works:
        qty = work.whasalesitemqty or 1
        w_pool = str(work.workpoolid).lower()
        if 'pack' in w_pool: stats['packing'] += qty
        elif 'sort' in w_pool: stats['sorting'] += qty
        else: stats['picking'] += qty
    return stats


def get_shift_number(hours_str: str) -> str:
    if not hours_str: return "0"
    
    h = str(hours_str).lower().replace(" ", "").replace(":", "").replace("–", "-").strip()
    
    # ZMIANA I (Rano)
    if any(x in h for x in ["06-14", "6-14", "06-16" "0614", "614", "07-15", "08-16", "12-22"]): 
        return "1"
    
    # ZMIANA II (Popołudnie)
    if any(x in h for x in ["14-22", "1422", "12-20", "16-24"]): 
        return "2"
    
    # ZMIANA III (Noc)
    if any(x in h for x in ["22-06", "2206", "22-6", "22-07"]): 
        return "3"
        
    return "0"

async def get_daily_plan(db: AsyncSession, target_date: date = None):
    """Zwraca plan przydziałów, wczytując zapisane już zadania z bazy."""
    if target_date is None: 
        target_date = date.today()
    
    from sqlalchemy import cast, Date

    # 1. Pobieramy grafiki (kto powinien być w pracy)
    sched_stmt = select(Schedule).where(cast(Schedule.work_date, Date) == target_date)
    sched_res = await db.execute(sched_stmt)
    schedules = sched_res.scalars().all()

    # 2. Pobieramy JUŻ ZAPISANE przypisania
    assign_stmt = select(ShiftAssignment).where(cast(ShiftAssignment.assignment_date, Date) == target_date)
    assign_res = await db.execute(assign_stmt)
    assignments = {a.worker_login: a.task for a in assign_res.scalars().all()}

    # 3. Pobieramy wydajność (skille)
    perf_stmt = select(WorkerPerformance)
    perf_res = await db.execute(perf_stmt)
    performances = {str(p.login): p for p in perf_res.scalars().all()}

    plan_data = []
    for s in schedules:
        hours = str(s.planned_shift).strip()
        if not hours or hours.lower() in ['nan', 'urlop', 'zw', 'none', 'ub']:
            continue
            
        worker_id = str(s.login)
        p = performances.get(worker_id)
        current_task = assignments.get(worker_id, "unassigned")

        plan_data.append({
            "worker_login": worker_id,
            "full_name": s.full_name,  
            "shift": get_shift_number(hours),
            "hours": hours,
            "task": current_task,
            "picking": getattr(p, 'picking', 0) if p else 0,
            "packing": getattr(p, 'packing', 0) if p else 0,
            "receiving": getattr(p, 'receiving', 0) if p else 0,
            "putaway": getattr(p, 'putaway', 0) if p else 0,
            "sorting": getattr(p, 'sorting', 0) if p else 0
        })
        
    return plan_data



async def save_daily_plan(assignments: list, db: AsyncSession, target_date: date = None):
    """
    Kuloodporny zapis planu: Usuwa stare i wstawia nowe rekordy.
    """
    if not assignments:
        return {"status": "empty"}
    
    # Jeśli data nie przyszła z Reacta, bierzemy dzisiejszą
    if target_date is None: 
        target_date = date.today()

    try:
        # Wyciągamy loginy pracowników, których właśnie planujemy
        worker_logins = [str(item['worker_login']) for item in assignments]

        # 1. USUWANIE STARYCH PRZYDZIAŁÓW (Tylko dla tych loginów na ten konkretny dzień)
        del_stmt = delete(ShiftAssignment).where(
            cast(ShiftAssignment.assignment_date, Date) == target_date,
            ShiftAssignment.worker_login.in_(worker_logins)
        )
        await db.execute(del_stmt)

        # 2. PRZYGOTOWANIE NOWYCH DANYCH
        values_to_insert = [
            {
                "worker_login": str(item['worker_login']),
                "shift": str(item['shift']),
                "task": str(item['task']),
                "assignment_date": target_date
            }
            for item in assignments
        ]

        # 3. MASOWE WSTAWIANIE
        if values_to_insert:
            await db.execute(insert(ShiftAssignment).values(values_to_insert))
        
        await db.commit()
        
        print(f"🚀 Zapis zakończony sukcesem: {len(values_to_insert)} osób na dzień {target_date}")
        return {"status": "success", "count": len(values_to_insert)}

    except Exception as e:
        await db.rollback()
        print(f"❌ KRYTYCZNY BŁĄD ZAPISU: {str(e)}")
        raise e

# ==============================================================================
# --- DODATKOWE FUNKCJE POMOCNICZE (DLA AI) ---
# ==============================================================================

def is_worker_on_shift(shift_str: str, current_time: time) -> bool:
    """
    Sprawdza, czy podany czas mieści się w przedziale godzinowym z grafiku (np. '06-14').
    Wykorzystywane przez AI do liczenia aktywnych pracowników.
    """
    if not shift_str or str(shift_str).lower() in ['nan', 'none', '', 'urlop', 'zw']:
        return False
        
    # Parsowanie formatu '06-14' lub '14-22'
    parts = str(shift_str).replace(' ', '').split('-')
    if len(parts) == 2:
        try:
            start_h = int(parts[0])
            end_h = int(parts[1])
            
            # Obsługa zmiany nocnej ('22-06')
            if start_h > end_h:
                return current_time.hour >= start_h or current_time.hour < end_h
            else:
                return start_h <= current_time.hour < end_h
        except ValueError:
            return False
            
    return False


# ==============================================================================
# 5. ZARZĄDZANIE KONSTRYKCJAMI AI (MIN/MAX/PRIO)
# ==============================================================================

async def get_all_constraints(db: AsyncSession):
    """Pobiera wszystkie reguły stref posortowane po priorytecie (P1 -> P6)."""
    stmt = select(ZoneConstraint).order_by(ZoneConstraint.priority.asc())
    result = await db.execute(stmt)
    return result.scalars().all()

async def update_or_create_constraints(db: AsyncSession, constraints_data: list):
    try:
        for raw_item in constraints_data:
            # --- KLUCZOWA ZMIANA: Zamieniamy obiekt Pydantic na słownik ---
            # (Obsługuje zarówno nowe FastAPI v2 jak i starsze v1)
            item = raw_item.model_dump() if hasattr(raw_item, 'model_dump') else raw_item.dict()
            
            # Pobieramy priorytet (np. "P1") i zamieniamy na samą liczbę (1)
            raw_prio = str(item.get('priority', 'P5'))
            # Wyciągamy tylko cyfry z tekstu
            prio_int = int(''.join(filter(str.isdigit, raw_prio)) or 5)

            vals = {
                "zone_name": item.get('zone_name'),
                "category": item.get('category', 'Outbound'),
                "priority": prio_int, # <--- Zapisujemy czysty INTEGER (np. 1)
                "s1_min": int(item.get('s1_min') or 0),
                "s1_max": int(item.get('s1_max') or 0),
                "s2_min": int(item.get('s2_min') or 0),
                "s2_max": int(item.get('s2_max') or 0),
                "s3_min": int(item.get('s3_min') or 0),
                "s3_max": int(item.get('s3_max') or 0),
            }

            if not vals["zone_name"]:
                continue

            stmt = insert(ZoneConstraint).values(**vals).on_conflict_do_update(
                index_elements=['zone_name'],
                set_={k: v for k, v in vals.items() if k != 'zone_name'}
            )
            await db.execute(stmt)
        
        await db.commit()
        return True
    except Exception as e:
        await db.rollback()
        print(f"❌ BŁĄD ZAPISU DO DB: {str(e)}")
        raise e