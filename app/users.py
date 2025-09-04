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
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.message import EmailMessage
import secrets
import logging
from dotenv import load_dotenv

# Ensure environment variables are loaded
load_dotenv()
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

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def send_password_reset_email(email: str, reset_url: str, user_name: str = None) -> bool:
    """
    Send a password reset email with HTML formatting.
    Returns True if email was sent successfully, False otherwise.
    """
    smtp_host = os.getenv("SMTP_HOST")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER")
    smtp_password = os.getenv("SMTP_PASSWORD")
    smtp_from = os.getenv("SMTP_FROM", smtp_user or "no-reply@example.com")
    use_tls = os.getenv("SMTP_USE_TLS", "true").lower() == "true"
    
    if not smtp_host or not smtp_user or not smtp_password:
        logger.warning("SMTP configuration incomplete. Required: SMTP_HOST, SMTP_USER, SMTP_PASSWORD")
        return False
    
    try:
        # Create HTML email content
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>Réinitialisation de mot de passe</title>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background-color: #4f46e5; color: white; padding: 20px; text-align: center; border-radius: 8px 8px 0 0; }}
                .content {{ background-color: #f9fafb; padding: 30px; border: 1px solid #e5e7eb; }}
                .footer {{ background-color: #374151; color: #d1d5db; padding: 20px; text-align: center; border-radius: 0 0 8px 8px; font-size: 14px; }}
                .button {{ display: inline-block; background-color: #4f46e5; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; font-weight: bold; margin: 20px 0; }}
                .button:hover {{ background-color: #3730a3; }}
                .warning {{ background-color: #fef3c7; border: 1px solid #f59e0b; color: #92400e; padding: 15px; border-radius: 6px; margin: 20px 0; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>🔒 Réinitialisation de mot de passe</h1>
                <p>Unipile Connect</p>
            </div>
            <div class="content">
                <h2>Bonjour{f" {user_name}" if user_name else ""},</h2>
                <p>Vous avez demandé la réinitialisation de votre mot de passe pour votre compte Unipile Connect.</p>
                <p>Cliquez sur le bouton ci-dessous pour créer un nouveau mot de passe :</p>
                <p style="text-align: center;">
                    <a href="{reset_url}" class="button">Réinitialiser mon mot de passe</a>
                </p>
                <p>Ou copiez et collez ce lien dans votre navigateur :</p>
                <p style="word-break: break-all; background-color: #e5e7eb; padding: 10px; border-radius: 4px; font-family: monospace;">{reset_url}</p>
                <div class="warning">
                    <strong>⚠️ Important :</strong>
                    <ul>
                        <li>Ce lien expire dans <strong>30 minutes</strong></li>
                        <li>Il ne peut être utilisé qu'une seule fois</li>
                        <li>Si vous n'êtes pas à l'origine de cette demande, ignorez cet email</li>
                    </ul>
                </div>
            </div>
            <div class="footer">
                <p>Cet email a été envoyé automatiquement, merci de ne pas y répondre.</p>
                <p>© 2024 Unipile Connect - Tous droits réservés</p>
            </div>
        </body>
        </html>
        """
        
        # Create plain text version as fallback
        text_content = f"""
Bonjour{f" {user_name}" if user_name else ""},

Vous avez demandé la réinitialisation de votre mot de passe pour votre compte Unipile Connect.

Cliquez sur ce lien pour réinitialiser votre mot de passe :
{reset_url}

IMPORTANT :
- Ce lien expire dans 30 minutes
- Il ne peut être utilisé qu'une seule fois  
- Si vous n'êtes pas à l'origine de cette demande, ignorez cet email

Cordialement,
L'équipe Unipile Connect

---
Cet email a été envoyé automatiquement, merci de ne pas y répondre.
        """
        
        # Create multipart message
        msg = MIMEMultipart('alternative')
        msg['Subject'] = "🔒 Réinitialisation de votre mot de passe - Unipile Connect"
        msg['From'] = smtp_from
        msg['To'] = email
        
        # Attach both text and HTML versions
        text_part = MIMEText(text_content, 'plain', 'utf-8')
        html_part = MIMEText(html_content, 'html', 'utf-8')
        
        msg.attach(text_part)
        msg.attach(html_part)
        
        # Send email
        if use_tls:
            context = ssl.create_default_context()
            with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as server:
                server.starttls(context=context)
                server.login(smtp_user, smtp_password)
                server.send_message(msg)
        else:
            with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as server:
                server.login(smtp_user, smtp_password)
                server.send_message(msg)
        
        logger.info(f"Password reset email sent successfully to {email}")
        return True
        
    except smtplib.SMTPAuthenticationError as e:
        logger.error(f"SMTP Authentication failed for {email}: {e}")
        return False
    except smtplib.SMTPRecipientsRefused as e:
        logger.error(f"SMTP Recipients refused for {email}: {e}")
        return False
    except smtplib.SMTPException as e:
        logger.error(f"SMTP error sending email to {email}: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error sending email to {email}: {e}")
        return False

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
    user = get_user_by_email(db, email)
    debug_reset_url = None
    
    # Debug logging
    print(f"[DEBUG] Looking for user with email: {email}")
    print(f"[DEBUG] User found: {user is not None}")
    
    if not user:
        print(f"[DEBUG] No user found with email: {email}")
        # Show clear error message when account doesn't exist
        return templates.TemplateResponse(
            "forgot_password.html",
            {
                "request": request,
                "error": f"❌ Aucun compte n'existe avec l'email '{email}'.",
                "error_suggestion": "Veuillez d'abord créer un compte avec cet email."
            }
        )
    
    print(f"[DEBUG] User details: ID={user.id}, Username={user.username}, Email={user.email}")
    
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

        # Send password reset email
        user_name = user.full_name or user.username
        email_sent = send_password_reset_email(email, reset_url, user_name)
        
        if email_sent:
            logger.info(f"Password reset email sent successfully to {email}")
            print(f"✅ SUCCESS: Password reset email sent to {email}")
        else:
            logger.warning(f"Failed to send password reset email to {email}. Reset URL: {reset_url}")
            print(f"❌ FAILED: Could not send email to {email}. Reset URL: {reset_url}")

        # Optionally expose the link on the page in development
        show_link_env = os.getenv("SHOW_RESET_LINK_ON_PAGE", "false")
        print(f"[DEBUG] SHOW_RESET_LINK_ON_PAGE env var: '{show_link_env}'")
        print(f"[DEBUG] Condition check: {show_link_env.lower() == 'true'}")
        if show_link_env.lower() == "true":
            debug_reset_url = reset_url
            print(f"[DEBUG] Setting debug_reset_url to: {debug_reset_url}")

    print(f"[DEBUG] Template context - debug_reset_url: {debug_reset_url}")
    success_message = f"Un lien de réinitialisation a été envoyé à {email}. Vérifiez votre boîte mail (et vos spams)."
    return templates.TemplateResponse(
        "forgot_password.html",
        {"request": request, "success": success_message, "debug_reset_url": debug_reset_url},
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

@router.post("/admin/test-smtp")
async def test_smtp_configuration(
    request: Request,
    test_email: str = Form(...),
    db: Session = Depends(get_db)
):
    """Test SMTP configuration by sending a test email (Admin only)"""
    user_session = get_current_user_session(request, db)
    if not user_session or not user_session.user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    # Validate email format
    import re
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(email_pattern, test_email):
        raise HTTPException(status_code=400, detail="Invalid email format")
    
    try:
        # Create a test reset URL (not functional, just for testing)
        test_reset_url = "https://example.com/test-reset-link"
        
        # Try to send test email
        success = send_password_reset_email(test_email, test_reset_url, "Test User")
        
        if success:
            return {
                "success": True,
                "message": f"Test email sent successfully to {test_email}",
                "smtp_status": "configured_and_working"
            }
        else:
            return {
                "success": False,
                "message": "Failed to send test email. Check SMTP configuration and logs.",
                "smtp_status": "configured_but_failing"
            }
    except Exception as e:
        logger.error(f"SMTP test failed: {e}")
        return {
            "success": False,
            "message": f"SMTP test failed: {str(e)}",
            "smtp_status": "error"
        }

@router.post("/debug/create-test-user")
async def debug_create_test_user(
    request: Request, 
    email: str = Form(...),
    username: str = Form(None),
    password: str = Form("password123"),
    db: Session = Depends(get_db)
):
    """Debug endpoint to quickly create a test user (no auth required for debugging)"""
    try:
        # Check if user already exists
        existing_user = get_user_by_email(db, email)
        if existing_user:
            return {"error": f"User with email {email} already exists", "user_id": existing_user.id}
        
        # Create username from email if not provided
        if not username:
            username = email.split('@')[0]
        
        # Check if username exists
        existing_username = get_user_by_username(db, username)
        if existing_username:
            username = f"{username}_{secrets.token_hex(4)}"
        
        # Create user
        user = create_user(
            db=db,
            username=username,
            email=email,
            password=password,
            full_name=f"Test User ({email})",
            is_admin=False
        )
        
        return {
            "success": True,
            "message": f"Test user created successfully",
            "user": {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "password": password
            }
        }
    except Exception as e:
        return {"error": str(e)}

@router.get("/debug/users")
async def debug_list_users(request: Request, db: Session = Depends(get_db)):
    """Debug endpoint to list all users (no auth required for debugging)"""
    try:
        users = db.query(User).all()
        return {
            "total_users": len(users),
            "users": [
                {
                    "id": user.id,
                    "username": user.username,
                    "email": user.email,
                    "full_name": user.full_name,
                    "is_active": user.is_active,
                    "created_at": str(user.created_at)
                }
                for user in users
            ]
        }
    except Exception as e:
        return {"error": str(e)}

@router.get("/debug/test-email")
async def debug_test_email(request: Request, email: str = None):
    """Simple debug endpoint to test email sending (no auth required for debugging)"""
    if not email:
        return {"error": "Please provide email parameter: /users/debug/test-email?email=your@email.com"}
    
    try:
        test_reset_url = "http://localhost:8000/debug/test-reset-link"
        success = send_password_reset_email(email, test_reset_url, "Debug User")
        
        return {
            "success": success,
            "message": f"Test email {'sent successfully' if success else 'failed'} to {email}",
            "smtp_config": {
                "host": os.getenv("SMTP_HOST"),
                "port": os.getenv("SMTP_PORT", "587"),
                "user": os.getenv("SMTP_USER"),
                "password_set": bool(os.getenv("SMTP_PASSWORD")),
                "from": os.getenv("SMTP_FROM"),
                "tls": os.getenv("SMTP_USE_TLS", "true")
            }
        }
    except Exception as e:
        return {"error": str(e), "success": False}

@router.get("/admin/smtp-status")
async def get_smtp_status(request: Request, db: Session = Depends(get_db)):
    """Get SMTP configuration status (Admin only)"""
    user_session = get_current_user_session(request, db)
    if not user_session or not user_session.user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    smtp_host = os.getenv("SMTP_HOST")
    smtp_port = os.getenv("SMTP_PORT", "587")
    smtp_user = os.getenv("SMTP_USER")
    smtp_password = os.getenv("SMTP_PASSWORD")
    smtp_from = os.getenv("SMTP_FROM")
    use_tls = os.getenv("SMTP_USE_TLS", "true")
    
    config_status = {
        "smtp_host": "✅ Configured" if smtp_host else "❌ Missing",
        "smtp_port": f"✅ {smtp_port}" if smtp_port else "❌ Missing",
        "smtp_user": "✅ Configured" if smtp_user else "❌ Missing",
        "smtp_password": "✅ Configured" if smtp_password else "❌ Missing",
        "smtp_from": f"✅ {smtp_from}" if smtp_from else f"⚠️ Using default ({smtp_user})",
        "smtp_use_tls": f"✅ {use_tls}" if use_tls else "⚠️ Default (true)"
    }
    
    is_fully_configured = all([smtp_host, smtp_user, smtp_password])
    
    return {
        "is_configured": is_fully_configured,
        "configuration": config_status,
        "status": "ready" if is_fully_configured else "incomplete",
        "message": "SMTP is fully configured and ready to use" if is_fully_configured else "SMTP configuration is incomplete. Check missing fields."
    }
