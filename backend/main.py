from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from azure.storage.blob import BlobServiceClient, BlobClient
import pandas as pd
import os
import io

app = FastAPI()

# Serve frontend
app.mount("/static", StaticFiles(directory="frontend"), name="static")

@app.get("/", response_class=FileResponse)
async def root():
    return FileResponse("frontend/login.html")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ENV Variables
ACCOUNT_NAME = os.getenv("AZURE_STORAGE_ACCOUNT_NAME")
ACCOUNT_KEY = os.getenv("AZURE_STORAGE_ACCOUNT_KEY")
CONTAINER_NAME = os.getenv("AZURE_CONTAINER_NAME", "csvdata")

# Blob Client
blob_service = BlobServiceClient(
    f"https://{ACCOUNT_NAME}.blob.core.windows.net",
    credential=ACCOUNT_KEY
)

def download_csv(blob_name: str) -> pd.DataFrame:
    try:
        blob_client = blob_service.get_blob_client(CONTAINER_NAME, blob_name)
        stream = blob_client.download_blob().readall()
        return pd.read_csv(io.BytesIO(stream), encoding="ISO-8859-1")
    except:
        return pd.DataFrame()

def append_csv(blob_name: str, new_data: dict):
    df_new = pd.DataFrame([new_data])
    blob_client = blob_service.get_blob_client(CONTAINER_NAME, blob_name)

    try:
        existing_df = download_csv(blob_name)
        df_combined = pd.concat([existing_df, df_new], ignore_index=True)
    except:
        df_combined = df_new

    buffer = io.StringIO()
    df_combined.to_csv(buffer, index=False)
    blob_client.upload_blob(buffer.getvalue(), overwrite=True)

# Login
@app.post("/login")
async def login(username: str = Form(...), password: str = Form(...)):
    expected_user = os.getenv("LOGIN_USERNAME", "fs2025")
    expected_pass = os.getenv("LOGIN_PASSWORD", "icbfs1095")
    if username == expected_user and password == expected_pass:
        return JSONResponse({"success": True})
    return JSONResponse({"success": False}, status_code=401)

# Search
@app.post("/search")
async def search(account: str = Form(""), first: str = Form(""), last: str = Form(""),
                 company: str = Form(""), regname: str = Form("")):
    df = download_csv("registered.csv")
    match = df[
        df.apply(lambda row:
            account.lower() in str(row.get("Customer Code", "")).lower() or
            first.lower() in str(row.get("Attendee Name", "")).split()[0].lower() or
            last.lower() in str(row.get("Attendee Name", "")).split()[-1].lower() or
            company.lower() in str(row.get("Customer Name", "")).lower() or
            regname.lower() in str(row.get("Attendee Name", "")).lower(), axis=1)
    ]
    return match.to_dict(orient="records")

# Attendance log
@app.post("/mark_attendance")
async def mark_attendance(data: dict):
    append_csv("attendance_log.csv", data)
    return {"status": "Logged"}

# Walk-in form
@app.post("/walkin")
async def register_walkin(data: dict):
    append_csv("walkins.csv", data)
    return {"status": "Walk-in Registered"}
