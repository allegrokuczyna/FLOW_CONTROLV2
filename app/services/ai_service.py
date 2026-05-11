import ollama
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import Schedule, WorkerPerformance
from app.services.sync_service import get_workpool_analytics, is_worker_on_shift
from datetime import datetime, time

async def get_ai_warehouse_advice(db: AsyncSession):
    now = datetime.now()
    workpool_stats = await get_workpool_analytics(db)
    
    worker_query = select(WorkerPerformance, Schedule.planned_shift).join(
        Schedule, WorkerPerformance.login == Schedule.login
    ).where(Schedule.work_date == now.date(), Schedule.group_prefix == 'O')
    
    result = await db.execute(worker_query)
    all_workers = result.all()

 
    team_data = []
    for worker, shift in all_workers:
        if is_worker_on_shift(shift, now.time()):

            p = int(worker.picking*100)
            pa = int(worker.packing*100)
            f = int(worker.forklift*100)
            s = int(worker.sorting*100)
            
            if p+pa+f+s == 0:
                team_data.append(f"{worker.login}:NOWY")
            else:
                team_data.append(f"{worker.login}:PI{p}%,PA{pa}%,FO{f}%,SO{s}%")

    team_str = "\n".join(team_data)

   
    prompt = f"""
    SYSTEM: Jesteś logistykiem ADM-01.
    ZADANIA: {workpool_stats}
    PRACOWNICY (Login:Skille):
    {team_str}

    INSTRUKCJA:
    1. Przypisz KAŻDEGO z powyższych {len(team_data)} pracowników do: PICKING, PACKING, FORKLIFT lub SORTING.
    2. Odpowiedz TYLKO I WYŁĄCZNIE tabelą Markdown.
    3. NIE używaj wielokropka (...). Wypisz WSZYSTKIE {len(team_data)} wierszy.
    4. Kolumny: | Login | Proces | Uzasadnienie |
    5. Jeśli ktoś ma 0% (NOWY), proces = PICKING.
    6. Język: Polski.

    TABELA:
    """

    try:
        response = ollama.chat(
            model='llama3', 
            messages=[{'role': 'user', 'content': prompt}],
            options={
                "num_predict": 8192,  # Maksymalna długość
                "temperature": 0.1,   # Maksymalna precyzja, zero kreatywności
                "top_p": 0.9
            }
        )
        return {
            "time": now.strftime("%H:%M"),
            "workers_count": len(team_data),
            "ai_analysis": response['message']['content']
        }
    except Exception as e:
        return {"error": str(e)}