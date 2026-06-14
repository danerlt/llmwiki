import uuid

from pydantic import BaseModel, EmailStr, Field


class DepartmentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    parent_id: uuid.UUID | None = None


class DepartmentOut(BaseModel):
    id: uuid.UUID
    name: str
    parent_id: uuid.UUID | None

    model_config = {"from_attributes": True}


class TeamCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)


class TeamOut(BaseModel):
    id: uuid.UUID
    name: str

    model_config = {"from_attributes": True}


class UserCreate(BaseModel):
    email: EmailStr = Field(max_length=320)
    password: str = Field(min_length=8, max_length=128)
    display_name: str = Field(min_length=1, max_length=255)
    role: str = "user"
    department_id: uuid.UUID | None = None


class TeamMemberAdd(BaseModel):
    user_id: uuid.UUID
    can_write: bool = True  # False=只读成员
