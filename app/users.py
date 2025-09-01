"""
User management routes for Unipile Connect
"""
from fastapi import APIRouter, Depends, HTTPException, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db, User, PasswordResetToken
from app.auth import get_current_user_session, get_password_hash, verify_password, get_user_by_username, get_user_by_email, create_user
from datetime import datetime, timedelta, timezone
import os
import smtplib
import ssl
from email.message import EmailMessage
import secrets
def _is_expired(expires_at: datetime) -> bool:
    """Return True if expires_at is in the past. Handles naive datetimes from SQLite.

    Some SQLite drivers drop timezone info. If the datetime is naive, we
    assume it's in UTC and attach tzinfo=UTC before comparing.
    """
    now_utc = datetime.now(timezone.utc)
    if isinstance(expires_at, datetime):
        dt = expires_at
        if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
            dt = dt.replace(tzinfo=timezone.utc)
        else:
            dt = dt.astimezone(timezone.utc)
        return dt < now_utc
    # If for some reason it's not a datetime, consider it expired
    return True
from app.schemas import UserCreate, UserUpdate, AdminUserCreate, AdminUserUpdate
import re

router = APIRouter()
# Use absolute path to avoid template lookup issues in staging
TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

@router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})

@router.post("/register")
async def register_user(
    request: Request,
    username: str = Form(...),
    email: str = Form(...),
    full_name: str = Form(None),
    password: str = Form(...),
    confirm_password: str = Form(...),
    db: Session = Depends(get_db)
):
    # Validation
    if password != confirm_password:
        return templates.TemplateResponse("register.html", {
            "request": request,
            "error": "Les mots de passe ne correspondent pas"
        })
    
    if len(password) < 8:
        return templates.TemplateResponse("register.html", {
            "request": request,
            "error": "Le mot de passe doit contenir au moins 8 caractères"
        })
    
    if len(username) < 3:
        return templates.TemplateResponse("register.html", {
            "request": request,
            "error": "Le nom d'utilisateur doit contenir au moins 3 caractères"
        })
    
    # Check if username already exists
    existing_user = get_user_by_username(db, username)
    if existing_user:
        return templates.TemplateResponse("register.html", {
            "request": request,
            "error": "Ce nom d'utilisateur est déjà pris"
        })
    
    # Check if email already exists
    existing_email = get_user_by_email(db, email)
    if existing_email:
        return templates.TemplateResponse("register.html", {
            "request": request,
            "error": "Cet email est déjà utilisé"
        })
    
    try:
        # Create user
        user = create_user(
            db=db,
            username=username,
            email=email,
            password=password,
            full_name=full_name,
            is_admin=False
        )
        
        return RedirectResponse(url="/login?success=account_created", status_code=303)
    except Exception as e:
        return templates.TemplateResponse("register.html", {
            "request": request,
            "error": "Une erreur s'est produite lors de l'inscription"
        })

@router.get("/forgot-password", response_class=HTMLResponse)
async def forgot_password_page(request: Request):
    return templates.TemplateResponse("forgot_password.html", {"request": request})

@router.post("/forgot-password")
async def forgot_password(
    request: Request,
    email: str = Form(...),
    db: Session = Depends(get_db)
):
    # Generic response to avoid account enumeration
    generic_message = "Si un compte existe avec cet email, vous recevrez un lien de réinitialisation"

    user = get_user_by_email(db, email)
    debug_reset_url = None
    if user:
        # Invalidate existing tokens for this user
        db.query(PasswordResetToken).filter(
            PasswordResetToken.user_id == user.id,
            PasswordResetToken.used == False
        ).delete(synchronize_session=False)

        # Create new token valid for 30 minutes
        token = secrets.token_urlsafe(48)
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=30)
        prt = PasswordResetToken(user_id=user.id, token=token, expires_at=expires_at)
        db.add(prt)
        db.commit()

        # Build reset URL
        from app.main import APP_BASE_URL
        reset_url = f"{APP_BASE_URL}/users/reset-password?token={token}"

        # Attempt to send email if SMTP is configured; otherwise log
        smtp_host = os.getenv("SMTP_HOST")
        smtp_port = int(os.getenv("SMTP_PORT", "587"))
        smtp_user = os.getenv("SMTP_USER")
        smtp_password = os.getenv("SMTP_PASSWORD")
        smtp_from = os.getenv("SMTP_FROM", smtp_user or "no-reply@example.com")
        use_tls = os.getenv("SMTP_USE_TLS", "true").lower() == "true"

        if smtp_host and smtp_user and smtp_password:
            try:
                msg = EmailMessage()
                msg["Subject"] = "Lien de réinitialisation du mot de passe"
                msg["From"] = smtp_from
                msg["To"] = email
                msg.set_content(
                    f"Bonjour,\n\nCliquez sur ce lien pour réinitialiser votre mot de passe: {reset_url}\n\nCe lien expire dans 30 minutes.\n\nSi vous n'êtes pas à l'origine de cette demande, ignorez cet email."
                )

                if use_tls:
                    context = ssl.create_default_context()
                    with smtplib.SMTP(smtp_host, smtp_port, timeout=20) as server:
                        server.starttls(context=context)
                        server.login(smtp_user, smtp_password)
                        server.send_message(msg)
                else:
                    with smtplib.SMTP(smtp_host, smtp_port, timeout=20) as server:
                        server.login(smtp_user, smtp_password)
                        server.send_message(msg)
                print(f"[PasswordReset] Email sent to {email}")
            except Exception as e:
                print(f"[PasswordReset] Email send failed for {email}: {e}. Link: {reset_url}")
        else:
            print(f"[PasswordReset] Send reset link to {email}: {reset_url}")

        # Optionally expose the link on the page in development
        if os.getenv("SHOW_RESET_LINK_ON_PAGE", "false").lower() == "true":
            debug_reset_url = reset_url

    return templates.TemplateResponse(
        "forgot_password.html",
        {"request": request, "success": generic_message, "debug_reset_url": debug_reset_url},
    )

