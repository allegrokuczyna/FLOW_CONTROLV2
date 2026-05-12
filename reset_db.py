import asyncio
import sys
from app.db.database import engine, Base
from app.db.models import User, Schedule, WorkerPerformance, WorkExport # Importuj wszystkie modele


if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

async def reset_database():
    async with engine.begin() as conn:
     
        all_tables = Base.metadata.tables
        tables_to_drop = [
            table for name, table in all_tables.items() 
            if name != "users"
        ]
        
        if tables_to_drop:
            print(f"🗑️ Usuwam tabele: {[t.name for t in tables_to_drop]}...")
            # Musimy użyć run_sync, ponieważ metadata.drop_all nie jest asynchroniczne
            await conn.run_sync(Base.metadata.drop_all, tables=tables_to_drop)
        
        print("✨ Tworzę brakujące tabele (oprócz 'users', jeśli już istnieje)...")
        # create_all domyślnie nie dotknie tabeli, która już istnieje
        await conn.run_sync(Base.metadata.create_all)
        
    print("✅ Baza zresetowana. Twoje konto użytkownika pozostało nienaruszone!")

if __name__ == "__main__":
    asyncio.run(reset_database())