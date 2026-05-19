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
THREADS = 4                # Limit obciążenia procesora


# ==============================================================================
# 1. GENEROWANIE PRZYDZIAŁÓW (ALGORYTM Z KLASTERINGIEM PROCESÓW I BLOKADAMI)
# ==============================================================================
async def generate_ai_assignments(db: AsyncSession, shift_id: str = None, target_date: date = None):
    now = datetime.now()
    if target_date is None:
        target_date = now.date()
        
    # --- BEZPIECZNIK: Lista zablokowanych loginów ---

    NOT_ALLOWED_LOGINS = []
        
    SKILL_TO_ZONE = {
        "receiving": "Rozładunek",
        "putaway": "Putaway",
        "picking": "Pick",
        "packing": "Pack",
        "sorting": "Sort",
        "forklift": "Rozładunek",
        "załadunki": "Załadunki",
        "shipping": "Załadunki"
    }
        
    # 1. Pobieramy limity i priorytety stref z bazy
    constraint_stmt = select(ZoneConstraint).order_by(ZoneConstraint.priority.asc())
    constraints_res = await db.execute(constraint_stmt)
    constraints = constraints_res.scalars().all()
    
    zones_status = {}
    for c in constraints:
        zones_status[c.zone_name] = {
            "priority": c.priority,
            "min": getattr(c, f"s{shift_id}_min", 0),
            "max": getattr(c, f"s{shift_id}_max", 0),
            "current_assigned": 0
        }

    # 2. Pobieramy pracowników
    stmt = select(Schedule.login, Schedule.planned_shift, WorkerPerformance).outerjoin(
        WorkerPerformance, Schedule.login == WorkerPerformance.login
    ).where(Schedule.work_date == target_date)
    
    result = await db.execute(stmt)
    rows = result.all()

    workers = []
    IGNORED_KEYS = ['id', 'login', 'worker_login', 'full_name', 'worker_name', 'updated_at', 'created_at', 'timestamp', 'date']

    for login, shift_name, perf in rows:
        # --- WERYFIKACJA BEZPIECZNIKA ---
        if str(login) in NOT_ALLOWED_LOGINS:
            continue # Pomijamy pracownika, algorytm go nie zobaczy!
            
        if get_shift_number(str(shift_name).strip()) == str(shift_id):
            skills = {}
            if perf:
                for col in perf.__table__.columns.keys():
                    if col.lower() not in IGNORED_KEYS:
                        val = getattr(perf, col, 0)
                        if isinstance(val, int) and val > 0:
                            zone_name = SKILL_TO_ZONE.get(col.lower(), col)
                            skills[zone_name] = val
            
            workers.append({"id": str(login), "raw_skills": skills})

    print(f"--- 🚀 CLUSTERED OPTIMIZER START (Shift: {shift_id}, Workers: {len(workers)}) ---")

    final_assignments = {}
    unassigned_workers = workers.copy()

    # --- DEFINICJA KLASTRÓW OPERACYJNYCH ---
    ZONE_ALLOWED_SKILLS = {
        "Rozładunek": ["Rozładunek", "Putaway"], 
        "Przyjęcie": ["Rozładunek", "Putaway"],  
        "Putaway": ["Rozładunek", "Putaway"],    
        
        "Pick": ["Pick", "Pack"],                
        "Pack": ["Pick", "Pack"],                
        
        "Sort": ["Sort"],                        
        "Załadunki": ["Załadunki"]               
    }

    # --- KROK 1: ZASPOKOJENIE MINIMÓW (Z UWZGLĘDNIENIEM KLASTRÓW) ---
    for zone_name, status in sorted(zones_status.items(), key=lambda x: x[1]["priority"]):
        allowed_skills_for_this_zone = ZONE_ALLOWED_SKILLS.get(zone_name, [zone_name])
        
        while status["current_assigned"] < status["min"]:
            best_worker = None
            best_skill_lvl = 0
            
            for w in unassigned_workers:
                matching_skills = [w["raw_skills"].get(s, 0) for s in allowed_skills_for_this_zone]
                skill_lvl = max(matching_skills) if matching_skills else 0
                
                if skill_lvl > best_skill_lvl:
                    best_skill_lvl = skill_lvl
                    best_worker = w
            
            if best_worker:
                final_assignments[best_worker["id"]] = zone_name
                status["current_assigned"] += 1
                unassigned_workers.remove(best_worker)
            else:
                if status["min"] > 0 and status["current_assigned"] < status["min"]:
                    print(f"⚠️ MANKAMENT: Nie można spełnić MIN dla strefy {zone_name}. Brak wolnych ludzi w dedykowanym klastrze!")
                break

    # --- KROK 2: ROZDZIELENIE RESZTY W RAMACH ICH NAJLEPSZYCH KLASTRÓW ---
    for w in list(unassigned_workers):
        sorted_skills = sorted(w["raw_skills"].items(), key=lambda x: x[1], reverse=True)
        assigned = False
        
        for preferred_zone, skill_lvl in sorted_skills:
            if preferred_zone in zones_status:
                status = zones_status[preferred_zone]
                allowed_skills = ZONE_ALLOWED_SKILLS.get(preferred_zone, [preferred_zone])
                has_valid_cluster_skill = any(w["raw_skills"].get(s, 0) > 0 for s in allowed_skills)
                
                if has_valid_cluster_skill and status["current_assigned"] < status["max"]:
                    final_assignments[w["id"]] = preferred_zone
                    status["current_assigned"] += 1
                    unassigned_workers.remove(w)
                    assigned = True
                    break
        
        # --- KROK 3: REZERWOWY FALLBACK ---
        if not assigned:
            final_assignments[w["id"]] = "Pick"
            if "Pick" in zones_status:
                zones_status["Pick"]["current_assigned"] += 1

    print(f"✅ OPTIMIZER: Przydzielono {len(final_assignments)} osób.")
    for z, s in zones_status.items():
        print(f"📊 {z}: {s['current_assigned']} osób (Min: {s['min']}, Max: {s['max']})")

    # --- KROK 4: SŁOWNIK TŁUMACZĄCY NA IDENTYFIKATORY DLA REACTA ---
    ZONE_TO_REACT_ID = {
        "Rozładunek": "receiving",
        "Przyjęcie": "receiving",
        "Załadunki": "shipping",
        "Putaway": "putaway",
        "Pick": "picking",
        "Pack": "packing",
        "Sort": "sorting"
    }

    react_assignments = {}
    for worker_id, db_zone_name in final_assignments.items():
        react_id = ZONE_TO_REACT_ID.get(db_zone_name)
        if react_id:
            react_assignments[worker_id] = react_id
            
    return react_assignments