@router.get("/reset-password", response_class=HTMLResponse)
async def reset_password_page(request: Request, token: str, db: Session = Depends(get_db)):
    # Validate token
    prt = db.query(PasswordResetToken).filter(PasswordResetToken.token == token).first()
    if not prt or prt.used or _is_expired(prt.expires_at):
        return templates.TemplateResponse("forgot_password.html", {
            "request": request,
            "error": "Lien de réinitialisation invalide ou expiré"
        })

    return templates.TemplateResponse("reset_password.html", {"request": request, "token": token})

@router.post("/reset-password")
async def reset_password_submit(
    request: Request,
    token: str = Form(...),
    new_password: str = Form(...),
    confirm_password: str = Form(...),
    db: Session = Depends(get_db)
):
    # Validate token
    prt = db.query(PasswordResetToken).filter(PasswordResetToken.token == token).first()
    if not prt or prt.used or _is_expired(prt.expires_at):
        return templates.TemplateResponse("forgot_password.html", {
            "request": request,
            "error": "Lien de réinitialisation invalide ou expiré"
        })

    if new_password != confirm_password:
        return templates.TemplateResponse("reset_password.html", {
            "request": request,
            "token": token,
            "error": "Les mots de passe ne correspondent pas"
        })

    if len(new_password) < 8:
        return templates.TemplateResponse("reset_password.html", {
            "request": request,
            "token": token,
            "error": "Le mot de passe doit contenir au moins 8 caractères"
        })

    user = db.query(User).filter(User.id == prt.user_id).first()
    if not user:
        return templates.TemplateResponse("forgot_password.html", {
            "request": request,
            "error": "Utilisateur introuvable"
        })

    # Update password and mark token used
    user.hashed_password = get_password_hash(new_password)
    prt.used = True
    db.commit()

    return RedirectResponse(url="/login", status_code=303)

@router.get("/profile", response_class=HTMLResponse)
async def profile_page(request: Request, db: Session = Depends(get_db)):
    user_session = get_current_user_session(request, db)
    if not user_session:
        return RedirectResponse(url="/login", status_code=303)
    
    user = user_session.user
    return templates.TemplateResponse("profile.html", {
        "request": request,
        "user": user
    })

@router.post("/profile")
async def update_profile(
    request: Request,
    email: str = Form(...),
    full_name: str = Form(None),
    db: Session = Depends(get_db)
):
    user_session = get_current_user_session(request, db)
    if not user_session:
        return RedirectResponse(url="/login", status_code=303)
    
    user = user_session.user
    
    # Check if email is already taken by another user
    existing_email = db.query(User).filter(
        User.email == email,
        User.id != user.id
    ).first()
    if existing_email:
        return templates.TemplateResponse("profile.html", {
            "request": request,
            "user": user,
            "error": "Cet email est déjà utilisé par un autre compte"
        })
    
    # Update user
    user.email = email
    user.full_name = full_name
    db.commit()
    
    return templates.TemplateResponse("profile.html", {
        "request": request,
        "user": user,
        "success": "Profil mis à jour avec succès"
    })

