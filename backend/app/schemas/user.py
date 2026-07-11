import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from backend.app.models.user import UserRole


class UserBase(BaseModel):
    email: EmailStr
    username: str = Field(min_length=3, max_length=100)


class UserCreate(UserBase):
    password: str = Field(min_length=8, max_length=128)


class UserRead(UserBase):
    id: uuid.UUID
    role: UserRole
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

