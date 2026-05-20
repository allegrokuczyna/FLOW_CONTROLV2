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
from app.services.gate_sync import poll_gates_and_update # <-- Agent SSRS (pobieranie z raportu)

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
        
        yield 
        
        print("🛑 Zamykanie zadań w tle...")
        gate_task.cancel()


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