# async def generate_ai_assignments(db: AsyncSession, shift_id: str = None, target_date: date = None):
#     now = datetime.now()
    
#     if target_date is None:
#         target_date = now.date()
        
#     # 1. Pobieramy limity i priorytety stref
#     constraint_stmt = select(ZoneConstraint).order_by(ZoneConstraint.priority.asc())
#     constraints_res = await db.execute(constraint_stmt)
#     constraints = constraints_res.scalars().all()
    
#     zones_config = [
#         {
#             "zone": c.zone_name,
#             "priority": c.priority,
#             "min": getattr(c, f"s{shift_id}_min", 0),
#             "max": getattr(c, f"s{shift_id}_max", 0)
#         } for c in constraints
#     ]

#     # 2. Pobieramy pracowników zaplanowanych na dany dzień i ich płaską matrycę skilli
#     stmt = select(Schedule.login, Schedule.planned_shift, WorkerPerformance).outerjoin(
#         WorkerPerformance, Schedule.login == WorkerPerformance.login
#     ).where(Schedule.work_date == target_date)
    
#     result = await db.execute(stmt)
#     rows = result.all()

#     team_data = []
#     print(f"--- 🤖 AI ENGINE START (Shift ID: {shift_id}, Date: {target_date}) ---")
    
#     # Ignorowane kolumny techniczne przy wyciąganiu skilli
#     IGNORED_KEYS = ['id', 'login', 'worker_login', 'full_name', 'worker_name', 'updated_at', 'created_at', 'timestamp', 'date']

#     for login, shift_name, perf in rows:
#         db_shift_str = str(shift_name).strip()
#         detected_shift = get_shift_number(db_shift_str)
        
