import asyncio
import sys
import selectors
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

if sys.platform == 'win32':
    selector = selectors.SelectSelector()
    loop = asyncio.SelectorEventLoop(selector)
    asyncio.set_event_loop(loop)
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from app.db.database import engine, Base, AsyncSessionLocal
from app.api.endpoints import router as api_router
import app.db.models 
from app.services.gate_sync import poll_gates_and_update  # Agent SSRS

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Inicjalizacja głównej bazy (Postgres)
    print("⏳ Uruchamianie serwera: Tworzenie tabel w bazie danych...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("✅ Baza danych gotowa!")

    # 2. Uruchomienie zadań w tle (Bramki)
    print("🚀 Uruchamianie zadań w tle (Bramki SSRS)...")
    async with AsyncSessionLocal() as session:
        gate_task = asyncio.create_task(poll_gates_and_update(session))
        
        # 3. Uruchomienie harmonogramu D365 (Automatycznie co 10 min)
        print("🕒 Uruchamianie zadań w tle (Harmonogram D365 co 10 min)...")
        async def d365_scheduler_loop():
            await asyncio.sleep(10)  # Bufor bezpieczeństwa na start serwera
            while True:
                try:
                    # Otwieramy osobną, krótką sesję bazy specjalnie dla bota automatycznego
                    async with AsyncSessionLocal() as d365_session:
                        from app.api.routers.sync import execute_d365_sync
                        print("🕒 [HARMONOGRAM] Rozpoczynam automatyczną synchronizację z D365...")
                        await execute_d365_sync(d365_session, triggered_by="Automatycznie")
                        print("🕒 [HARMONOGRAM] Automatyczna synchronizacja zakończona sukcesem.")
                except Exception as e:
                    print(f"❌ [HARMONOGRAM] Błąd pętli automatycznej D365: {e}")
                
                await asyncio.sleep(600)  # 10 minut = 600 sekund

        d365_task = asyncio.create_task(d365_scheduler_loop())
        
        yield 
        
        # 4. Procedura bezpiecznego wyłączania aplikacji
        print("🛑 Zamykanie zadań w tle...")
        gate_task.cancel()
        d365_task.cancel()


app = FastAPI(title="Flow Control API V2", lifespan=lifespan)

# Podpięcie głównych ścieżek
app.include_router(api_router, prefix="/api")

# Ustawienia CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"status": "online", "message": "Witaj w Flow Control V2!"}