import asyncio
import sys
import bcrypt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import sessionmaker

# Importy z Twojej struktury
from app.db.database import engine
from app.db.models import User

async def create_admin():
    async_session_local = sessionmaker(
        bind=engine, 
        class_=AsyncSession, 
        expire_on_commit=False
    )

    async with async_session_local() as db:
        print("🔍 Przeszukuję bazę...")
        
        # 1. Sprawdzamy czy użytkownik już istnieje
        result = await db.execute(select(User).where(User.username == "kuczyna"))
        if result.scalar_one_or_none():
            print("ℹ️ Użytkownik 'kuczyna' już istnieje.")
            return

        # 2. Hashowanie hasła (ręczne, aby uniknąć błędów passlib/bcrypt)
        password = "1234"
        salt = bcrypt.gensalt()
        hashed_password = bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

        # 3. Tworzenie obiektu zgodnie z Twoją klasą
        print("🔨 Generuję konto dla kuczyna...")
        new_user = User(
            username="kuczyna",
            hashed_password=hashed_password,
            role="ADMIN",        # Nadpisujemy domyślne WEB_USER
            is_active=True       # KLUCZOWE: zmieniamy z False na True
        )
        
        try:
            db.add(new_user)
            await db.commit()
            print("---")
            print("✅ SUKCES! Konto utworzone i aktywowane.")
            print(f"Login: kuczyna")
            print(f"Hasło: {password}")
            print("---")
        except Exception as e:
            await db.rollback()
            print(f"❌ Błąd zapisu do bazy: {e}")

if __name__ == "__main__":
    # Poprawka dla Windows
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    asyncio.run(create_admin())