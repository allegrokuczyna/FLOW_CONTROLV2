import httpx
import pandas as pd
from io import StringIO
from datetime import date, timedelta, datetime, time
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, select, delete
from sqlalchemy.dialects.postgresql import insert  # Wyłącznie Postgres
from app.core.auth import get_d365_access_token
from app.core.config import settings
from app.db.models import WorkExport, WorkerPerformance, Schedule, ActiveWork, ShiftAssignment, ForecastIntake

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

def get_shift_number(hours_str: str) -> str:
    """Mapuje formaty godzin na numery zmian 1, 2, 3."""
    if not hours_str: return "0"
    h = str(hours_str).lower().replace(" ", "").strip()
    if any(x in h for x in ["06-14", "6-14", "08-16", "06-16"]): return "1"
    if any(x in h for x in ["14-22", "12-22"]): return "2"
    if any(x in h for x in ["22-06", "22-6"]): return "3"
    return "0"

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
    """
    Odbiera dane wypchnięte z Google Apps Script (Matryca, Grafik, Forecast).
    Omija błędy 401, bo to Google pcha dane do nas.
    """
    report = {}
    today = date.today()
    target_dates = [today, today + timedelta(days=1)]

    # --- 2.1 MATRYCA SKILLI ---
    try:
        raw_m = payload.get("matryca", [])
        if raw_m and len(raw_m) > 1:
            # 🔍 Szukamy wiersza z nagłówkami (szukamy 'login' w pierwszych 10 wierszach)
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
        else:
            report["matrix"] = "No data"
    except Exception as e:
        report["matrix"] = f"Error: {str(e)}"

    # --- 2.2 GRAFIK PRACY ---
    try:
        raw_g = payload.get("grafik", [])
        if raw_g and len(raw_g) > 1:
            # 🔍 Szukamy wiersza z nagłówkami
            header_idx = 0
            for i, row in enumerate(raw_g[:10]):
                row_str = [str(cell).lower() for cell in row]
                if any("numer" in cell or "status" in cell for cell in row_str):
                    header_idx = i
                    break
            
            headers = [str(c).strip() for c in raw_g[header_idx]]
            data = raw_g[header_idx + 1:]
            df_g = pd.DataFrame(data, columns=headers)
            
            # Filtrowanie statusu
            if 'Status' in df_g.columns:
                df_g = df_g[df_g['Status'].astype(str).str.lower().str.contains('pracuje', na=False)]
            
            count_g = 0
            for _, row in df_g.iterrows():
                login = str(row.get('Numer Pracownika', '')).strip()
                if not login or login == 'nan': continue
                
                for col in df_g.columns:
                    work_date = flexible_date_parser(col)
                    if work_date in target_dates:
                        shift = str(row.get(col, '')).strip()
                        if shift and shift.lower() not in ['nan', '']:
                            stmt = insert(Schedule).values(
                                login=login, work_date=work_date, planned_shift=shift
                            ).on_conflict_do_update(
                                index_elements=['login', 'work_date'],
                                set_={"planned_shift": shift}
                            )
                            await db.execute(stmt)
                            count_g += 1
            report["schedule"] = f"Success ({count_g} shifts)"
        else:
            report["schedule"] = "No data"
    except Exception as e:
        report["schedule"] = f"Error: {str(e)}"

    # --- 2.3 FORECAST (INTAKE) ---
    try:
        raw_f = payload.get("forecast", [])
        if raw_f:
            # 1. Usuwamy z bazy stare wpisy, ale TYLKO dla tych dni, które aktualizujemy
            await db.execute(delete(ForecastIntake).where(ForecastIntake.forecast_date.in_(target_dates)))
            
            new_forecasts = []
            for item in raw_f:
                # Parsujemy datę przysłaną z Apps Script
                dt_obj = datetime.fromisoformat(item['dt'].replace('Z', '+00:00'))
                
                # 2. FILTR: Bierzemy tylko rekordy, które pasują do dzisiaj (i ew. jutra)
                if dt_obj.date() in target_dates:
                    new_forecasts.append(ForecastIntake(
                        forecast_date=dt_obj.date(),      
                        hour_from=dt_obj,                 
                        forecast_pcs=int(item['pcs'])     
                    ))
            
            if new_forecasts:
                db.add_all(new_forecasts)
                
            report["forecast"] = f"Success ({len(new_forecasts)} lines for target dates)"
        else:
            report["forecast"] = "No data"
    except Exception as e:
        report["forecast"] = f"Error: {str(e)}"

    await db.commit()
    return report

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
    """Live Sync prac Open/InProcess."""
    filter_query = "WarehouseId eq 'ADM-01' and (WarehouseWorkStatus eq Microsoft.Dynamics.DataEntities.WHSWorkStatus'Open' or WarehouseWorkStatus eq Microsoft.Dynamics.DataEntities.WHSWorkStatus'InProcess')"
    endpoint = f"WarehouseWorkHeaders?cross-company=true&$filter={filter_query}"
    works_data = await get_data(endpoint)
    if not works_data: return

    for w in works_data:
        stmt = insert(ActiveWork).values(
            workid=w.get("WarehouseWorkId"),
            ordernum=w.get("SourceOrderNumber"),
            workpoolid=w.get("WarehouseWorkPoolId"),
            workstatus=str(w.get("WarehouseWorkStatus")),
            whasalesitemqty=float(w.get("WHASalesItemQty") or 0),
            whaadditionalzone2=w.get("WHAAdditionalZone2"),
            workpriority=int(w.get("WorkPriority") or 0)
        ).on_conflict_do_update(
            index_elements=['workid'],
            set_={
                "workstatus": str(w.get("WarehouseWorkStatus")),
                "whasalesitemqty": float(w.get("WHASalesItemQty") or 0),
                "whaadditionalzone2": w.get("WHAAdditionalZone2")
            }
        )
        await db.execute(stmt)
    await db.commit()

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

