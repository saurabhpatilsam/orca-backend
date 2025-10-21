"""
Authentication models for request/response validation
"""
from pydantic import BaseModel, EmailStr, Field, ConfigDict
from typing import Optional
from datetime import datetime
from uuid import UUID


class UserSignupRequest(BaseModel):
    """Request model for user registration"""
    email: EmailStr
    password: str = Field(..., min_length=8)
    name: str = Field(..., min_length=1)


class UserSigninRequest(BaseModel):
    """Request model for user login"""
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    """Response model for user data (without sensitive info)"""
    id: UUID
    email: str
    name: Optional[str] = None
    confirmed: bool
    is_active: bool
    created_at: datetime
    last_login: Optional[datetime] = None
    
    model_config = ConfigDict(from_attributes=True)


class TokenResponse(BaseModel):
    """Response model for authentication tokens"""
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class ChangePasswordRequest(BaseModel):
    """Request model for password change"""
    old_password: str
    new_password: str = Field(..., min_length=8)


class PasswordResetRequest(BaseModel):
    """Request model for password reset"""
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    """Request model for confirming password reset"""
    token: str
    new_password: str = Field(..., min_length=8)


class OrganizationCreate(BaseModel):
    """Request model for creating an organization"""
    name: str = Field(..., min_length=1)
    slug: str = Field(..., min_length=1, pattern=r'^[a-z0-9-]+$')


class OrganizationResponse(BaseModel):
    """Response model for organization data"""
    id: UUID
    name: str
    slug: str
    owner_id: UUID
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class OrganizationMemberAdd(BaseModel):
    """Request model for adding a member to organization"""
    user_email: EmailStr
    role: str = Field(default="member", pattern=r'^(owner|admin|member)$')


class SessionInfo(BaseModel):
    """Session information"""
    id: UUID
    user_id: UUID
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    expires_at: datetime
    created_at: datetime
