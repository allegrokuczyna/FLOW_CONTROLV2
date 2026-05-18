from pydantic import BaseModel
from typing import Optional, Union, List
from datetime import date

class UserCreate(BaseModel):
    username: str
    password: str
    role: Optional[str] = "WEB_USER"


class UserResponse(BaseModel):
    id: int
    username: str
    role: str
    is_active: bool

    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None

class AssignmentSchema(BaseModel):
    worker_login: str
    shift: str
    task: str

class AiRequest(BaseModel):
    shift: Union[int, str]
    target_date: Optional[str] = None


class ZoneConstraintUpdate(BaseModel):
    zone_name: str
    category: str
    priority: str
    s1_min: int
    s1_max: int
    s2_min: int
    s2_max: int
    s3_min: int
    s3_max: int

class DailyConstraintsSave(BaseModel):
    target_date: date
    constraints: List[ZoneConstraintUpdate]