import io
import token
import httpx
import pandas as pd
from datetime import date, timedelta, datetime, time
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import delete, insert, cast, Date, select, func
from sqlalchemy.dialects.postgresql import insert  # Wyłącznie Postgres do UPSERT
from app.core.auth import get_d365_access_token
from app.core.config import settings
from app.db.models import WorkerPerformance, Schedule, ShiftAssignment, ForecastIntake, ZoneConstraint, WorkerSpecialTask, SortWork
import logging

# ==============================================================================
# 1. FUNKCJE POMOCNICZE (Parsery i Narzędzia)
# ==============================================================================

def flexible_date_parser(text):
    """Próbuje zamienić nagłówek z Excela lub Timestamp na czystą datę."""
    if isinstance(text, (datetime, date)):
        return text.date() if isinstance(text, datetime) else text
        
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

# ==============================================================================
# 2. GŁÓWNY SILNIK IMPORTU Z EXCELA
# ==============================================================================

async def process_excel_master(contents: bytes, db: AsyncSession):
    """
    Funkcja przetwarzająca wielki arkusz Excel:
    - Zakładka 0: Forecast 1P, Forecast 1F, Matryca Skilli
    - Zakładka 1: Grafik (zabezpieczona przed brakiem drugiej zakładki)
    """
    today = date.today()
    # Szerokie okno czasowe: 14 dni wstecz, 30 dni w przód
    target_dates = [today + timedelta(days=i) for i in range(-14, 31)]
    report = {}

    try:
        excel_file = pd.ExcelFile(io.BytesIO(contents))
    except Exception as e:
        return {"forecast_matrix": f"Krytyczny błąd otwierania pliku Excel: {str(e)}"}

    # -------------------------------------------------------------------------
    # 2.1 PRZETWARZANIE GRAFIKU
    # -------------------------------------------------------------------------
    if len(excel_file.sheet_names) > 1:
        try:
            df_g_raw = pd.read_excel(excel_file, sheet_name=1, header=None)
            
            header_idx = 0
            for i, row in df_g_raw.head(10).iterrows():
                row_str = [str(cell).lower() for cell in row.values]
                if any("numer" in cell or "status" in cell for cell in row_str):
                    header_idx = i
                    break
            
            df_g = pd.read_excel(excel_file, sheet_name=1, header=header_idx)
            
            if 'Status' in df_g.columns:
                df_g = df_g[df_g['Status'].astype(str).str.lower().str.strip() == 'pracuje']
            if 'Prefiks Grupy' in df_g.columns:
                df_g = df_g[df_g['Prefiks Grupy'].astype(str).str.upper().str.strip() == 'O']

            count_g = 0
            valid_shifts = ['06-16', '12-22', '06-14', '6-14', '14-22', '22-6', '22-06', '16-24']
            ignored_values = ['nan', '', 'null', '0', 'zw', 'nn', 'ub', 'uw']

            for _, row in df_g.iterrows():
                login = str(row.get('Numer Pracownika', '')).strip()
                full_name = str(row.get('Imię i Nazwisko', '')).strip()
                prefix = str(row.get('Prefiks Grupy', '')).strip() 
                
                # --- NOWE: Odczyt kolumny "Proces" ---
                process_val = str(row.get('Proces', '')).strip()
                if not process_val or process_val.lower() == 'nan':
                    process_val = None
                
                if not login or login.lower() == 'nan': 
                    continue
                
                for col in df_g.columns:
                    # --- NOWE: Ignorujemy kolumnę "Proces", żeby nie traktował jej jako daty ---
                    if col in ['Numer Pracownika', 'Imię i Nazwisko', 'Status', 'Prefiks Grupy', 'Proces']:
                        continue
                        
                    work_date = flexible_date_parser(col)
                    
                    # --- AUTOKOREKTA AMERYKAŃSKICH DAT W GRAFIKU ---
                    if work_date and work_date not in target_dates:
                        try:
                            swapped_date = work_date.replace(month=work_date.day, day=work_date.month)
                            if swapped_date in target_dates:
                                work_date = swapped_date
                        except ValueError:
                            pass
                            
                    if work_date and work_date in target_dates:
                        raw_val = row.get(col)
                        shift_val = str(raw_val).strip()
                        
                        if shift_val.endswith('.0'):
                            shift_val = shift_val[:-2]
                        
                        if not shift_val or shift_val.lower() in ignored_values:
                            continue
                            
                        if shift_val.lower() not in valid_shifts:
                            try:
                                float(shift_val.replace(',', '.'))
                                continue 
                            except ValueError:
                                pass 

                        # --- NOWE: Zapis kolumny process_val do bazy ---
                        stmt = insert(Schedule).values(
                            login=login,
                            full_name=full_name if full_name != 'nan' else None,
                            work_date=work_date,
                            planned_shift=shift_val,
                            group_prefix=prefix,
                            process=process_val 
                        ).on_conflict_do_update(
                            index_elements=['login', 'work_date'],
                            set_={
                                "planned_shift": shift_val,
                                "full_name": full_name if full_name != 'nan' else None,
                                "group_prefix": prefix,
                                "process": process_val
                            }
                        )
                        await db.execute(stmt)
                        count_g += 1

            report["schedule"] = f"Sukces ({count_g} zmian wgranych)"
        except Exception as e:
            report["schedule"] = f"Błąd grafiku: {e}"
    else:
        report["schedule"] = "Pominięto (W skoroszycie wykryto tylko jedną zakładkę)"

    # -------------------------------------------------------------------------
    # 2.2 PRZETWARZANIE FORECASTU I MATRYCY 
    # -------------------------------------------------------------------------
    try:
        df_master = pd.read_excel(excel_file, sheet_name=0, header=1)
        
        df_1p = df_master.iloc[:, 0:6]
        df_1f = df_master.iloc[:, 6:12]

        login_idx = 12 
        for idx, col_name in enumerate(df_master.columns):
            if str(col_name).strip().lower() == 'login':
                login_idx = idx
                break
                
        df_matrix = df_master.iloc[:, login_idx:]

        await db.execute(delete(ForecastIntake).where(ForecastIntake.forecast_date.in_(target_dates)))
        new_forecasts = []
        
        def parse_forecast_stream(df_stream, client_label):
            last_valid_date = None
            
            for _, row in df_stream.iterrows():
                raw_date = row.iloc[0]
                
                # 1. Scalone komórki (puste) podciągamy pod ostatnią dobrą datę
                if pd.isna(raw_date) or str(raw_date).strip() == '' or str(raw_date).lower() == 'nan':
                    if last_valid_date is not None:
                        date_val = last_valid_date
                    else:
                        continue
                else:
                    if isinstance(raw_date, (datetime, pd.Timestamp)):
                        date_val = raw_date
                        # --- AUTOKOREKTA AMERYKAŃSKICH DAT W FORECAŚCIE ---
                        if date_val.date() not in target_dates:
                            try:
                                swapped = date_val.replace(month=date_val.day, day=date_val.month)
                                if swapped.date() in target_dates:
                                    date_val = swapped
                            except Exception:
                                pass
                    else:
                        raw_str = str(raw_date).replace('.', '/').replace('-', '/').strip()
                        
                        # Fix dla dwucyfrowych lat (26 -> 2026)
                        parts = raw_str.split('/')
                        if len(parts) == 3 and len(parts[2]) == 2:
                            parts[2] = "20" + parts[2]
                            raw_str = "/".join(parts)

                        date_val = pd.to_datetime(raw_str, errors='coerce', dayfirst=True)
                        
                        if pd.notna(date_val) and date_val.date() not in target_dates:
                            alt_date = pd.to_datetime(raw_str, errors='coerce', dayfirst=False)
                            if pd.notna(alt_date) and alt_date.date() in target_dates:
                                date_val = alt_date

                    if pd.isna(date_val):
                        continue
                        
                    last_valid_date = date_val
                    
                if date_val.date() in target_dates:
                    # 2. Parsowanie godziny
                    hour_dt = datetime.combine(date_val.date(), time(0, 0))
                    try:
                        raw_time = row.iloc[2]
                        if pd.notna(raw_time):
                            if isinstance(raw_time, time):
                                hour_dt = datetime.combine(date_val.date(), raw_time)
                            elif isinstance(raw_time, (datetime, pd.Timestamp)):
                                hour_dt = datetime.combine(date_val.date(), raw_time.time())
                            else:
                                t_parsed = pd.to_datetime(str(raw_time).strip(), errors='coerce')
                                if pd.notna(t_parsed):
                                    hour_dt = datetime.combine(date_val.date(), t_parsed.time())
                    except Exception:
                        pass 

                    # 3. Parsowanie PCS
                    try:
                        pcs_val = float(row.iloc[5]) if pd.notna(row.iloc[5]) else 0
                    except (ValueError, TypeError):
                        pcs_val = 0
                        
                    new_forecasts.append(ForecastIntake(
                        forecast_date=date_val.date(),      
                        hour_from=hour_dt,             
                        forecast_pcs=int(pcs_val), 
                        client_type=client_label
                    ))

        parse_forecast_stream(df_1p, "1P")
        parse_forecast_stream(df_1f, "1F")

        if new_forecasts:
            db.add_all(new_forecasts)
        report["forecast"] = f"Sukces (Wgrano {len(new_forecasts)} rzędów forecastu z podziałem godzinowym)"

        # -- MATRYCA PRACOWNIKÓW --
        def get_skill_val(row_data, skill_keywords):
            for col_name in df_matrix.columns:
                col_lower = str(col_name).lower()
                if any(kw in col_lower for kw in skill_keywords):
                    return parse_skill_level(row_data[col_name])
            return 0

        count_m = 0
        for _, row in df_matrix.iterrows():
            login = str(row.iloc[0]).strip()
            if not login or login.lower() in ['nan', 'none', '', 'login']:
                continue

            vals = {
                "receiving": get_skill_val(row, ['receiving', 'rec']),
                "putaway": get_skill_val(row, ['putaway', 'put']),
                "picking": get_skill_val(row, ['picking', 'pick']),
                "packing": get_skill_val(row, ['packing', 'pack']),
                "sorting": get_skill_val(row, ['sorting', 'sort']),
                "forklift": get_skill_val(row, ['forklift', 'wózk']),
                "returns": get_skill_val(row, ['returns', 'zwrot'])
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
            count_m += 1

        report["matrix"] = f"Sukces ({count_m} zaktualizowanych skilli)"

    except Exception as e:
        report["forecast_matrix"] = f"Błąd przetwarzania 1P/1F/Matrycy: {str(e)}"

    await db.commit()
    return report

# ==============================================================================
# 3. ODCZYT GRAFIKU / PLANOWANIE ZADAŃ
# ==============================================================================

async def get_weekly_schedule(db: AsyncSession):
    today = date.today()
    days = [today + timedelta(days=i) for i in range(7)]
    
    stmt = select(Schedule).where(Schedule.work_date.in_(days))
    res = await db.execute(stmt)
    all_schedules = res.scalars().all()

    matrix = {}
    for s in all_schedules:
        if s.login not in matrix:
            matrix[s.login] = {
                "login": s.login,
                "full_name": s.full_name or "Brak danych",
                "process": s.process,
                "days": {}
            }
        matrix[s.login]["days"][str(s.work_date)] = s.planned_shift

    return {
        "dates": [str(d) for d in days],
        "workers": list(matrix.values())
    }

def get_shift_number(hours_str: str) -> str:
    if not hours_str: return "0"
    h = str(hours_str).lower().replace(" ", "").replace(":", "").replace("–", "-").strip()
    if any(x in h for x in ["06-14", "6-14", "06-16", "0614", "614", "07-15", "08-16", "12-22"]): 
        return "1"
    if any(x in h for x in ["14-22", "1422", "12-20", "16-24"]): 
        return "2"
    if any(x in h for x in ["22-06", "2206", "22-6", "22-07"]): 
        return "3"
    return "0"

async def get_daily_plan(db: AsyncSession, target_date: date = None):
    if target_date is None: 
        target_date = date.today()
    
    # 1. Pobieramy grafiki, przypisania i skille (to już miałeś)
    sched_stmt = select(Schedule).where(cast(Schedule.work_date, Date) == target_date)
    sched_res = await db.execute(sched_stmt)
    schedules = sched_res.scalars().all()

    assign_stmt = select(ShiftAssignment).where(cast(ShiftAssignment.assignment_date, Date) == target_date)
    assign_res = await db.execute(assign_stmt)
    assignments = {a.worker_login: a.task for a in assign_res.scalars().all()}

    perf_stmt = select(WorkerPerformance)
    perf_res = await db.execute(perf_stmt)
    performances = {str(p.login): p for p in perf_res.scalars().all()}

    # --- NOWE: 2. Pobieramy zadania specjalne (indirects) ---
    special_stmt = select(WorkerSpecialTask)
    special_res = await db.execute(special_stmt)
    # Tworzymy słownik { "login": "nazwa_zadania" } do szybkiego wyszukiwania
    special_tasks = {str(s.login): s.task_name for s in special_res.scalars().all()}

    plan_data = []
    for s in schedules:
        hours = str(s.planned_shift).strip()
        if not hours or hours.lower() in ['nan', 'urlop', 'zw', 'none', 'ub']:
            continue
            
        worker_id = str(s.login)
        p = performances.get(worker_id)
        

        current_task = assignments.get(worker_id)

        if not current_task:
            current_task = special_tasks.get(worker_id, "unassigned")

        plan_data.append({
            "worker_login": worker_id,
            "full_name": s.full_name,  
            "shift": get_shift_number(hours),
            "hours": hours,
            "task": current_task,       
            "is_present": bool(s.is_present), 
            "process": s.process,      
            "picking": getattr(p, 'picking', 0) if p else 0,
            "packing": getattr(p, 'packing', 0) if p else 0,
            "receiving": getattr(p, 'receiving', 0) if p else 0,
            "putaway": getattr(p, 'putaway', 0) if p else 0,
            "sorting": getattr(p, 'sorting', 0) if p else 0
        })
        
    return plan_data

async def save_daily_plan(assignments: list, db: AsyncSession, target_date: date = None):
    if not assignments:
        return {"status": "empty"}
    
    if target_date is None: 
        target_date = date.today()

    try:
        worker_logins = [str(item['worker_login']) for item in assignments]

        del_stmt = delete(ShiftAssignment).where(
            cast(ShiftAssignment.assignment_date, Date) == target_date,
            ShiftAssignment.worker_login.in_(worker_logins)
        )
        await db.execute(del_stmt)

        values_to_insert = [
            {
                "worker_login": str(item['worker_login']),
                "shift": str(item['shift']),
                "task": str(item['task']),
                "assignment_date": target_date
            }
            for item in assignments
        ]

        if values_to_insert:
            await db.execute(insert(ShiftAssignment).values(values_to_insert))
        
        await db.commit()
        return {"status": "success", "count": len(values_to_insert)}

    except Exception as e:
        await db.rollback()
        raise e

# ==============================================================================
# 4. DODATKOWE FUNKCJE POMOCNICZE (DLA AI)
# ==============================================================================

def is_worker_on_shift(shift_str: str, current_time: time) -> bool:
    if not shift_str or str(shift_str).lower() in ['nan', 'none', '', 'urlop', 'zw']:
        return False
        
    parts = str(shift_str).replace(' ', '').split('-')
    if len(parts) == 2:
        try:
            start_h = int(parts[0])
            end_h = int(parts[1])
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

async def get_all_constraints(db: AsyncSession, target_date: date):
    stmt = select(ZoneConstraint).where(
        ZoneConstraint.target_date == target_date
    ).order_by(ZoneConstraint.priority.asc())
    result = await db.execute(stmt)
    return result.scalars().all()

async def update_or_create_constraints(db: AsyncSession, target_date: str | date, constraints_data: list):
    try:
        if isinstance(target_date, str):
            target_date = date.fromisoformat(target_date)

        for raw_item in constraints_data:
            item = raw_item.model_dump() if hasattr(raw_item, 'model_dump') else raw_item.dict()
            raw_prio = str(item.get('priority', 'P5'))
            prio_int = int(''.join(filter(str.isdigit, raw_prio)) or 5)

            vals = {
                "target_date": target_date,
                "zone_name": item.get('zone_name'),
                "category": item.get('category', 'Outbound'),
                "priority": prio_int,
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
                index_elements=['zone_name', 'target_date'],
                set_={k: v for k, v in vals.items() if k not in ['zone_name', 'target_date']}
            )
            await db.execute(stmt)
        
        await db.commit()
        return True
    except Exception as e:
        await db.rollback()
        raise e

# ==============================================================================
# 6. ANALITYKA I D365 (Nowa Architektura QRDE)
# ==============================================================================

async def get_workpool_analytics(db: AsyncSession):
    """Zlicza ilości w danych pulach na podstawie przefiltrowanej bazy ActiveWork."""
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

async def sync_active_works_from_d365(db: AsyncSession):
    """Błyskawiczne pobieranie danych z D365 przy użyciu usługi REST (QRDE)."""
    print(f"[{datetime.now()}] 🔄 Rozpoczynam pobieranie otwartych prac z D365 (QRDE)...")

    try:
        # 1. Pobieramy token i budujemy URL
        token = await get_d365_access_token()
        base_url = settings.D365_URL.rstrip('/')
        d365_endpoint = f"{base_url}/api/services/IWSQRDE/QRDE/GetRows"

        # 2. Payload wskazujący zapytanie SQL po stronie Microsoft Dynamics
        payload = {
            "_request": {
                "Message": {
                    "RequestID": "fastapi-sync-works",
                    "RequestType": "GetRows",
                    "RequestService": "QRDE",
                    "RequestSource": "FastAPI" 
                },
                "EndpointParamName": "SalesWithoutShippingType", 
                "QueryValues": []
            }
        }

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}"
        }

        # 3. Wykonujemy żądanie POST do Dynamics 365
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(d365_endpoint, json=payload, headers=headers)
            response.raise_for_status() 
            
            d365_data = response.json()
            rows = d365_data 
            
            if not rows or not isinstance(rows, list):
                print("⚠️ D365 zwróciło pustą listę lub błędny format. Brak otwartych prac.")
                return

            # 4. Normalizacja i mapowanie kluczy na małe litery
            mapped_rows = []
            for row in rows:
                mapped_rows.append({str(k).lower(): v for k, v in row.items()})

            # 5. Zapis Pełnego Snapshotu w bazie
            await db.execute(delete(ActiveWork))
            db.add_all([ActiveWork(**row) for row in mapped_rows])
            await db.commit()
            print(f"✅ Sukces! Zaktualizowano Live Status. Zapisano {len(mapped_rows)} prac.")

    except httpx.HTTPStatusError as exc:
        print(f"❌ [HTTP D365 ERROR] Błąd {exc.response.status_code}: {exc.response.text}")
    except Exception as e:
        await db.rollback()
        print(f"❌ [BŁĄD APLIKACJI] Błąd synchronizacji prac: {str(e)}")



