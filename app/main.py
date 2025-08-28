# app/main.py
import os
import mimetypes
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Any, Optional

import requests
from dotenv import load_dotenv
from fastapi import FastAPI, Request, HTTPException, Body, Depends, Form, Response
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

# ---------- Fix MIME (certaines images slim ne mappent pas .css/.js correctement)
mimetypes.add_type("text/css", ".css")
mimetypes.add_type("application/javascript", ".js")

# ---------- Env
load_dotenv()

# ---------- App
app = FastAPI()

# ---------- Chemins robustes (absolus)
BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
TEMPLATES_DIR = BASE_DIR / "templates"

# Static & templates (montage unique)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
# Also mount CSS directly for compatibility
app.mount("/css", StaticFiles(directory=str(STATIC_DIR / "css")), name="css")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# ---------- Config Unipile / App
UNIPILE_API_BASE = os.getenv("UNIPILE_API_BASE", "").rstrip("/")  # ex: https://api8.unipile.com:13816/api/v1
UNIPILE_API_HOST = os.getenv("UNIPILE_API_HOST", "").rstrip("/")  # ex: https://api8.unipile.com:13816 (SANS /api/v1)
UNIPILE_API_KEY = os.getenv("UNIPILE_API_KEY", "")
APP_BASE_URL = os.getenv("APP_BASE_URL", "http://127.0.0.1:8000").rstrip("/")

# ---------- Config
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-this")

SUCCESS_URL = f"{APP_BASE_URL}/connect/success"
FAILURE_URL = f"{APP_BASE_URL}/connect/failure"
NOTIFY_URL  = f"{APP_BASE_URL}/unipile/notify"

# Import database and auth first
from .database import get_db, ConnectedAccount, User, create_tables
from .auth import get_current_user_session, create_session, delete_session

# Now import and include user routes after dependencies are loaded
from .users import router as users_router
app.include_router(users_router, prefix="/users", tags=["users"])

# Debug: Print all routes to verify inclusion
@app.on_event("startup")
async def startup_event():
    print("🚀 Application starting up...")
    # Ensure database tables exist (idempotent)
    try:
        create_tables()
        print("✅ Database tables ensured")
    except Exception as e:
        print(f"❌ Failed to ensure database tables: {e}")
    print("📋 Available routes:")
    for route in app.routes:
        if hasattr(route, 'path') and hasattr(route, 'methods'):
            print(f"  {route.methods} {route.path}")
        elif hasattr(route, 'path'):
            print(f"  MOUNT {route.path}")

# ---------- Account Management
def disconnect_account(account_id: str, db: Session) -> bool:
    """Disconnect an account and remove it from storage"""
    account = db.query(ConnectedAccount).filter(ConnectedAccount.account_id == account_id).first()
    if account:
        db.delete(account)
        db.commit()
        return True
    return False

def iso8601_millis(dt: datetime) -> str:
    """YYYY-MM-DDTHH:MM:SS.sssZ (UTC, millisecondes)."""
    dt = dt.astimezone(timezone.utc)
    ms = int(dt.microsecond / 1000)
    return dt.strftime(f"%Y-%m-%dT%H:MM:%S.{ms:03d}Z")

# ---------- Pages
@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login")
async def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    from .auth import authenticate_user, create_session
    
    user = authenticate_user(db, username, password)
    if user:
        session_id = create_session(db, user.id)
        response = RedirectResponse(url="/dashboard", status_code=303)
        response.set_cookie(
            key="session_id",
            value=session_id,
            httponly=True,
            max_age=24 * 60 * 60,  # 24 hours
            secure=False,  # Set to True in production with HTTPS
            samesite="lax"
        )
        return response
    else:
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": "Nom d'utilisateur ou mot de passe incorrect"
        })

@app.get("/logout")
async def logout(request: Request, db: Session = Depends(get_db)):
    session_id = request.cookies.get("session_id")
    if session_id:
        delete_session(db, session_id)
    
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie("session_id")
    return response

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(request: Request, db: Session = Depends(get_db)):
    user_session = get_current_user_session(request, db)
    if not user_session:
        return RedirectResponse(url="/login", status_code=303)
    
    # Get user's connected accounts
    connected_accounts = db.query(ConnectedAccount).filter(
        ConnectedAccount.user_id == user_session.user_id
    ).all()
    
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "user": user_session.user,
        "connected_accounts": connected_accounts
    })

@app.post("/disconnect/{account_id}")
async def disconnect_account_route(
    account_id: str,
    request: Request,
    db: Session = Depends(get_db)
):
    user_session = get_current_user_session(request, db)
    if not user_session:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    success = disconnect_account(account_id, db)
    if success:
        return {"message": "Account disconnected successfully"}
    else:
        raise HTTPException(status_code=404, detail="Account not found")

