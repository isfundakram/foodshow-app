# backend/main.py
from fastapi import FastAPI, HTTPException, Depends
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from azure.storage.blob import BlobServiceClient
import pandas as pd
from io import StringIO
import os

from fastapi.security import HTTPBasic, HTTPBasicCredentials
import secrets as pysecrets  # for constant-time compare

app = FastAPI()
app.mount("/static", StaticFiles(directory="frontend"), name="static")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- config
AZURE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING", "")
CONTAINER_NAME = os.getenv("REG_CONTAINER", "registration-data")
REGISTERED_BLOB = os.getenv("REGISTERED_BLOB", "registered.csv")

ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "staff")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "changeme")

security = HTTPBasic()

def require_basic_auth(creds: HTTPBasicCredentials = Depends(security)):
    u_ok = pysecrets.compare_digest(creds.username, ADMIN_USERNAME)
    p_ok = pysecrets.compare_digest(creds.password, ADMIN_PASSWORD)
    if not (u_ok and p_ok):
        # FastAPI will return 401 with WWW-Authenticate header automatically
        raise HTTPException(status_code=401, detail="Unauthorized")
    return creds.username

def read_registered_df() -> pd.DataFrame:
    if not AZURE_CONNECTION_STRING:
        raise HTTPException(status_code=500, detail="Missing AZURE_STORAGE_CONNECTION_STRING")
    bsc = BlobServiceClient.from_connection_string(AZURE_CONNECTION_STRING)
    blob = bsc.get_container_client(CONTAINER_NAME).get_blob_client(REGISTERED_BLOB)
    content = blob.download_blob().readall().decode("utf-8", errors="ignore")
    df = pd.read_csv(StringIO(content), dtype=str).fillna("")
    df.columns = [c.strip().lower() for c in df.columns]
    return df

@app.get("/api/registered/list")
def registered_list(
    customer_code: str = "",
    customer_name: str = "",
    attendee_name: str = "",
    registration_id: str = "",
    _: str = Depends(require_basic_auth),  # protect this endpoint
):
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
    out = df.loc[mask, ["customer_code","customer_name","attendee_name","registration_id"]].to_dict(orient="records")
    return {"count": len(out), "rows": out}

@app.get("/")
def root():
    path = os.path.join("frontend", "index.html")
    return FileResponse(path) if os.path.exists(path) else JSONResponse({"ok": True})
