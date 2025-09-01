"""
Authentication and user management for Unipile Connect
"""
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional, Union
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
# Workaround for passlib + bcrypt>=4 on Python 3.12 where __about__.__version__
# was removed from the bcrypt package. Passlib 1.7.x still probes this attribute
# and logs noisy errors. We add a minimal shim before importing passlib.
import bcrypt  # type: ignore
try:  # pragma: no cover - defensive shim
    _ = bcrypt.__about__.__version__  # noqa: F401
except Exception:  # Attribute missing on bcrypt>=4
    try:
        version = getattr(bcrypt, "__version__", "4")
        class _About:  # lightweight container to satisfy passlib check
            __version__ = version
        bcrypt.__about__ = _About()  # type: ignore[attr-defined]
    except Exception:
        pass
from passlib.context import CryptContext
from jose import JWTError, jwt
from sqlalchemy.orm import Session
from sqlalchemy import func

from .database import get_db, User, UserSession, ConnectedAccount

# Security configuration
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-this-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours
SESSION_EXPIRE_HOURS = 24

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT token security
security = HTTPBearer()

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash"""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """Hash a password"""
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Create a JWT access token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verify_token(token: str) -> Optional[dict]:
    """Verify and decode a JWT token"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None

def authenticate_user(db: Session, username: str, password: str) -> Optional[User]:
    """Authenticate a user with username and password"""
    user = db.query(User).filter(User.username == username).first()
    if not user or not verify_password(password, user.hashed_password):
        return None
    return user

def get_user_by_username(db: Session, username: str) -> Optional[User]:
    """Get user by username"""
    return db.query(User).filter(User.username == username).first()

def get_user_by_email(db: Session, email: str) -> Optional[User]:
    """Get user by email"""
    if not email:
        return None
    email_clean = email.strip().lower()
    return db.query(User).filter(func.lower(User.email) == email_clean).first()

def create_user(
    db: Session, 
    username: str, 
    email: str, 
    password: str, 
    full_name: Optional[str] = None,
    is_admin: bool = False
) -> User:
    """Create a new user"""
    # Check if username or email already exists
    if get_user_by_username(db, username):
        raise HTTPException(
            status_code=400,
            detail="Username already registered"
        )
    
    if get_user_by_email(db, email):
        raise HTTPException(
            status_code=400,
            detail="Email already registered"
        )
    
    # Create new user
    hashed_password = get_password_hash(password)
    user = User(
        username=username,
        email=email.strip().lower(),
        hashed_password=hashed_password,
        full_name=full_name,
        is_admin=is_admin
    )
    
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

def create_session(db: Session, user_id: int) -> str:
    """Create a new session for user"""
    session_id = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=SESSION_EXPIRE_HOURS)
    
    session = UserSession(
        session_id=session_id,
        user_id=user_id,
        expires_at=expires_at
    )
    
    db.add(session)
    db.commit()
    return session_id

def get_current_user_session(request: Request, db: Session = Depends(get_db)) -> Optional[UserSession]:
    """Get current user session from session cookie"""
    session_id = request.cookies.get("session_id")
    if not session_id:
        return None
    
    # Check session in database
    session = db.query(UserSession).filter(
        UserSession.session_id == session_id,
        UserSession.expires_at > datetime.now(timezone.utc)
    ).first()
    
    if not session:
        return None
    
    # Get user and check if active
    user = db.query(User).filter(User.id == session.user_id).first()
    if not user or not user.is_active:
        return None
    
    return session

def get_current_user_jwt(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """Get current user from JWT token"""
    token = credentials.credentials
    payload = verify_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    username: str = payload.get("sub")
    if not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user = get_user_by_username(db, username)
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return user

def require_admin(user: User = Depends(get_current_user_session)) -> User:
    """Require admin privileges"""
    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
        )
    return user

def delete_session(db: Session, session_id: str) -> bool:
    """Delete a user session"""
    session = db.query(UserSession).filter(UserSession.session_id == session_id).first()
    if session:
        db.delete(session)
        db.commit()
        return True
    return False

def cleanup_expired_sessions(db: Session):
    """Clean up expired sessions"""
    expired_sessions = db.query(UserSession).filter(
        UserSession.expires_at < datetime.now(timezone.utc)
    ).all()
    
    for session in expired_sessions:
        db.delete(session)
    
    db.commit()
    return len(expired_sessions)