#         if detected_shift == str(shift_id):
#             # DYNAMICZNE POBIERANIE SKILLI (Pancerne rozwiązanie)
#             worker_skills = {}
#             if perf:
#                 # Skanuje wszystkie kolumny w tabeli WorkerPerformance
#                 for col in perf.__table__.columns.keys():
#                     if col.lower() not in IGNORED_KEYS:
#                         val = getattr(perf, col, 0)
#                         # Bierzemy tylko cyfry (poziomy skilli)
#                         if isinstance(val, int) and val > 0:
#                             worker_skills[col] = val
            
#             team_data.append({
#                 "id": str(login),
#                 "skills": worker_skills
#             })

#     print(f"--- 🔍 AI DEBUG: Znaleziono: {len(team_data)} osób dla zmiany {shift_id}")

#     if not team_data:
#         return {}

#     # ==============================================================================
#     # --- MIEJSCE NA PRZYSZŁĄ LOGIKĘ (FORECAST & BACKLOG) ---
#     # : dla przyszlosci aby zmienic logike i dodac elementy te ponizej
#     # current_workload = await get_workpool_analytics(db)
#     # upcoming_forecast = await get_upcoming_forecast(db)
#     # ==============================================================================

#     # 3. Konstruujemy Prompt dla Ollama (Skupiony w 100% na najwyższych skillach)
#     simplified_workers = {}
#     for w in team_data:
#         if not w["skills"]:
#             # Brak skilli -> rzucamy domyślnie na picking
#             simplified_workers[w["id"]] = ["picking"]
#         else:
#             # Sortujemy skille pracownika malejąco (najwyższa ocena na pierwszym miejscu)
#             sorted_skills = sorted(w["skills"].items(), key=lambda x: x[1], reverse=True)
#             # Zostawiamy same nazwy procesów (np. ["picking", "packing", "putaway"])
#             simplified_workers[w["id"]] = [skill_name for skill_name, val in sorted_skills]

#     valid_zones = [z["zone"] for z in zones_config]
    
#     prompt = (
#         f"Assign EXACTLY ONE zone to each worker.\n"
#         f"WORKERS PREFERENCES (First item is their best skill): {json.dumps(simplified_workers)}\n"
#         f"ALLOWED ZONES: {json.dumps(valid_zones)}\n\n"
#         f"TASK: Return a flat JSON dictionary. Key = worker ID, Value = assigned zone name (string).\n"
#         f"Do NOT return lists. Pick the best possible zone for each worker.\n"
#         f"EXAMPLE OUTPUT:\n{{\"3002448\": \"picking\", \"3002491\": \"putaway\", \"9001504\": \"packing\"}}"
#     )

#     try:
#         response = ollama.chat(
#             model=MODEL_JSON,
#             messages=[
#                 {
#                     'role': 'system', 
#                     'content': 'You are a JSON formatter. You must ONLY output a flat dictionary mapping string IDs to string zone names. Never output nested objects or lists.'
#                 },
#                 {
#                     'role': 'user', 
#                     'content': prompt
#                 }
#             ],
#             format='json',
#             options={"temperature": 0.0, "num_thread": THREADS}
#         )
        
#         raw_content = response['message']['content']
#         print(f"👀 [RAW AI OUTPUT] Surowa odpowiedź modelu:\n{raw_content}\n--------------------")
        
#         ai_raw_dict = json.loads(raw_content)

#         # 4. Siatka bezpieczeństwa - upewniamy się, że każdy dostał zadanie
#         final_assignments = {}
#         valid_zones = [c.zone_name for c in constraints]
        
#         for worker in team_data:
#             w_id = worker["id"]
#             suggested = ai_raw_dict.get(w_id)
            
#             if suggested in valid_zones:
#                 final_assignments[w_id] = suggested
#             else:
#                 # Jeśli AI się pomyli lub brakuje skilli, bezpieczny fallback (np. picking)
#                 final_assignments[w_id] = "picking"

#         print(f"✅ AI: Przydzielono {len(final_assignments)} pracowników (Baza na najlepszych skillach).")
#         return final_assignments

#     except Exception as e:
#         print(f"❌ BŁĄD SILNIKA AI: {e}")
#         return {w["id"]: "picking" for w in team_data}


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
    

    