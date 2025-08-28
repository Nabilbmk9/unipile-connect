"""
Pydantic schemas for request/response validation
"""
from pydantic import BaseModel, EmailStr, validator
from typing import Optional, List
from datetime import datetime

# User schemas
class UserBase(BaseModel):
    username: str
    email: EmailStr
    full_name: Optional[str] = None

class UserCreate(UserBase):
    password: str
    
    @validator('password')
    def password_strength(cls, v):
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        return v
    
    @validator('username')
    def username_valid(cls, v):
        if len(v) < 3:
            raise ValueError('Username must be at least 3 characters long')
        if not v.isalnum():
            raise ValueError('Username must contain only letters and numbers')
        return v

class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    is_active: Optional[bool] = None

class UserResponse(UserBase):
    id: int
    is_active: bool
    is_admin: bool
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

# Authentication schemas
class UserLogin(BaseModel):
    username: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int

class SessionResponse(BaseModel):
    session_id: str
    expires_at: datetime
    user: UserResponse

# Account schemas
class ConnectedAccountBase(BaseModel):
    provider: str
    status: str

class ConnectedAccountCreate(ConnectedAccountBase):
    account_id: str
    user_id: int
    account_data: Optional[str] = None

class ConnectedAccountResponse(ConnectedAccountBase):
    id: int
    account_id: str
    user_id: int
    connected_at: datetime
    last_sync: Optional[datetime] = None
    account_data: Optional[str] = None
    
    class Config:
        from_attributes = True

# Dashboard schemas
class DashboardStats(BaseModel):
    total_accounts: int
    active_accounts: int
    pending_accounts: int
    total_users: int
    recent_connections: List[ConnectedAccountResponse]

# Admin schemas
class AdminUserCreate(UserCreate):
    is_admin: bool = False

class AdminUserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    is_active: Optional[bool] = None
    is_admin: Optional[bool] = None

# Error schemas
class ErrorResponse(BaseModel):
    detail: str
    error_code: Optional[str] = None

# Success schemas
class SuccessResponse(BaseModel):
    message: str
    data: Optional[dict] = None
