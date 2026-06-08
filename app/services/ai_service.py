import ollama
import json
import re
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, date

from app.db.models import Schedule, WorkerPerformance, ZoneConstraint
from app.db.models import InboundMezzanineWorks, InventoryQty, OutboundWork
from app.services.sync_service import get_shift_number

MODEL_JSON = "qwen2:0.5b"
THREADS = 4
CHUNK_SIZE = 10

async def generate_ai_assignments(db: AsyncSession, shift_id: str = None, target_date: date = None, locked_logins: list = None):
    if locked_logins is None:
        locked_logins = []
    
    now = datetime.now()
    if target_date is None:
        target_date = now.date()
        
    print(f"--- 🤖 AI ENGINE START (Shift ID: {shift_id}, Date: {target_date}) ---")

    # ==============================================================================
    # 1. POBRANIE ŻYWYCH DANYCH O WOLUMENACH
    # ==============================================================================
    inbound_qty = (await db.execute(select(func.sum(InboundMezzanineWorks.item_qty)))).scalar() or 0
    inv_row = (await db.execute(select(InventoryQty.available_physical).where(InventoryQty.id == 1))).scalar_one_or_none()
    putaway_qty = inv_row or 0
    outbound_qty = (await db.execute(select(func.sum(OutboundWork.work_qty)))).scalar() or 0

    print(f"📊 LIVE BACKLOG -> Inbound: {inbound_qty} | Putaway: {putaway_qty} | Outbound: {outbound_qty}")

    # ==============================================================================
    # 2. POBRANIE REGUŁ BIZNESOWYCH (LIMITÓW) NA DANY DZIEŃ I ZMIANĘ
    # ==============================================================================
    constraint_stmt = select(ZoneConstraint).where(ZoneConstraint.target_date == target_date)
    constraints_res = await db.execute(constraint_stmt)
    constraints = constraints_res.scalars().all()
    
    ZONE_TO_REACT_ID = {
        "Rozładunek": "receiving", "Przyjęcie": "receiving", "receiving": "receiving",
        "Putaway": "putaway", "putaway": "putaway",
        "Pick": "picking", "picking": "picking",
        "Pack": "packing", "packing": "packing",
        "Sort": "sorting", "sorting": "sorting"
    }

    # Słownik śledzący limity (min/max) dla każdej strefy
    zone_limits = {}
    for c in constraints:
        react_id = ZONE_TO_REACT_ID.get(c.zone_name)
        if react_id:
            # Pobieramy min/max dynamicznie w zależności od przekazanego shift_id (1, 2 lub 3)
            min_val = getattr(c, f"s{shift_id}_min", 0) or 0
            max_val = getattr(c, f"s{shift_id}_max", 999) or 999
            # Zabezpieczenie przed błędem z bazy
            max_val = max(min_val, max_val) 
            
            zone_limits[react_id] = {
                "min": min_val,
                "max": max_val,
                "current": 0 # to będzie zliczać Python
            }

    
    for default_zone in ["receiving", "putaway", "picking", "packing", "sorting"]:
        if default_zone not in zone_limits:
            zone_limits[default_zone] = {"min": 0, "max": 999, "current": 0}

    workload_context = (
        f"CURRENT BACKLOG:\n"
        f"- 'receiving': {int(inbound_qty)} items\n"
        f"- 'putaway': {int(putaway_qty)} items\n"
        f"- 'picking': {int(outbound_qty)} items\n\n"
        f"HARD CONSTRAINTS (You MUST NOT exceed MAX or go below MIN workers per zone!):\n"
        f"{json.dumps({z: {'min': v['min'], 'max': v['max']} for z, v in zone_limits.items()})}\n"
    )

    # ==============================================================================
    # 3. POBIERANIE PRACOWNIKÓW I SKILLI
    # ==============================================================================
    stmt = select(Schedule.login, Schedule.planned_shift, WorkerPerformance).outerjoin(
        WorkerPerformance, Schedule.login == WorkerPerformance.login
    ).where(Schedule.work_date == target_date)
    
    result = await db.execute(stmt)
    rows = result.all()

    team_data = []
    IGNORED_KEYS = ['id', 'login', 'worker_login', 'full_name', 'worker_name', 'updated_at', 'created_at', 'timestamp', 'date']

    for login, shift_name, perf in rows:
        if str(login) in locked_logins:
            continue
            
        if get_shift_number(str(shift_name).strip()) == str(shift_id):
            worker_skills = {}
            if perf:
                for col in perf.__table__.columns.keys():
                    if col.lower() not in IGNORED_KEYS:
                        val = getattr(perf, col, 0)
                        if isinstance(val, int) and val > 0:
                            mapped_skill = ZONE_TO_REACT_ID.get(col.lower(), col.lower())
                            worker_skills[mapped_skill] = val
            team_data.append({"id": str(login), "skills": worker_skills})

    if not team_data:
        print("⚠️ Brak dostępnych pracowników do przypisania.")
        return {}

    simplified_workers = {}
    for w in team_data:
        if not w["skills"]:
            simplified_workers[w["id"]] = ["picking"]
        else:
            sorted_skills = sorted(w["skills"].items(), key=lambda x: x[1], reverse=True)
            simplified_workers[w["id"]] = [skill_name for skill_name, val in sorted_skills]

    # ==============================================================================
    # 4. PĘTLA CHUNKOWANIA (LLM) - BAZOWY SZKIC
    # ==============================================================================
    ai_assignments = {}
    worker_items = list(simplified_workers.items())
    ai_allowed_zones = list(zone_limits.keys())

    for i in range(0, len(worker_items), CHUNK_SIZE):
        chunk = dict(worker_items[i:i + CHUNK_SIZE])
        
        prompt = (
            f"{workload_context}\n"
            f"WORKERS (First item is best skill): {json.dumps(chunk)}\n"
            f"ALLOWED ZONES: {json.dumps(ai_allowed_zones)}\n\n"
            f"TASK: Assign EXACTLY ONE zone to each worker. Return ONLY a flat JSON dictionary."
        )

        try:
            response = ollama.chat(
                model=MODEL_JSON,
                messages=[
                    {'role': 'system', 'content': 'Output ONLY a flat JSON dictionary mapping string IDs to string zone names.'},
                    {'role': 'user', 'content': prompt}
                ],
                format='json',
                options={"temperature": 0.1, "num_thread": THREADS}
            )
            
            raw_content = response['message']['content']
            ai_raw_dict = json.loads(raw_content)

            for w_id, suggested_zone in ai_raw_dict.items():
                if isinstance(suggested_zone, list) and len(suggested_zone) > 0:
                    suggested_zone = str(suggested_zone[0])
                matched_react_id = ZONE_TO_REACT_ID.get(str(suggested_zone).lower(), "picking")
                ai_assignments[w_id] = matched_react_id

        except Exception as e:
            print(f"❌ BŁĄD dla paczki {i}: {e}")
            for w_id in chunk.keys():
                ai_assignments[w_id] = simplified_workers[w_id][0] # Fallback na najlepszy skill

    # ==============================================================================
    # 5. PYTHON ENFORCER (STRAŻNIK LIMITÓW MIN / MAX)
    # ==============================================================================
    print("🛡️ Uruchamiam Python Enforcer (Korekta limitów Min/Max)...")
    
    # Obliczamy ile AI przypisało do poszczególnych stref
    for w_id, zone in ai_assignments.items():
        if zone in zone_limits:
            zone_limits[zone]["current"] += 1

    # Krok 5A: Redukcja przepełnień (Max constraint)
    for zone, limits in zone_limits.items():
        while limits["current"] > limits["max"]:
            # Szukamy pracownika w tej strefie o najniższym skilu, żeby go przerzucić
            candidates = [w for w, z in ai_assignments.items() if z == zone]
            if not candidates: break
            
            worker_to_move = candidates[0]
            # Przesuwamy go do pierwszej strefy, która ma jeszcze miejsce do limitu MAX
            target_zone = next((z for z, l in zone_limits.items() if l["current"] < l["max"]), "picking")
            
            ai_assignments[worker_to_move] = target_zone
            zone_limits[zone]["current"] -= 1
            if target_zone in zone_limits:
                zone_limits[target_zone]["current"] += 1

    # Krok 5B: Zaspokojenie niedoborów (Min constraint)
    for zone, limits in zone_limits.items():
        while limits["current"] < limits["min"]:
            # Brakuje nam ludzi w 'zone'. Szukamy kogoś w strefach, które są powyżej swojego MIN
            candidates = [w for w, z in ai_assignments.items() if z != zone and zone_limits[z]["current"] > zone_limits[z]["min"]]
            
            if not candidates:
                print(f"⚠️ Nie można spełnić limitu MIN dla strefy {zone} (za mało pracowników na zmianie!)")
                break
                
            worker_to_move = candidates[0]
            old_zone = ai_assignments[worker_to_move]
            
            # Re-przypisanie
            ai_assignments[worker_to_move] = zone
            zone_limits[old_zone]["current"] -= 1
            zone_limits[zone]["current"] += 1

    print("✅ Weryfikacja limitów zakończona sukcesem!")
    return ai_assignments