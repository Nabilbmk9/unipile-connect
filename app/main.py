# app/main.py
import os
import mimetypes
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from typing import Dict, Any, Optional

import requests
from dotenv import load_dotenv
from urllib.parse import urlencode
from fastapi import FastAPI, Request, HTTPException, Body, Depends, Form, Response
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

# ---------- Fix MIME (certaines images slim ne mappent pas .css/.js correctement)
mimetypes.add_type("text/css", ".css")
mimetypes.add_type("application/javascript", ".js")

# ---------- Env
load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")

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
UNIPILE_API_BASE = os.getenv("UNIPILE_API_BASE", "").strip().rstrip("/")  # ex: https://api8.unipile.com:13816/api/v1
UNIPILE_API_HOST = os.getenv("UNIPILE_API_HOST", "").strip().rstrip("/")  # ex: https://api8.unipile.com:13816 (SANS /api/v1)
UNIPILE_API_KEY = os.getenv("UNIPILE_API_KEY", "")
_raw_app_base = os.getenv("APP_BASE_URL", "http://127.0.0.1:8000").strip()
if not _raw_app_base.startswith("http"):
    _raw_app_base = "https://" + _raw_app_base
APP_BASE_URL = _raw_app_base.rstrip("/")

# ---------- Config
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-this")

# ---------- SMTP Configuration
SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM = os.getenv("SMTP_FROM", os.getenv("SMTP_USER", "no-reply@example.com"))
SMTP_USE_TLS = os.getenv("SMTP_USE_TLS", "true").lower() == "true"

SUCCESS_URL = f"{APP_BASE_URL}/connect/success"
FAILURE_URL = f"{APP_BASE_URL}/connect/failure"
NOTIFY_URL  = f"{APP_BASE_URL}/unipile/notify"

# ---------- V1: stockage en mémoire pour debug/visualisation
CONNECTED_ACCOUNTS: Dict[str, Dict[str, Any]] = {}

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
    # Log key configuration (sanitized)
    try:
        print("🔧 Config:")
        print(f"  APP_BASE_URL = {APP_BASE_URL}")
        print(f"  UNIPILE_API_HOST = {UNIPILE_API_HOST}")
        print(f"  UNIPILE_API_BASE = {UNIPILE_API_BASE}")
        print(f"  UNIPILE_API_KEY set: {'yes' if bool(UNIPILE_API_KEY) else 'no'}")
        print(f"  SMTP_HOST = {SMTP_HOST}")
        print(f"  SMTP_PORT = {SMTP_PORT}")
        print(f"  SMTP_USER = {SMTP_USER}")
        print(f"  SMTP_PASSWORD set: {'yes' if bool(SMTP_PASSWORD) else 'no'}")
        print(f"  SMTP_FROM = {SMTP_FROM}")
        print(f"  SMTP_USE_TLS = {SMTP_USE_TLS}")
    except Exception as e:
        print(f"⚠️ Could not print config: {e}")
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
    return dt.strftime(f"%Y-%m-%dT%H:%M:%S.{ms:03d}Z")

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

    # Build dict of connected accounts keyed by account_id from DB + memory
    db_accounts = db.query(ConnectedAccount).filter(
        ConnectedAccount.user_id == user_session.user_id
    ).all()

    accounts_dict: Dict[str, Dict[str, Any]] = {}
    # Start with in-memory (from webhook) for immediate feedback
    accounts_dict.update(CONNECTED_ACCOUNTS)

    for acc in db_accounts:
        # Preserve any in-memory status if already present
        if acc.account_id not in accounts_dict:
            try:
                raw_obj = json.loads(acc.account_data) if acc.account_data else None
            except Exception:
                raw_obj = acc.account_data
            accounts_dict[acc.account_id] = {
                "status": acc.status,
                "user": str(user_session.user_id),
                "raw": raw_obj,
            }

    display_name = (
        (user_session.user.full_name if getattr(user_session.user, "full_name", None) else None)
        or getattr(user_session.user, "username", None)
        or f"User {user_session.user_id}"
    )

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "current_user": display_name,
            "connected_accounts": accounts_dict,
        },
    )

@app.post("/disconnect/{account_id}")
async def disconnect_account_route(
    account_id: str,
    request: Request,
    db: Session = Depends(get_db)
):
    user_session = get_current_user_session(request, db)
    if not user_session:
        return JSONResponse(status_code=401, content={"success": False, "error": "Not authenticated"})

    success = disconnect_account(account_id, db)
    if success:
        # Also remove from in-memory cache if present
        if account_id in CONNECTED_ACCOUNTS:
            CONNECTED_ACCOUNTS.pop(account_id, None)
        return {"success": True}
    else:
        return JSONResponse(status_code=404, content={"success": False, "error": "Account not found"})

@app.get("/api/accounts")
async def get_user_accounts(request: Request, db: Session = Depends(get_db)):
    user_session = get_current_user_session(request, db)
    if not user_session:
        return JSONResponse(status_code=401, content={"success": False, "error": "Not authenticated"})

    db_accounts = db.query(ConnectedAccount).filter(
        ConnectedAccount.user_id == user_session.user_id
    ).all()

    accounts_dict: Dict[str, Dict[str, Any]] = {}
    accounts_dict.update(CONNECTED_ACCOUNTS)

    for acc in db_accounts:
        if acc.account_id not in accounts_dict:
            try:
                raw_obj = json.loads(acc.account_data) if acc.account_data else None
            except Exception:
                raw_obj = acc.account_data
            accounts_dict[acc.account_id] = {
                "status": acc.status,
                "user": str(user_session.user_id),
                "raw": raw_obj,
            }

    return {"success": True, "accounts": accounts_dict}