async def get_daily_plan(db: AsyncSession, target_date: date = None):
    """Zwraca plan przydziałów na dany dzień, wzbogacony o matrycę skilli."""
    if target_date is None: 
        target_date = date.today()
        
    sched_stmt = select(Schedule).where(Schedule.work_date == target_date)
    sched_res = await db.execute(sched_stmt)
    schedules = sched_res.scalars().all()
    
    assign_stmt = select(ShiftAssignment).where(ShiftAssignment.assignment_date == target_date)
    assign_res = await db.execute(assign_stmt)
    assignments = {a.worker_login: a.task for a in assign_res.scalars().all()}

    perf_stmt = select(WorkerPerformance)
    perf_res = await db.execute(perf_stmt)
    performances = {p.login: p for p in perf_res.scalars().all()}

    plan_data = []
    for s in schedules:
        hours = str(s.planned_shift).strip()
        if not hours or hours.lower() in ['nan', 'urlop', 'zw', 'none']: 
            continue
            
        p = performances.get(s.login)
        
        plan_data.append({
            "login": str(s.login),               # <--- TEN KLUCZ ZWRÓCI LOGINY NA EKRAN!
            "worker_login": str(s.login),        # Zostawiamy dla pewności
            "name": str(s.login),                # Czasem frontendy UI szukają klucza 'name'
            "shift": get_shift_number(hours),
            "hours": hours,
            "task": assignments.get(s.login, 'unassigned'),
            "picking": getattr(p, 'picking', 0) if p else 0,
            "packing": getattr(p, 'packing', 0) if p else 0,
            "putaway": getattr(p, 'putaway', 0) if p else 0,
            "receiving": getattr(p, 'receiving', 0) if p else 0,
            "sorting": getattr(p, 'sorting', 0) if p else 0,
            "forklift": getattr(p, 'forklift', 0) if p else 0,
            "returns": getattr(p, 'returns', 0) if p else 0,
        })
        
    return plan_data

async def save_daily_plan(assignments: list, db: AsyncSession, target_date: date = None):
    """Zapisuje ręczne przydziały do stref."""
    if target_date is None: target_date = date.today()
    for item in assignments:
        stmt = insert(ShiftAssignment).values(
            worker_login=item['worker_login'], shift=item['shift'],
            task=item['task'], assignment_date=target_date
        ).on_conflict_do_update(
            index_elements=['worker_login', 'assignment_date'],
            set_={"task": item['task'], "shift": item['shift']}
        )
        await db.execute(stmt)
    await db.commit()
    return {"status": "success"}

# ==============================================================================
# --- DODATKOWE FUNKCJE POMOCNICZE (DLA AI) ---
# ==============================================================================

async def is_worker_on_shift(login: str, shift_id: str, db: AsyncSession, target_date: date = None) -> bool:
    """
    Sprawdza, czy dany pracownik ma zaplanowaną konkretną zmianę danego dnia.
    Wykorzystywane głównie przez AI do filtrowania dostępnych rąk do pracy.
    """
    if target_date is None: 
        target_date = date.today()
        
    stmt = select(Schedule).where(Schedule.login == login, Schedule.work_date == target_date)
    result = await db.execute(stmt)
    sched = result.scalar_one_or_none()
    
    if not sched:
        return False
        
    # Pobieramy godziny z grafiku (np. "06-14") i zmieniamy na numer zmiany (1, 2 lub 3)
    actual_shift = get_shift_number(str(sched.planned_shift))
    
    # Zwraca True, jeśli numer zmiany w grafiku zgadza się z tą, o którą pyta AI
    return actual_shift == str(shift_id)