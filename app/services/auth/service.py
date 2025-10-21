"""
Authentication service for user management
"""
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple
from uuid import UUID
import hashlib

from app.services.orca_supabase.orca_supabase import SUPABASE
from app.services.auth.password import hash_password, verify_password
from app.services.auth.jwt import create_access_token, create_token_hash, generate_verification_token
from app.services.auth.models import UserSignupRequest, UserSigninRequest, UserResponse


class AuthService:
    """Service for handling authentication operations"""
    
    @staticmethod
    def create_user(signup_data: UserSignupRequest) -> Tuple[Optional[UserResponse], Optional[str]]:
        """
        Create a new user account
        
        Args:
            signup_data: User signup information
            
        Returns:
            Tuple of (UserResponse, error_message)
        """
        try:
            # Check if user already exists
            existing = SUPABASE.table("users").select("id").eq("email", signup_data.email).execute()
            if existing.data:
                return None, "Email already registered"
            
            # Hash password
            password_hash = hash_password(signup_data.password)
            
            # Create user record
            user_data = {
                "email": signup_data.email,
                "password_hash": password_hash,
                "name": signup_data.name,
                "confirmed": False,  # User needs admin confirmation
                "is_active": True,
                "created_at": datetime.now(timezone.utc).isoformat()
            }
            
            response = SUPABASE.table("users").insert(user_data).execute()
            
            if not response.data:
                return None, "Failed to create user"
            
            user = response.data[0]
            return UserResponse(**user), None
            
        except Exception as e:
            return None, str(e)
    
    @staticmethod
    def authenticate_user(signin_data: UserSigninRequest) -> Tuple[Optional[dict], Optional[str]]:
        """
        Authenticate a user and return user data with token
        
        Args:
            signin_data: User signin credentials
            
        Returns:
            Tuple of (user_dict_with_token, error_message)
        """
        try:
            # Get user by email
            response = SUPABASE.table("users").select("*").eq("email", signin_data.email).execute()
            
            if not response.data:
                return None, "Invalid email or password"
            
            user = response.data[0]
            
            # Check if user is confirmed
            if not user.get("confirmed", False):
                return None, "Account not confirmed. Please contact administrator."
            
            # Check if user is active
            if not user.get("is_active", True):
                return None, "Account has been deactivated"
            
            # Verify password
            if not verify_password(signin_data.password, user["password_hash"]):
                return None, "Invalid email or password"
            
            # Update last login
            SUPABASE.table("users").update({
                "last_login": datetime.now(timezone.utc).isoformat()
            }).eq("id", user["id"]).execute()
            
            # Create access token
            token_data = {
                "sub": user["id"],
                "email": user["email"],
                "name": user.get("name")
            }
            access_token = create_access_token(token_data)
            
            # Store session
            AuthService._create_session(
                user_id=user["id"],
                token=access_token,
                ip_address=None,  # Will be set by endpoint
                user_agent=None   # Will be set by endpoint
            )
            
            # Remove password hash from response
            user_response = {k: v for k, v in user.items() if k != "password_hash"}
            
            return {
                "user": UserResponse(**user_response),
                "access_token": access_token,
                "token_type": "bearer"
            }, None
            
        except Exception as e:
            return None, str(e)
    
    @staticmethod
    def _create_session(
        user_id: str,
        token: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        expires_minutes: int = 1440  # 24 hours
    ) -> Optional[dict]:
        """
        Create a session record
        
        Args:
            user_id: User UUID
            token: JWT access token
            ip_address: Client IP address
            user_agent: Client user agent
            expires_minutes: Session expiration in minutes
            
        Returns:
            Session record or None
        """
        try:
            token_hash = create_token_hash(token)
            expires_at = datetime.now(timezone.utc) + timedelta(minutes=expires_minutes)
            
            session_data = {
                "user_id": user_id,
                "token_hash": token_hash,
                "ip_address": ip_address,
                "user_agent": user_agent,
                "expires_at": expires_at.isoformat(),
                "created_at": datetime.now(timezone.utc).isoformat()
            }
            
            response = SUPABASE.table("sessions").insert(session_data).execute()
            return response.data[0] if response.data else None
            
        except Exception as e:
            print(f"Error creating session: {e}")
            return None
    
    @staticmethod
    def get_user_by_id(user_id: str) -> Optional[UserResponse]:
        """
        Get user by ID
        
        Args:
            user_id: User UUID
            
        Returns:
            UserResponse or None
        """
        try:
            response = SUPABASE.table("users").select("*").eq("id", user_id).execute()
            
            if not response.data:
                return None
            
            user = response.data[0]
            # Remove password hash
            user_data = {k: v for k, v in user.items() if k != "password_hash"}
            return UserResponse(**user_data)
            
        except Exception as e:
            print(f"Error getting user: {e}")
            return None
    
    @staticmethod
    def validate_session(token: str) -> Optional[UserResponse]:
        """
        Validate a session token and return user
        
        Args:
            token: JWT access token
            
        Returns:
            UserResponse if valid, None otherwise
        """
        from app.services.auth.jwt import decode_access_token
        
        try:
            # Decode token
            payload = decode_access_token(token)
            if not payload:
                return None
            
            user_id = payload.get("sub")
            if not user_id:
                return None
            
            # Check if session exists and is valid
            token_hash = create_token_hash(token)
            session_response = (
                SUPABASE.table("sessions")
                .select("*")
                .eq("token_hash", token_hash)
                .gte("expires_at", datetime.now(timezone.utc).isoformat())
                .execute()
            )
            
            if not session_response.data:
                return None
            
            # Get user
            return AuthService.get_user_by_id(user_id)
            
        except Exception as e:
            print(f"Error validating session: {e}")
            return None
    
    @staticmethod
    def signout(token: str) -> bool:
        """
        Sign out user by invalidating session
        
        Args:
            token: JWT access token
            
        Returns:
            True if successful, False otherwise
        """
        try:
            token_hash = create_token_hash(token)
            
            # Delete session
            SUPABASE.table("sessions").delete().eq("token_hash", token_hash).execute()
            return True
            
        except Exception as e:
            print(f"Error signing out: {e}")
            return False
    
    @staticmethod
    def confirm_user(user_id: str) -> Tuple[Optional[UserResponse], Optional[str]]:
        """
        Confirm a user account (admin action)
        
        Args:
            user_id: User UUID to confirm
            
        Returns:
            Tuple of (UserResponse, error_message)
        """
        try:
            response = (
                SUPABASE.table("users")
                .update({"confirmed": True, "updated_at": datetime.now(timezone.utc).isoformat()})
                .eq("id", user_id)
                .execute()
            )
            
            if not response.data:
                return None, "User not found"
            
            user = response.data[0]
            user_data = {k: v for k, v in user.items() if k != "password_hash"}
            return UserResponse(**user_data), None
            
        except Exception as e:
            return None, str(e)
    
    @staticmethod
    def get_all_users() -> list[UserResponse]:
        """
        Get all users (admin function)
        
        Returns:
            List of UserResponse objects
        """
        try:
            response = SUPABASE.table("users").select("*").order("created_at", desc=True).execute()
            
            users = []
            for user in response.data:
                user_data = {k: v for k, v in user.items() if k != "password_hash"}
                users.append(UserResponse(**user_data))
            
            return users
            
        except Exception as e:
            print(f"Error getting users: {e}")
            return []
    
    @staticmethod
    def get_user_permissions(user_id: str) -> list[str]:
        """
        Get permissions for a user
        
        Args:
            user_id: User UUID
            
        Returns:
            List of permission strings
        """
        try:
            response = (
                SUPABASE.table("user_permissions")
                .select("permission")
                .eq("user_id", user_id)
                .execute()
            )
            
            return [p["permission"] for p in response.data]
            
        except Exception as e:
            print(f"Error getting permissions: {e}")
            return []