@router.post("/change-password")
async def change_password(
    request: Request,
    current_password: str = Form(...),
    new_password: str = Form(...),
    confirm_password: str = Form(...),
    db: Session = Depends(get_db)
):
    user_session = get_current_user_session(request, db)
    if not user_session:
        return RedirectResponse(url="/login", status_code=303)
    
    user = user_session.user
    
    # Verify current password
    if not verify_password(current_password, user.hashed_password):
        return templates.TemplateResponse("profile.html", {
            "request": request,
            "user": user,
            "error": "Mot de passe actuel incorrect"
        })
    
    # Check if new passwords match
    if new_password != confirm_password:
        return templates.TemplateResponse("profile.html", {
            "request": request,
            "user": user,
            "error": "Les nouveaux mots de passe ne correspondent pas"
        })
    
    # Check password length
    if len(new_password) < 8:
        return templates.TemplateResponse("profile.html", {
            "request": request,
            "user": user,
            "error": "Le nouveau mot de passe doit contenir au moins 8 caractères"
        })
    
    # Update password
    user.hashed_password = get_password_hash(new_password)
    db.commit()
    
    return templates.TemplateResponse("profile.html", {
        "request": request,
        "user": user,
        "success": "Mot de passe modifié avec succès"
    })

@router.get("/admin", response_class=HTMLResponse)
async def admin_page(request: Request, db: Session = Depends(get_db)):
    user_session = get_current_user_session(request, db)
    if not user_session or not user_session.user.is_admin:
        return RedirectResponse(url="/dashboard", status_code=303)
    
    users = db.query(User).all()
    return templates.TemplateResponse("admin.html", {
        "request": request,
        "users": users
    })

@router.post("/admin/create")
async def admin_create_user(
    request: Request,
    username: str = Form(...),
    email: str = Form(...),
    full_name: str = Form(None),
    password: str = Form(...),
    is_admin: bool = Form(False),
    db: Session = Depends(get_db)
):
    user_session = get_current_user_session(request, db)
    if not user_session or not user_session.user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    # Check if username already exists
    existing_user = db.query(User).filter(User.username == username).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Username already exists")
    
    # Check if email already exists
    existing_email = db.query(User).filter(User.email == email).first()
    if existing_email:
        raise HTTPException(status_code=400, detail="Email already exists")
    
    # Create user
    hashed_password = get_password_hash(password)
    user = User(
        username=username,
        email=email,
        full_name=full_name,
        hashed_password=hashed_password,
        is_active=True,
        is_admin=is_admin
    )
    
    db.add(user)
    db.commit()
    
    return {"message": "User created successfully"}

@router.post("/admin/update/{user_id}")
async def admin_update_user(
    user_id: int,
    request: Request,
    email: str = Form(...),
    full_name: str = Form(None),
    is_active: bool = Form(True),
    is_admin: bool = Form(False),
    db: Session = Depends(get_db)
):
    user_session = get_current_user_session(request, db)
    if not user_session or not user_session.user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Check if email is already taken by another user
    existing_email = db.query(User).filter(
        User.email == email,
        User.id != user_id
    ).first()
    if existing_email:
        raise HTTPException(status_code=400, detail="Email already exists")
    
    # Update user
    user.email = email
    user.full_name = full_name
    user.is_active = is_active
    user.is_admin = is_admin
    db.commit()
    
    return {"message": "User updated successfully"}

@router.post("/admin/delete/{user_id}")
async def admin_delete_user(
    user_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    user_session = get_current_user_session(request, db)
    if not user_session or not user_session.user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Don't allow admin to delete themselves
    if user.id == user_session.user.id:
        raise HTTPException(status_code=400, detail="Cannot delete your own account")
    
    db.delete(user)
    db.commit()
    
    return {"message": "User deleted successfully"}

@router.get("/api/me")
async def get_current_user(request: Request, db: Session = Depends(get_db)):
    user_session = get_current_user_session(request, db)
    if not user_session:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    return {
        "id": user_session.user.id,
        "username": user_session.user.username,
        "email": user_session.user.email,
        "full_name": user_session.user.full_name,
        "is_admin": user_session.user.is_admin,
        "created_at": user_session.user.created_at
    }

@router.get("/api/users")
async def get_users(request: Request, db: Session = Depends(get_db)):
    user_session = get_current_user_session(request, db)
    if not user_session or not user_session.user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    users = db.query(User).all()
    return [
        {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "full_name": user.full_name,
            "is_active": user.is_active,
            "is_admin": user.is_admin,
            "created_at": user.created_at
        }
        for user in users
    ]
