from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.database import get_db
from app.db.models import User
from app.db.schemas import UserCreate, UserResponse, Token
from app.api.deps import get_current_user, get_current_admin
from app.core.security import verify_password, create_access_token
from app.services import users_service

router = APIRouter(tags=["Autoryzacja i Użytkownicy"])

# ╔════════════════════════════════════════════════════════════════════════╗
# ║ 🔑 LOGOWANIE I TOKENY JWT                                              ║
# ╚════════════════════════════════════════════════════════════════════════╝
@router.post("/auth/login", response_model=Token)
async def login_for_access_token(
    db: AsyncSession = Depends(get_db),
    form_data: OAuth2PasswordRequestForm = Depends()
):
    """Wydaje token JWT po weryfikacji loginu i hasła w Swagger/Frontendzie."""
    result = await db.execute(select(User).where(User.username == form_data.username))
    user = result.scalar_one_or_none()
    
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Niepoprawny login lub hasło",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token = create_access_token(data={"sub": user.username})
    return {"access_token": access_token, "token_type": "bearer"}

# ╔════════════════════════════════════════════════════════════════════════╗
# ║ 👤 PROFIL UŻYTKOWNIKA                                                  ║
# ╚════════════════════════════════════════════════════════════════════════╝
@router.get("/users/me", response_model=UserResponse)
async def read_users_me(current_user: User = Depends(get_current_user)):
    """Zwraca profil aktualnie zalogowanego użytkownika (na podstawie tokena)."""
    return current_user

# ╔════════════════════════════════════════════════════════════════════════╗
# ║ 🆕 REJESTRACJA (TYLKO ADMIN)                                           ║
# ╚════════════════════════════════════════════════════════════════════════╝
@router.post("/users/register", response_model=UserResponse)
async def register_new_user(
    user_data: UserCreate, 
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(get_current_admin)
):
    """Rejestracja nowego użytkownika - dostępna tylko dla konta z rolą ADMIN."""
    return await users_service.register_new_user(db, user_data)