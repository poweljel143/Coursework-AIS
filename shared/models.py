from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from enum import Enum

class UserRole(str, Enum):
    CLIENT = "client"
    MANAGER = "manager"
    ADMIN = "admin"

class UserBase(BaseModel):
    email: str
    full_name: str
    phone: Optional[str] = None
    role: UserRole = UserRole.CLIENT

class UserCreate(UserBase):
    password: str

class UserResponse(UserBase):
    id: int
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class TokenData(BaseModel):
    user_id: Optional[int] = None
    email: Optional[str] = None
    role: Optional[UserRole] = None

# Event models for message broker
class EventBase(BaseModel):
    event_id: str
    event_type: str
    timestamp: datetime
    payload: dict

class OrderEvent(EventBase):
    pass

class PaymentEvent(EventBase):
    pass

class FinancingEvent(EventBase):
    pass

class InsuranceEvent(EventBase):
    pass