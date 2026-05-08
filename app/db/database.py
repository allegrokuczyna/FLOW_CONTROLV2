from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base
from app.core.config import settings

# Inicjalizacja silnika bazy danych
engine = create_async_engine(settings.DATABASE_URL, echo=False)

# Fabryka sesji (połączeń)
AsyncSessionLocal = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

# Klasa bazowa dla naszych modeli
Base = declarative_base()

# Funkcja dostarczająca sesję do endpointów (Dependency Injection)
async def get_db():
    async with AsyncSessionLocal() as session:
        yield session