# app/main.py
import os
from datetime import datetime, timedelta, timezone
from typing import Dict, Any
from pathlib import Path

import requests
from dotenv import load_dotenv
from fastapi import FastAPI, Request, HTTPException, Body
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# Charge les variables du .env (UNIPILE_API_BASE, UNIPILE_API_HOST, UNIPILE_API_KEY, APP_BASE_URL)
load_dotenv()

app = FastAPI()

# chemins robustes, indépendants du cwd
BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
TEMPLATES_DIR = BASE_DIR / "templates"

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# --- Fichiers statiques (CSS/JS) ---
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# --- Templates Jinja ---
templates = Jinja2Templates(directory="app/templates")

# --- Config ---
UNIPILE_API_BASE = os.getenv("UNIPILE_API_BASE", "").rstrip("/")  # ex: https://api8.unipile.com:11624/api/v1
UNIPILE_API_HOST = os.getenv("UNIPILE_API_HOST", "").rstrip("/")  # ex: https://api8.unipile.com:11624 (SANS /api/v1)
UNIPILE_API_KEY = os.getenv("UNIPILE_API_KEY", "")
APP_BASE_URL = os.getenv("APP_BASE_URL", "http://127.0.0.1:8000").rstrip("/")

SUCCESS_URL = f"{APP_BASE_URL}/connect/success"
FAILURE_URL = f"{APP_BASE_URL}/connect/failure"
NOTIFY_URL = f"{APP_BASE_URL}/unipile/notify"

# Stockage en mémoire pour la V1 (remplacer par une DB plus tard)
CONNECTED_ACCOUNTS: Dict[str, Dict[str, Any]] = {}


def iso8601_millis(dt: datetime) -> str:
    """Retourne une date au format YYYY-MM-DDTHH:MM:SS.sssZ (UTC, millisecondes)."""
    dt = dt.astimezone(timezone.utc)
    ms = int(dt.microsecond / 1000)
    return dt.strftime(f"%Y-%m-%dT%H:%M:%S.{ms:03d}Z")


# --- Pages ---
@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/connect/success", response_class=HTMLResponse)
def connect_success(request: Request):
    # Affiche ce qu'on a reçu via /unipile/notify (pour debug V1)
    return templates.TemplateResponse(
        "success.html",
        {"request": request, "accounts": CONNECTED_ACCOUNTS},
    )


@app.get("/connect/failure", response_class=HTMLResponse)
def connect_failure(request: Request):
    return templates.TemplateResponse("failure.html", {"request": request})


# --- Démarrer le Hosted Auth Wizard (LinkedIn) ---
@app.get("/connect/linkedin")
def connect_linkedin():
    """
    Crée un lien 'hosted auth' chez Unipile puis redirige l'utilisateur vers l'assistant.
    Obligatoire: type, providers, api_url, expiresOn.
    """
    if not (UNIPILE_API_BASE and UNIPILE_API_HOST and UNIPILE_API_KEY):
        raise HTTPException(
            status_code=500,
            detail="Config manquante: UNIPILE_API_BASE, UNIPILE_API_HOST ou UNIPILE_API_KEY.",
        )

    # Lien valable 15 minutes (Unipile conseille de régénérer à chaque clic)
    expires_on = iso8601_millis(datetime.now(timezone.utc) + timedelta(minutes=15))

    payload = {
        "type": "create",
        "providers": ["LINKEDIN"],        # ou "*" pour laisser choisir la plateforme
        "api_url": UNIPILE_API_HOST,      # SANS /api/v1
        "expiresOn": expires_on,          # ISO8601 UTC avec millisecondes et 'Z'
        "success_redirect_url": SUCCESS_URL,
        "failure_redirect_url": FAILURE_URL,
        "notify_url": NOTIFY_URL,
        # Facultatif: identifiant utilisateur interne (remplace par ton vrai user_id si tu as une session)
        "name": "anonymous-user",
        # Exemples d'options possibles:
        # "bypass_success_screen": True,
        # "disabled_options": ["proxy", "cookie_auth", "credentials_auth"],
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
        # remonter le message d'erreur Unipile pour debug
        raise HTTPException(status_code=502, detail=f"Unipile error: {resp.text}")

    url = resp.json().get("url")
    if not url:
        raise HTTPException(status_code=502, detail=f"Réponse Unipile invalide: {resp.text}")

    # Redirige vers l'assistant d'auth Unipile
    return RedirectResponse(url, status_code=302)


# --- Notify (appelé serveur->serveur par Unipile) ---
@app.post("/unipile/notify")
def unipile_notify(payload: Dict[str, Any] = Body(...)):
    """
    Exemple attendu (pouvant varier) :
    {
      "status": "CREATION_SUCCESS",
      "account_id": "abc123",
      "name": "anonymous-user",
      ...
    }
    """
    status = payload.get("status")
    account_id = payload.get("account_id") or payload.get("accountId")
    user_ref = payload.get("name")

    # En V1: on stocke en mémoire pour visualiser sur /connect/success
    key = account_id or f"evt:{len(CONNECTED_ACCOUNTS)+1}"
    CONNECTED_ACCOUNTS[key] = {"status": status, "user": user_ref, "raw": payload}

    return JSONResponse({"ok": True})