import httpx
from datetime import datetime
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.auth import get_d365_access_token
from app.db.models import InboundMezzanineWorks, InventoryQty, PackingWork

async def fetch_and_save_workpool_volumes(db: AsyncSession):
    token = await get_d365_access_token()

    base_url = settings.D365_URL.rstrip('/')
    d365_endpoint = f"{base_url}/api/services/IWSQRDE/QRDE/GetRows"

    # 1. Dokładnie ten sam payload co w działającym teście
    payload = {
        "_request": {
            "Message": {
                "RequestID": "fastapi-sandbox-sync",
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

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(d365_endpoint, json=payload, headers=headers)
            response.raise_for_status() 
            data = response.json()

        # Wyciągamy tablicę Rows
        rows = data.get("Rows") or []
        
    except httpx.HTTPStatusError as exc:
        print(f"❌ Błąd silnika D365: {exc.response.text}")
        raise exc
    except Exception as e:
        print(f"❌ Błąd połączenia lub pobierania danych: {e}")
        raise e

    if not rows:
        print("⚠️ Brak danych z QRDE (Zwróciło pustą tablicę lub null).")
        return 0

    values = []

    # 2. Parsowanie dopasowane 1:1 do Twojego JSON-a
    for row in rows:
        columns = row.get("Columns") or []
        
        # Tworzymy płaski słownik z { "FieldName": "Value" }
        row_dict = {}
        for col in columns:
            field_name = col.get("FieldName")
            if field_name:
                row_dict[field_name] = col.get("Value")
        
        # Wyciągamy wartości dokładnie po kluczach z JSON-a
        workpool_id = row_dict.get("workpoolid")
        
        if not workpool_id:
            continue
            
        values.append({
            "work_pool_id": str(workpool_id),
            "work_count": int(row_dict.get("IloscPrac") or 0),
            "item_qty": float(row_dict.get("IloscSztuk") or 0.0)
        })

    if not values:
        return 0

    # 3. Zapis do PostgreSQL
    stmt = insert(InboundMezzanineWorks).values(values)
    
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
    
    print(f"✅ Pomyślnie zaktualizowano {len(values)} procesów z QRDE w bazie PostgreSQL.")
    return len(values)


#inventsum towarow w lokalizacjach przyjecia 
async def fetch_and_save_inventory_qty(db: AsyncSession):
  
    token = await get_d365_access_token()
    base_url = settings.D365_URL.rstrip('/')
    d365_endpoint = f"{base_url}/api/services/IWSQRDE/QRDE/GetRows"

    payload = {
        "_request": {
            "Message": {
                "RequestID": "fastapi-inventory-sync",
                "RequestType": "GetRows",
                "RequestService": "QRDE",
                "RequestSource": "FastAPI-Sync"
            },
            
            "EndpointParamName": "InbRecQty", 
            "QueryValues": []
        }
    }

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    }

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(d365_endpoint, json=payload, headers=headers)
            response.raise_for_status() 
            data = response.json()

        rows = data.get("Rows") or []
        
    except Exception as e:
        print(f"❌ Błąd pobierania InventoryQty: {e}")
        raise e

    if not rows:
        print("⚠️ Brak danych Inventory z QRDE.")
        return 0

    
    row = rows[0] 
    columns = row.get("Columns", [])
    row_dict = {col.get("FieldName"): col.get("Value") for col in columns if "FieldName" in col}
    
    
    total_qty = int(float(row_dict.get("availphysical") or 0))

    
    values = [{
        "id": 1,
        "available_physical": total_qty
    }]

    
    stmt = insert(InventoryQty).values(values)
    
    stmt = stmt.on_conflict_do_update(
        index_elements=['id'], 
        set_={
            "available_physical": stmt.excluded.available_physical,
            "updated_at": datetime.utcnow()
        }
    )

    await db.execute(stmt)
    await db.commit()
    
    print(f"✅ Pomyślnie zaktualizowano stan technicznych przyjęć: {total_qty} szt.")
    return 1



import httpx
from datetime import datetime
from sqlalchemy import delete
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.auth import get_d365_access_token
from app.db.models import OutboundWork

async def fetch_and_save_outbound_works(db: AsyncSession):
    
    token = await get_d365_access_token()
    base_url = settings.D365_URL.rstrip('/')
    d365_endpoint = f"{base_url}/api/services/IWSQRDE/QRDE/GetRows"

    payload = {
        "_request": {
            "Message": {
                "RequestID": f"fastapi-outbound-{int(datetime.utcnow().timestamp())}",
                "RequestType": "GetRows",
                "RequestService": "QRDE",
                "RequestSource": "FastAPI-Sync"
            },

            "EndpointParamName": "OutFlowControl", 
            "QueryValues": []
        }
    }

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(d365_endpoint, json=payload, headers=headers)
            response.raise_for_status() 
            data = response.json()

        rows = data.get("Rows") or []
        
    except Exception as e:
        print(f"❌ Błąd pobierania Outbound z QRDE: {e}")
        raise e

    if not rows:
        print("⚠️ Brak danych Outbound z QRDE (Zwrócono puste). Czyszczę tabelę.")
        # Jeśli nie ma prac, czyścimy bazę do zera
        await db.execute(delete(OutboundWork))
        await db.commit()
        return 0

    values = []


    for row in rows:
        columns = row.get("Columns") or []
        row_dict = {col.get("FieldName"): col.get("Value") for col in columns if "FieldName" in col}
        
        workpool_id = row_dict.get("workpoolid")
        
        if not workpool_id:
            continue
            

        carrier = row_dict.get("whacarriercode") or "BRAK"
        
        values.append({
            "work_pool_id": str(workpool_id),
            "carrier": str(carrier),
            "work_qty": int(float(row_dict.get("TotalQty") or 0.0))
        })

    if not values:
        return 0

 
    await db.execute(delete(OutboundWork))
    
  
    stmt = insert(OutboundWork).values(values)
    await db.execute(stmt)
    await db.commit()
    
    print(f"✅ Pomyślnie nadpisano {len(values)} procesów Outbound w bazie PostgreSQL.")
    return len(values)





async def fetch_and_save_packing_qty(db: AsyncSession):
    token = await get_d365_access_token()
    base_url = settings.D365_URL.rstrip('/')
    d365_endpoint = f"{base_url}/api/services/IWSQRDE/QRDE/GetRows"

    payload = {
        "_request": {
            "Message": {

                "RequestID": "fastapi-packing-sync", 
                "RequestType": "GetRows",
                "RequestService": "QRDE",
                "RequestSource": "FastAPI-Sync"
            },
            "EndpointParamName": "FlowPackQuery", 
            "QueryValues": []
        }
    }

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(d365_endpoint, json=payload, headers=headers)
            response.raise_for_status() 
            data = response.json()

        rows = data.get("Rows") or []
        
    except Exception as e:
        print(f"❌ Błąd pobierania ilości do pakowania z QRDE: {e}")
        raise e

    if not rows:
        print("⚠️ Brak danych do pakowania z QRDE.")
        return 0

    row = rows[0] 
    columns = row.get("Columns", [])
    

    row_dict = {col.get("FieldName"): col.get("Value") for col in columns if "FieldName" in col}

    total_qty = float(row_dict.get("availphysical") or 0.0)

    
    values = [{
        "id": 1,
        "value": total_qty
    }]


    stmt = insert(PackingWork).values(values)
    
    stmt = stmt.on_conflict_do_update(
        index_elements=['id'], 
        set_={
            "value": stmt.excluded.value,
            "updated_at": datetime.utcnow()
        }
    )

    await db.execute(stmt)
    await db.commit()
    
    print(f"✅ Pomyślnie zaktualizowano stan sztuk do pakowania: {total_qty}")
    return 1



async def fetch_and_save_sort_qty(db: AsyncSession):
    token = await get_d365_access_token()
    base_url = settings.D365_URL.rstrip('/')
    d365_endpoint = f"{base_url}/api/services/IWSQRDE/QRDE/GetRows"

    payload = {
        "_request": {
            "Message": {
                "RequestID": "fastapi-sort-sync",
                "RequestType": "GetRows",
                "RequestService": "QRDE",
                "RequestSource": "FastAPI-Sync"
            },
            "EndpointParamName": "FlowSortQuery", 
            "QueryValues": []
        }
    }

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(d365_endpoint, json=payload, headers=headers)
            response.raise_for_status() 
            data = response.json()

        rows = data.get("Rows") or []
        
    except Exception as e:
        print(f"❌ Błąd pobierania ilości do sortowania z QRDE: {e}")
        raise e

    if not rows:
        print("⚠️ Brak danych do sortowania z QRDE.")
        return 0

    row = rows[0] 
    columns = row.get("Columns", [])
    row_dict = {col.get("FieldName"): col.get("Value") for col in columns if "FieldName" in col}
    
    
    total_qty = float(row_dict.get("qty") or 0.0)

 
    values = [{
        "id": 1,
        "qty": total_qty
    }]

    stmt = insert(SortWork).values(values)
    
    stmt = stmt.on_conflict_do_update(
        index_elements=['id'], 
        set_={
            "qty": stmt.excluded.qty,
            "updated_at": datetime.utcnow()
        }
    )

    await db.execute(stmt)
    await db.commit()
    
    print(f"✅ Pomyślnie zaktualizowano stan paczek do sortowania: {total_qty}")
    return 1