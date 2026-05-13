import ollama
import json
import re
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import Schedule, WorkerPerformance, AiReportLog
from app.services.sync_service import get_workpool_analytics, is_worker_on_shift
from datetime import datetime

# --- KONFIGURACJA ---
MODEL_JSON = "qwen2:0.5b"  # Szybki model do JSON
MODEL_TEXT = "phi3"        # Inteligentniejszy model do raportów
THREADS = 2                # Limit obciążenia procesora

# ==============================================================================
# 1. FUNKCJA DO GRAFIKU DRAG & DROP (ZWRACA JSON)
# ==============================================================================
async def generate_ai_assignments(db: AsyncSession, shift_id: str = None):
    """Generowanie planu z wymuszeniem 100% obsadzenia pracowników, używając skilli 0-6."""
    now = datetime.now()
    workload = await get_workpool_analytics(db)
    
    stmt = select(Schedule.login, Schedule.planned_shift, WorkerPerformance).outerjoin(
        WorkerPerformance, Schedule.login == WorkerPerformance.login
    ).where(Schedule.work_date == now.date())
    
    result = await db.execute(stmt)
    rows = result.all()

    team_data = []
    print(f"--- 🔍 DEBUG START (Szukamy zmiany: {shift_id}) ---")
    
    for login, shift_name, perf in rows:
        db_shift = str(shift_name).strip()
        is_match = False
        
        # Logika mapowania (Dostosowana do logów: '06-16', '14-22', '22-06')
        if shift_id == '1' and ('06-' in db_shift or '05-' in db_shift):
            is_match = True
        elif shift_id == '2' and ('14-' in db_shift or '13-' in db_shift):
            is_match = True
        elif shift_id == '3' and ('22-' in db_shift or '21-' in db_shift):
            is_match = True
        elif shift_id == 'all' or not shift_id:
            if is_worker_on_shift(shift_name, now.time()):
                is_match = True

        if is_match:
            # POBIERAMY SKILL (0-6)
            picking_skill = int(perf.picking) if perf and perf.picking else 0
            team_data.append({"id": login, "lvl": picking_skill})

    print(f"--- 🔍 DEBUG: Znaleziono pracowników spełniających kryteria: {len(team_data)}")

    if not team_data:
        print("⚠️ UWAGA: team_data jest pusta. AI nie ma kogo przydzielić.")
        return []

    # ZAKTUALIZOWANY PROMPT (SYSTEM SKILLI 0-6)
    prompt = (
        f"You MUST assign EXACTLY {len(team_data)} workers. DO NOT skip anyone! "
        f"Workers to assign: {json.dumps(team_data)}. "
        f"Workload context: {json.dumps(workload)}. "
        f"IMPORTANT RULE: 'lvl' means Skill Level (0 is beginner, 5/6 is expert). "
        f"Assign highly skilled workers (lvl 4-6) to demanding tasks. Assign beginners (lvl 0-1) mostly to 'picking'. "
        f"Output ONLY a JSON list of exactly {len(team_data)} objects: [{{'workerId': 'login', 'suggestedZone': 'picking', 'reason': 'text'}}] "
        f"Zones to use: picking, packing, inbound, sorting, putaway."
    )

    try:
        print(f"🤖 Wysyłam zapytanie do Ollama (oczekiwana liczba: {len(team_data)})...")
        response = ollama.chat(
            model=MODEL_JSON,
            messages=[{'role': 'user', 'content': prompt}],
            format='json',
            options={
                "temperature": 0.1, 
                "num_thread": THREADS,
                "num_predict": 8192
            }
        )
        
        raw_content = response['message']['content']
        data = json.loads(raw_content)

        # Wyciąganie listy
        temp_list = []
        if isinstance(data, list):
            temp_list = data
        elif isinstance(data, dict):
            for val in data.values():
                if isinstance(val, list):
                    temp_list = val
                    break
            if not temp_list: 
                temp_list = [data]

        final_list = []
        valid_zones = ['picking', 'packing', 'inbound', 'sorting', 'putaway']
        assigned_ids = set() 

        for entry in temp_list:
            if not isinstance(entry, dict): continue
            
            w_id = str(entry.get("workerId") or entry.get("id") or entry.get("login") or "")
            zone = str(entry.get("suggestedZone") or entry.get("zone") or "picking").lower().strip()
            
            if zone not in valid_zones or zone == "zone":
                zone = "picking"

            if w_id and w_id not in assigned_ids:
                final_list.append({
                    "workerId": w_id,
                    "login": w_id, 
                    "suggestedZone": zone,
                    "reason": str(entry.get("reason") or "Optymalizacja AI")
                })
                assigned_ids.add(w_id)
        
        # SIATKA BEZPIECZEŃSTWA (Ręczne dopisanie zgubionych przez AI)
        missing_workers = [w['id'] for w in team_data if w['id'] not in assigned_ids]
        
        if missing_workers:
            print(f"⚠️ AI zgubiło {len(missing_workers)} pracowników. Uruchamiam siatkę bezpieczeństwa...")
            for m_id in missing_workers:
                final_list.append({
                    "workerId": m_id,
                    "login": m_id,
                    "suggestedZone": "picking", 
                    "reason": "Automatyczne uzupełnienie systemu"
                })

        print(f"✅ Sukces: Zwracam {len(final_list)} propozycji (Oczekiwano: {len(team_data)}).")
        return final_list

    except Exception as e:
        print(f"❌ KRYTYCZNY BŁĄD AI: {e}")
        return []

# ==============================================================================
# 2. FUNKCJA DO GENEROWANIA RAPORTU (ZWRACA TABELĘ MARKDOWN)
# ==============================================================================
async def get_ai_warehouse_advice(db: AsyncSession, username: str = "System"):
    """Generuje strategiczny raport menedżerski i zapisuje go w bazie."""
    now = datetime.now()
    workpool_stats = await get_workpool_analytics(db)
    
    # Pobieramy grafiki na dziś
    worker_query = select(Schedule.planned_shift).where(Schedule.work_date == now.date())
    result = await db.execute(worker_query)
    all_shifts = result.scalars().all()

    # Liczymy dostępnych pracowników
    active_workers_count = sum(1 for shift in all_shifts if is_worker_on_shift(shift, now.time()))

    prompt = f"""
    Jesteś głównym doradcą logistycznym (AI Manager).
    Obciążenie: {json.dumps(workpool_stats)}
    Dostępnych pracowników: {active_workers_count}
    
    Napisz krótki raport dla kierownika zmiany (maksymalnie 3 zdania).
    Wskaż, gdzie jest najwięcej pracy ("wąskie gardła") i doradź, jak zorganizować zespół.
    ZASADY: ZERO wstępów, ZERO podsumowań. Od razu konkrety. Używaj formatowania Markdown.
    """

    try:
        response = ollama.chat(
            model=MODEL_TEXT, 
            messages=[{'role': 'user', 'content': prompt}],
            options={
                "temperature": 0.2, 
                "num_thread": THREADS,
                "num_predict": 500
            }
        )
        
        ai_text = response['message']['content']

        # --- NOWOŚĆ: Zapis do bazy danych ---
        new_log = AiReportLog(
            username=username,
            workers_count=active_workers_count,
            report_text=ai_text,
            created_at=now
        )
        db.add(new_log)
        await db.commit()
        # ------------------------------------

        return {
            "time": now.strftime("%H:%M"),
            "workers_count": active_workers_count,
            "generated_by": username,
            "ai_analysis": ai_text
        }
    except Exception as e:
        print(f"❌ Błąd AI (Advice): {e}")
        return {"error": str(e)}
    
