import asyncio
from app.db.database import engine, Base
from app.db.models import WorkExport

async def reset_database():
    async with engine.begin() as conn:
        print("🗑️ Usuwam stare tabele...")
        await conn.run_sync(Base.metadata.drop_all)
        print("✨ Tworzę tabele z nowymi kolumnami...")
        await conn.run_sync(Base.metadata.create_all)
    print("✅ Baza gotowa na świeże dane!")

if __name__ == "__main__":
    asyncio.run(reset_database())