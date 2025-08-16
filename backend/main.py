# backend/main.py
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from azure.storage.blob import BlobServiceClient
import pandas as pd
from io import StringIO
import os, time, hmac, hashlib, base64, json, secrets

app = FastAPI()

# --- Static frontend
app.mount("/static", StaticFiles(directory="frontend"), name="static")

# --- CORS (safe defaults; same-origin will also work)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Config (set these in Azure App Settings)
AZURE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING", "")
CONTAINER_NAME = os.getenv("REG_CONTAINER", "registration-data")
REGISTERED_BLOB = os.getenv("REGISTERED_BLOB", "registered.csv")

ADMIN_USERNAME = os.getenv["ADMIN_USERNAME"]
ADMIN_PASSWORD = os.getenv["ADMIN_PASSWORD"]
SESSION_SECRET = os.getenv("SESSION_SECRET", secrets.token_hex(16))
SESSION_COOKIE = "session"
SESSION_TTL_SECONDS = 3 * 24 * 60 * 60  # 3 days

# --- Helpers: signed cookie (HMAC-SHA256)
def _sign(payload: dict) -> str:
    data = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    sig = hmac.new(SESSION_SECRET.encode(), data, hashlib.sha256).digest()
    token = base64.urlsafe_b64encode(data + b"." + sig).decode()
    return token

def _verify(token: str) -> dict:
    try:
        blob = base64.urlsafe_b64decode(token.encode())
        data, sig = blob.rsplit(b".", 1)
        exp_sig = hmac.new(SESSION_SECRET.encode(), data, hashlib.sha256).digest()
        if not hmac.compare_digest(sig, exp_sig):
            raise ValueError("bad signature")
        payload = json.loads(data.decode())
        if payload.get("exp", 0) < int(time.time()):
            raise ValueError("expired")
        return payload
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid session")

def _require_auth(request: Request) -> str:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    payload = _verify(token)
    return payload.get("u", "")

# --- Azure Blob CSV reader
def read_registered_df() -> pd.DataFrame:
    if not AZURE_CONNECTION_STRING:
        raise HTTPException(status_code=500, detail="Missing AZURE_STORAGE_CONNECTION_STRING")
    bsc = BlobServiceClient.from_connection_string(AZURE_CONNECTION_STRING)
    blob = bsc.get_container_client(CONTAINER_NAME).get_blob_client(REGISTERED_BLOB)
    content = blob.download_blob().readall().decode("utf-8", errors="ignore")
    df = pd.read_csv(StringIO(content), dtype=str).fillna("")
    # Expected headers
    expected = {"customer_code", "customer_name", "attendee_name", "registration_id"}
    missing = expected - set(map(str.lower, df.columns))
    # Try to normalize casing if needed
    df.columns = [c.strip().lower() for c in df.columns]
    if missing - set(map(str.lower, df.columns)):
        pass  # don't hard-fail; just return whatever is there
    return df

# --- Auth endpoints
@app.post("/api/login")
async def login(body: dict):
    username = (body.get("username") or "").strip()
    password = (body.get("password") or "").strip()
    if username != ADMIN_USERNAME or password != ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    payload = {"u": username, "exp": int(time.time()) + SESSION_TTL_SECONDS}
    token = _sign(payload)
    resp = JSONResponse({"ok": True})
    resp.set_cookie(
        key=SESSION_COOKIE,
        value=token,
        httponly=True,
        samesite="lax",
        secure=True,  # keep True in Azure over HTTPS
        max_age=SESSION_TTL_SECONDS,
        path="/",
    )
    return resp

@app.post("/api/logout")
async def logout():
    resp = JSONResponse({"ok": True})
    resp.delete_cookie(SESSION_COOKIE, path="/")
    return resp

@app.get("/api/auth/me")
async def me(request: Request):
    user = _require_auth(request)
    return {"user": user}

# --- Registered list endpoint (protected)
@app.get("/api/registered/list")
async def registered_list(
    request: Request,
    customer_code: str = "",
    customer_name: str = "",
    attendee_name: str = "",
    registration_id: str = "",
):
    _require_auth(request)
    df = read_registered_df()

    def contains(col: str, val: str):
        v = (val or "").strip()
        if not v or col not in df.columns:
            return pd.Series([True] * len(df))
        return df[col].str.contains(v, case=False, na=False)

    mask = (
        contains("customer_code", customer_code)
        & contains("customer_name", customer_name)
        & contains("attendee_name", attendee_name)
        & contains("registration_id", registration_id)
    )
    out = df.loc[mask, ["customer_code", "customer_name", "attendee_name", "registration_id"]].to_dict_
