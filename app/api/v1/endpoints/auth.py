"""
Authentication endpoints
"""
from fastapi import APIRouter, HTTPException, Depends, status, Header, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional

from app.services.auth.models import (
    UserSignupRequest,
    UserSigninRequest,
    TokenResponse,
    UserResponse
)
from app.services.auth.service import AuthService

router = APIRouter(prefix="/auth", tags=["authentication"])
security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> UserResponse:
    """
    Dependency to get the current authenticated user
    """
    token = credentials.credentials
    user = AuthService.validate_session(token)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return user


async def get_current_confirmed_user(
    current_user: UserResponse = Depends(get_current_user)
) -> UserResponse:
    """
    Dependency to ensure user is confirmed
    """
    if not current_user.confirmed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account not confirmed"
        )
    
    return current_user


@router.post("/signup", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def signup(signup_data: UserSignupRequest):
    """
    Register a new user account
    
    Note: User account will be created but NOT confirmed.
    An administrator must confirm the account before the user can log in.
    """
    user, error = AuthService.create_user(signup_data)
    
    if error:
        # raise error
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error
        )
    
    return user


@router.post("/signin", response_model=TokenResponse)
async def signin(
    signin_data: UserSigninRequest,
    request: Request
):
    """
    Sign in with email and password
    
    Returns JWT access token if credentials are valid and user is confirmed.
    """
    result, error = AuthService.authenticate_user(signin_data)
    
    if error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=error,
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Update session with request info
    # (This is a simplified version - you might want to update the session record)
    
    return result


@router.post("/signout")
async def signout(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """
    Sign out the current user (invalidate session)
    """
    token = credentials.credentials
    success = AuthService.signout(token)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to sign out"
        )
    
    return {"message": "Successfully signed out"}


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: UserResponse = Depends(get_current_user)
):
    """
    Get current authenticated user information
    """
    return current_user


@router.get("/users", response_model=list[UserResponse])
async def get_all_users(
    current_user: UserResponse = Depends(get_current_confirmed_user)
):
    """
    Get all users (requires confirmed account)
    
    In production, you should add admin role checking here
    """
    users = AuthService.get_all_users()
    return users


@router.post("/users/{user_id}/confirm", response_model=UserResponse)
async def confirm_user(
    user_id: str,
    current_user: UserResponse = Depends(get_current_confirmed_user)
):
    """
    Confirm a user account (admin action)
    
    In production, you should add admin role checking here
    """
    user, error = AuthService.confirm_user(user_id)
    
    if error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error
        )
    
    return user


@router.get("/users/{user_id}/permissions")
async def get_user_permissions(
    user_id: str,
    current_user: UserResponse = Depends(get_current_confirmed_user)
):
    """
    Get permissions for a specific user
    """
    # In production, check if current_user has permission to view this
    permissions = AuthService.get_user_permissions(user_id)
    
    return {"user_id": user_id, "permissions": permissions}


@router.get("/health")
async def auth_health():
    """
    Health check for auth service
    """
    return {"status": "healthy", "service": "authentication"}
