"""
Authentication dependencies for FastAPI endpoints
"""
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.services.auth.jwt import decode_access_token
from app.services.auth.service import AuthService
from app.services.auth.models import UserResponse

# Security scheme for JWT Bearer token
security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> UserResponse:
    """
    Dependency to get the current authenticated user from JWT token.
    
    This dependency:
    1. Extracts the JWT token from Authorization header
    2. Validates the token
    3. Retrieves the user from database
    4. Returns the user object
    
    Usage:
        @app.get("/protected")
        async def protected_route(current_user: UserResponse = Depends(get_current_user)):
            return {"user": current_user.email}
    
    Raises:
        HTTPException: 401 if token is invalid or user not found
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    # Extract token from credentials
    token = credentials.credentials
    
    # Decode token
    payload = decode_access_token(token)
    if payload is None:
        raise credentials_exception
    
    # Extract user_id from token
    user_id: str = payload.get("sub")
    if user_id is None:
        raise credentials_exception
    
    # Get user from database
    user = AuthService.get_user_by_id(user_id)
    if user is None:
        raise credentials_exception
    
    return user


async def get_current_active_user(
    current_user: UserResponse = Depends(get_current_user)
) -> UserResponse:
    """
    Dependency to get the current active (confirmed) user.
    
    This adds an additional check to ensure the user is confirmed.
    
    Usage:
        @app.get("/admin-only")
        async def admin_route(user: UserResponse = Depends(get_current_active_user)):
            return {"user": user.email}
    
    Raises:
        HTTPException: 400 if user is not confirmed
    """
    if not current_user.confirmed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User account not confirmed. Please contact an administrator."
        )
    return current_user


async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False))
) -> Optional[UserResponse]:
    """
    Optional authentication dependency.
    Returns user if token is valid, None if no token provided.
    
    Useful for endpoints that work with or without authentication.
    
    Usage:
        @app.get("/maybe-protected")
        async def route(user: Optional[UserResponse] = Depends(get_optional_user)):
            if user:
                return {"message": f"Hello {user.email}"}
            return {"message": "Hello guest"}
    """
    if credentials is None:
        return None
    
    try:
        token = credentials.credentials
        payload = decode_access_token(token)
        if payload is None:
            return None
        
        user_id = payload.get("sub")
        if user_id is None:
            return None
        
        user = AuthService.get_user_by_id(user_id)
        return user
    except Exception:
        return None
