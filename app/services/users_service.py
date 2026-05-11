from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException, status
from app.db.models import User
from app.db.schemas import UserCreate
from app.core.security import hash_password

async def register_new_user(db: AsyncSession, user_data: UserCreate):

    result = await db.execute(select(User).where(User.username == user_data.username))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Użytkownik o takim loginie już istnieje."
        )


    new_user = User(
        username=user_data.username,
        hashed_password=hash_password(user_data.password),
        role=user_data.role.upper() if user_data.role else "WEB_USER"
    )
    
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    return new_user