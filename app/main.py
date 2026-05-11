import asyncio
import sys
import selectors


if sys.platform == 'win32':
    selector = selectors.SelectSelector()
    loop = asyncio.SelectorEventLoop(selector)
    asyncio.set_event_loop(loop)
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.db.database import engine, Base
from app.api.endpoints import router as api_router
import app.db.models 

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("⏳ Uruchamianie serwera: Tworzenie tabel w bazie danych...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("✅ Baza danych gotowa!")
    yield

# Inicjalizacja instancji FastAPI
app = FastAPI(title="Flow Control API V2", lifespan=lifespan)

# router z endpointami
app.include_router(api_router)

@app.get("/")
def read_root():
    return {"status": "online", "message": "Witaj w Flow Control V2!"}