@app.get("/connect/linkedin")
async def connect_linkedin(request: Request, db: Session = Depends(get_db)):
    user_session = get_current_user_session(request, db)
    if not user_session:
        return RedirectResponse(url="/login", status_code=303)

    # Validation de config
    if not (UNIPILE_API_BASE and UNIPILE_API_HOST and UNIPILE_API_KEY):
        raise HTTPException(
            status_code=500,
            detail="Config manquante: UNIPILE_API_BASE, UNIPILE_API_HOST ou UNIPILE_API_KEY.",
        )

    # Lien valable 15 minutes (Unipile conseille de régénérer à chaque clic)
    expires_on = iso8601_millis(datetime.now(timezone.utc) + timedelta(minutes=15))

    payload = {
        "type": "create",
        "providers": ["LINKEDIN"],
        "api_url": UNIPILE_API_HOST,  # SANS /api/v1
        "expiresOn": expires_on,
        "success_redirect_url": SUCCESS_URL,
        "failure_redirect_url": FAILURE_URL,
        "notify_url": NOTIFY_URL,
        "name": str(user_session.user_id),  # associer l'utilisateur courant
    }

    try:
        resp = requests.post(
            f"{UNIPILE_API_BASE}/hosted/accounts/link",
            headers={
                "X-API-KEY": UNIPILE_API_KEY,
                "accept": "application/json",
                "content-type": "application/json",
            },
            json=payload,
            timeout=30,
        )
    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=f"Erreur réseau Unipile: {e}")

    if resp.status_code >= 400:
        raise HTTPException(status_code=502, detail=f"Unipile error: {resp.text}")

    url = resp.json().get("url")
    if not url:
        raise HTTPException(status_code=502, detail=f"Réponse Unipile invalide: {resp.text}")

    return RedirectResponse(url, status_code=302)

@app.get("/connect/success")
async def connect_success(
    request: Request,
    code: str = None,
    state: str = None,
    error: str = None,
    db: Session = Depends(get_db)
):
    if error:
        return templates.TemplateResponse("failure.html", {"request": request, "error": error})

    # Hosted flow (no code/state expected): just show summary page
    if not code and not state:
        return templates.TemplateResponse(
            "success.html",
            {"request": request, "accounts": CONNECTED_ACCOUNTS},
        )

    # Fallback: if code/state present from an OAuth-like flow, keep legacy behavior
    try:
        token_url = f"{UNIPILE_API_BASE}/auth/access_token"
        token_data = {
            "grant_type": "authorization_code",
            "client_id": UNIPILE_API_KEY,
            "code": code,
            "redirect_uri": SUCCESS_URL,
        }
        token_response = requests.post(token_url, data=token_data, timeout=20)
        token_response.raise_for_status()
        token_info = token_response.json()

        profile_url = f"{UNIPILE_API_BASE}/me"
        headers = {"Authorization": f"Bearer {token_info['access_token']}"}
        profile_response = requests.get(profile_url, headers=headers, timeout=20)
        profile_response.raise_for_status()
        profile_info = profile_response.json()

        user_id = int(state) if state and state.isdigit() else None
        if user_id is not None:
            account = ConnectedAccount(
                account_id=profile_info.get("id", ""),
                user_id=user_id,
                provider="LINKEDIN",
                status="CREATION_SUCCESS",
                account_data=str(profile_info),
                last_sync=datetime.now(timezone.utc),
            )
            db.add(account)
            db.commit()

        return templates.TemplateResponse(
            "success.html",
            {"request": request, "provider": "LinkedIn", "account_info": profile_info},
        )

    except requests.RequestException:
        return templates.TemplateResponse("failure.html", {"request": request, "error": "api_error"})
    except Exception:
        return templates.TemplateResponse("failure.html", {"request": request, "error": "unknown_error"})

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
    """Handle Unipile webhook notifications (Hosted Auth)."""
    try:
        status = body.get("status")
        account_id = body.get("account_id") or body.get("accountId")
        user_ref = body.get("name")  # we set this to current user id in /connect/linkedin

        # V1: stock en mémoire pour visualiser sur /connect/success
        key = account_id or f"evt:{len(CONNECTED_ACCOUNTS) + 1}"
        CONNECTED_ACCOUNTS[key] = {"status": status, "user": user_ref, "raw": body}

        # Persist to DB when possible
        if account_id:
            existing = db.query(ConnectedAccount).filter(ConnectedAccount.account_id == account_id).first()
            if existing:
                existing.status = status or existing.status
                existing.account_data = str(body)
                existing.last_sync = datetime.now(timezone.utc)
            else:
                # Try link to a user if the webhook provides one (we passed it in name)
                try:
                    user_id = int(user_ref) if user_ref is not None and str(user_ref).isdigit() else None
                except Exception:
                    user_id = None
                if user_id is not None:
                    new_acc = ConnectedAccount(
                        account_id=account_id,
                        user_id=user_id,
                        provider="LINKEDIN",
                        status=status or "CREATION_SUCCESS",
                        account_data=str(body),
                        last_sync=datetime.now(timezone.utc),
                    )
                    db.add(new_acc)
            db.commit()

        return {"ok": True}

    except Exception as e:
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