@app.get("/api/accounts")
async def get_user_accounts(request: Request, db: Session = Depends(get_db)):
    user_session = get_current_user_session(request, db)
    if not user_session:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    connected_accounts = db.query(ConnectedAccount).filter(
        ConnectedAccount.user_id == user_session.user_id
    ).all()
    
    return [
        {
            "id": account.id,
            "account_id": account.account_id,
            "provider": account.provider,
            "status": account.status,
            "connected_at": account.connected_at,
            "last_sync": account.last_sync
        }
        for account in connected_accounts
    ]

@app.get("/connect/linkedin")
async def connect_linkedin(request: Request, db: Session = Depends(get_db)):
    user_session = get_current_user_session(request, db)
    if not user_session:
        return RedirectResponse(url="/login", status_code=303)
    
    # Redirect to Unipile LinkedIn connection
    unipile_url = f"{UNIPILE_API_HOST}/auth/linkedin"
    params = {
        "client_id": UNIPILE_API_KEY,
        "redirect_uri": SUCCESS_URL,
        "state": user_session.user_id,  # Pass user ID in state
        "scope": "r_liteprofile r_emailaddress w_member_social"
    }
    
    # Build query string
    query_string = "&".join([f"{k}={v}" for k, v in params.items()])
    full_url = f"{unipile_url}?{query_string}"
    
    return RedirectResponse(url=full_url, status_code=302)

@app.get("/connect/success")
async def connect_success(
    request: Request,
    code: str = None,
    state: str = None,
    error: str = None,
    db: Session = Depends(get_db)
):
    if error:
        return RedirectResponse(url=f"{FAILURE_URL}?error={error}", status_code=302)
    
    if not code or not state:
        return RedirectResponse(url=f"{FAILURE_URL}?error=missing_parameters", status_code=302)
    
    try:
        # Exchange code for access token
        token_url = f"{UNIPILE_API_BASE}/auth/access_token"
        token_data = {
            "grant_type": "authorization_code",
            "client_id": UNIPILE_API_KEY,
            "code": code,
            "redirect_uri": SUCCESS_URL
        }
        
        token_response = requests.post(token_url, data=token_data)
        token_response.raise_for_status()
        token_info = token_response.json()
        
        # Get user profile
        profile_url = f"{UNIPILE_API_BASE}/me"
        headers = {"Authorization": f"Bearer {token_info['access_token']}"}
        profile_response = requests.get(profile_url, headers=headers)
        profile_response.raise_for_status()
        profile_info = profile_response.json()
        
        # Store connected account
        user_id = int(state)
        account = ConnectedAccount(
            account_id=profile_info.get("id", ""),
            user_id=user_id,
            provider="LINKEDIN",
            status="CREATION_SUCCESS",
            account_data=str(profile_info),
            last_sync=datetime.now(timezone.utc)
        )
        
        db.add(account)
        db.commit()
        
        return templates.TemplateResponse("success.html", {
            "request": request,
            "provider": "LinkedIn",
            "account_info": profile_info
        })
        
    except requests.RequestException as e:
        return RedirectResponse(url=f"{FAILURE_URL}?error=api_error", status_code=302)
    except Exception as e:
        return RedirectResponse(url=f"{FAILURE_URL}?error=unknown_error", status_code=302)

@app.get("/connect/failure")
async def connect_failure(request: Request, error: str = None):
    return templates.TemplateResponse("failure.html", {
        "request": request,
        "error": error or "Unknown error occurred"
    })

@app.post("/unipile/notify")
async def unipile_notify(
    request: Request,
    body: Dict[str, Any] = Body(...),
    db: Session = Depends(get_db)
):
    """Handle Unipile webhook notifications"""
    try:
        # Extract notification data
        notification_type = body.get("type")
        account_id = body.get("account_id")
        status = body.get("status")
        details = body.get("details", {})
        
        if notification_type == "account_status_changed" and account_id:
            # Update or create connected account
            existing_account = db.query(ConnectedAccount).filter(
                ConnectedAccount.account_id == account_id
            ).first()
            
            if existing_account:
                # Update existing account
                existing_account.status = status
                existing_account.account_data = str(details)
                existing_account.last_sync = datetime.now(timezone.utc)
            else:
                # Create new account (if we have user info)
                # For now, we'll create a placeholder
                pass
            
            db.commit()
        
        return {"status": "success"}
        
    except Exception as e:
        return {"status": "error", "message": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
