"""
Database configuration and models for Unipile Connect
"""
import os
from pathlib import Path
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean, Text, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.sql import func
from datetime import datetime, timezone

# Database URL - use environment variable or default to SQLite under a persistent data dir
# Default path: ./data/unipile_connect.db (relative to project/app root)
_default_data_dir = Path(__file__).resolve().parents[1] / "data"
try:
    _default_data_dir.mkdir(parents=True, exist_ok=True)
except Exception:
    # In restricted environments the dir may already exist or be non-creatable; ignore
    pass
_default_sqlite_url = f"sqlite:///{(_default_data_dir / 'unipile_connect.db').as_posix()}"
DATABASE_URL = os.getenv("DATABASE_URL", _default_sqlite_url)

# Create engine
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {}
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create base class for models
Base = declarative_base()

# Database dependency
def get_db():
    """Get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# User Model
class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(100), nullable=True)
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    accounts = relationship("ConnectedAccount", back_populates="user")
    sessions = relationship("UserSession", back_populates="user")
    # Reset tokens
    reset_tokens = relationship("PasswordResetToken", back_populates="user")

# User Session Model
class UserSession(Base):
    __tablename__ = "user_sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(255), unique=True, index=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    user = relationship("User", back_populates="sessions")

# Connected Account Model
class ConnectedAccount(Base):
    __tablename__ = "connected_accounts"
    
    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(String(255), unique=True, index=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    provider = Column(String(50), nullable=False)  # LINKEDIN, FACEBOOK, etc.
    status = Column(String(50), nullable=False)    # CREATION_SUCCESS, PENDING, etc.
    account_data = Column(Text, nullable=True)     # JSON data from Unipile
    connected_at = Column(DateTime(timezone=True), server_default=func.now())
    last_sync = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="accounts")

# Password reset token model
class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    token = Column(String(255), unique=True, index=True, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    used = Column(Boolean, default=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    user = relationship("User", back_populates="reset_tokens")

# Create all tables
def create_tables():
    """Create all database tables"""
    Base.metadata.create_all(bind=engine)

# Initialize database
def init_db():
    """Initialize database with tables and admin user"""
    create_tables()
    print("✅ Database tables created successfully")
    print("📝 Users can now register accounts through the application")
