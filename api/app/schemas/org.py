import uuid

from pydantic import BaseModel, EmailStr


class DepartmentCreate(BaseModel):
    name: str
    parent_id: uuid.UUID | None = None


class DepartmentOut(BaseModel):
    id: uuid.UUID
    name: str
    parent_id: uuid.UUID | None

    model_config = {"from_attributes": True}


class TeamCreate(BaseModel):
    name: str


class TeamOut(BaseModel):
    id: uuid.UUID
    name: str

    model_config = {"from_attributes": True}


class UserCreate(BaseModel):
    email: EmailStr
    password: str
    display_name: str
    role: str = "user"
    department_id: uuid.UUID | None = None


class TeamMemberAdd(BaseModel):
    user_id: uuid.UUID
