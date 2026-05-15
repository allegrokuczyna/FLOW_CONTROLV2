import ollama
import json
import re
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import Schedule, WorkerPerformance, AiReportLog, ZoneConstraint
from app.services.sync_service import get_workpool_analytics, is_worker_on_shift, get_shift_number
from datetime import datetime, date

# --- KONFIGURACJA ---
MODEL_JSON = "qwen2:0.5b"  # Szybki model do struktury JSON
MODEL_TEXT = "phi3"        # Model do generowania raportów (inteligentniejszy)
THREADS = 2                # Limit obciążenia procesora

# ==============================================================================
# 1. GENEROWANIE PRZYDZIAŁÓW (JSON DLA DRAG & DROP)
# ==============================================================================
async def generate_ai_assignments(db: AsyncSession, shift_id: str = None, target_date: date = None):
    now = datetime.now()
    
    # Jeśli React nie przyśle daty, domyślnie bierzemy dzisiejszą
    if target_date is None:
        target_date = now.date()
        
    workload = await get_workpool_analytics(db)
    
    # 1. Pobieramy limity i priorytety
    constraint_stmt = select(ZoneConstraint).order_by(ZoneConstraint.priority.asc())
    constraints_res = await db.execute(constraint_stmt)
    constraints = constraints_res.scalars().all()
    
    zones_config = [
        {
            "zone": c.zone_name,
            "priority": c.priority,
            "min": getattr(c, f"s{shift_id}_min", 0),
            "max": getattr(c, f"s{shift_id}_max", 0)
        } for c in constraints
    ]

    # 2. Pobieramy pracowników (KLUCZOWA ZMIANA: szukamy po target_date!)
    stmt = select(Schedule.login, Schedule.planned_shift, WorkerPerformance).outerjoin(
        WorkerPerformance, Schedule.login == WorkerPerformance.login
    ).where(Schedule.work_date == target_date)
    
    result = await db.execute(stmt)
    rows = result.all()

    team_data = []
    print(f"--- 🤖 AI ENGINE START (Shift ID: {shift_id}, Date: {target_date}) ---")
    
    for login, shift_name, perf in rows:
        db_shift_str = str(shift_name).strip()
        
        # Używamy tej samej funkcji co w widoku!
        detected_shift = get_shift_number(db_shift_str)
        
        if detected_shift == str(shift_id):
            team_data.append({
                "id": str(login),
                "skills": {
                    "receiving": perf.receiving if perf else 0,
                    "putaway": perf.putaway if perf else 0,
                    "picking": perf.picking if perf else 0,
                    "packing": perf.packing if perf else 0,
                    "sorting": perf.sorting if perf else 0
                }
            })

    # DEBUG po zmianie
    print(f"--- 🔍 AI DEBUG: Po ujednoliceniu logiki znaleziono: {len(team_data)} osób")

    if not team_data:
        return {}

    # 3. Konstruujemy Prompt dla Ollama
    prompt = (
        f"You are a WMS Optimizer. Assign {len(team_data)} workers to zones. "
        f"Workers & Skills (0-6): {json.dumps(team_data)}. "
        f"Zone Constraints (Priority, Min, Max): {json.dumps(zones_config)}. "
        f"Current Workload: {json.dumps(workload)}. "
        f"RULES: 1. Priority 1 zones must be filled first. 2. Respect MIN/MAX staff per zone. "
        f"3. Assign best skilled workers to priorities. "
        f"Output ONLY a JSON object: {{\"worker_id\": \"zone_name\"}}."
    )

    try:
        response = ollama.chat(
            model=MODEL_JSON,
            messages=[{'role': 'user', 'content': prompt}],
            format='json',
            options={"temperature": 0.1, "num_thread": THREADS}
        )
        
        raw_content = response['message']['content']
        ai_raw_dict = json.loads(raw_content)

        # 4. Siatka bezpieczeństwa - upewniamy się, że każdy dostał zadanie
        final_assignments = {}
        valid_zones = [c.zone_name for c in constraints]
        
        for worker in team_data:
            w_id = worker["id"]
            suggested = ai_raw_dict.get(w_id)
            
            if suggested in valid_zones:
                final_assignments[w_id] = suggested
            else:
                # Jeśli AI kogoś pominęło, trafia do picking (bezpieczna przystań)
                final_assignments[w_id] = "picking"

        print(f"✅ AI: Przydzielono {len(final_assignments)} pracowników.")
        return final_assignments

    except Exception as e:
        print(f"❌ BŁĄD SILNIKA AI: {e}")
        # Fail-safe: przypisz wszystkich do picking
        return {w["id"]: "picking" for w in team_data}


# ==============================================================================
# 2. GENEROWANIE RAPORTU STRATEGICZNEGO (MARKDOWN)
# ==============================================================================
async def get_ai_warehouse_advice(db: AsyncSession, username: str = "System"):
    """Tworzy krótki, konkretny raport sytuacyjny i zapisuje go w logach."""
    now = datetime.now()
    workpool_stats = await get_workpool_analytics(db)
    
    # Pobieramy liczbę aktywnych pracowników na teraz
    worker_query = select(Schedule.planned_shift).where(Schedule.work_date == now.date())
    result = await db.execute(worker_query)
    all_shifts = result.scalars().all()
    active_count = sum(1 for s in all_shifts if is_worker_on_shift(s, now.time()))

    prompt = f"""
    Context: Workload {json.dumps(workpool_stats)}, Active Workers: {active_count}.
    Task: Write a 3-sentence operational report in POLISH.
    Rule: Identify bottlenecks and give 1 direct command. 
    Add a very short warehouse-related joke at the end.
    Format: Markdown. Zero intro, zero outro.
    """

    try:
        response = ollama.chat(
            model=MODEL_TEXT, 
            messages=[{'role': 'user', 'content': prompt}],
            options={"temperature": 0.4, "num_thread": THREADS}
        )
        
        ai_text = response['message']['content']

        # Zapis do historii raportów
        new_log = AiReportLog(
            username=username,
            workers_count=active_count,
            report_text=ai_text,
            created_at=now
        )
        db.add(new_log)
        await db.commit()

        return {
            "time": now.strftime("%H:%M"),
            "workers_count": active_count,
            "ai_analysis": ai_text
        }
    except Exception as e:
        print(f"❌ BŁĄD RAPORTU AI: {e}")
        return {"error": "AI currently unavailable"}