import asyncio
from app.db.database import SessionLocal
from app.db.models import User
from app.core.security import hash_password
from sqlalchemy import select

async def create_user(username, password, role):
    async with SessionLocal() as db:
        # 1. Sprawdz czy taki uzytkownik juz istnieje
        result = await db.execute(select(User).where(User.username == username))
        existing_user = result.scalar_one_or_none()
        
        if existing_user:
            print(f"⚠️ Użytkownik '{username}' już istnieje w bazie!")
            return

        # 2. Tworzenie nowego użytkownika
        new_user = User(
            username=username,
            hashed_password=hash_password(password),
            role=role.upper(),
            is_active=True
        )
        
        db.add(new_user)
        await db.commit()
        print(f"✅ Sukces: Utworzono użytkownika '{username}' z rolą '{role.upper()}'.")

if __name__ == "__main__":
    print("--- KREATOR UŻYTKOWNIKÓW FLOW CONTROL V2 ---")
    u = input("Podaj login: ").strip()
    p = input("Podaj hasło: ").strip()
    r = input("Podaj rolę (ADMIN / WEB_USER): ").strip() or "WEB_USER"

    if u and p:
        asyncio.run(create_user(u, p, r))
    else:
        print("❌ Błąd: Login i hasło nie mogą być puste.")