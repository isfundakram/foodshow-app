from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from azure.storage.blob import BlobServiceClient
import pandas as pd
import os
from io import StringIO, BytesIO
import uuid
import json

app = FastAPI()

# Serve static frontend
app.mount("/static", StaticFiles(directory="frontend"), name="static")

@app.get("/", response_class=FileResponse)
async def root():
    return FileResponse("frontend/login.html")

# CORS (adjust origins if needed)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Azure Blob Storage setup
connect_str = os.environ["AZURE_STORAGE_CONNECTION_STRING"]
blob_service_client = BlobServiceClient.from_connection_string(connect_str)
container_name = "foodshow"

def read_csv_from_blob(blob_name):
    try:
        blob_client = blob_service_client.get_blob_client(container=container_name, blob=blob_name)
        stream = blob_client.download_blob()
        df = pd.read_csv(BytesIO(stream.readall()), encoding="ISO-8859-1")
        return df
    except Exception as e:
        print(f"Error reading {blob_name}: {e}")
        return pd.DataFrame()

def append_to_blob_csv(blob_name, new_data: pd.DataFrame):
    try:
        df_existing = read_csv_from_blob(blob_name)
        df_combined = pd.concat([df_existing, new_data], ignore_index=True)
        blob_client = blob_service_client.get_blob_client(container=container_name, blob=blob_name)
        output = BytesIO()
        df_combined.to_csv(output, index=False)
        output.seek(0)
        blob_client.upload_blob(output, overwrite=True)
    except Exception as e:
        print(f"Error writing to {blob_name}: {e}")

# Login
@app.post("/login")
async def login(username: str = Form(...), password: str = Form(...)):
    expected_user = os.environ["LOGIN_USERNAME"]
    expected_pass = os.environ["LOGIN_PASSWORD"]
    if username == expected_user and password == expected_pass:
        return JSONResponse({"success": True})
    return JSONResponse({"success": False}, status_code=401)

# Search registered guests (partial match)
@app.post("/search")
async def search(
    account: str = Form(""),
    first: str = Form(""),
    last: str = Form(""),
    company: str = Form(""),
    regname: str = Form("")
):
    df = read_csv_from_blob("registered.csv")
    results = df[df.apply(lambda row:
        (account.lower() in str(row.get("Customer Code", "")).lower()) or
        (first.lower() in str(row.get("Attendee Name", "")).split()[0].lower()) or
        (last.lower() in str(row.get("Attendee Name", "")).split()[-1].lower()) or
        (company.lower() in str(row.get("Customer Name", "")).lower()) or
        (regname.lower() in str(row.get("Attendee Name", "")).lower()),
        axis=1
    )]
    return results.to_dict(orient="records")

# Mark attendance and add to booth queue
@app.post("/mark_attendance")
async def mark_attendance(data: dict):
    df = pd.DataFrame([data])
    append_to_blob_csv("attendance_log.csv", df)
    append_to_blob_csv("booth_queue.csv", df)
    return {"status": "Logged & Queued"}

# Register walk-in and add to booth queue
@app.post("/walkin")
async def register_walkin(data: dict):
    df = pd.DataFrame([data])
    append_to_blob_csv("walkins.csv", df)
    append_to_blob_csv("booth_queue.csv", df)
    return {"status": "Walk-in Registered & Queued"}

# Return booth queue
@app.get("/booth_queue")
async def get_booth_queue():
    df = read_csv_from_blob("booth_queue.csv")
    return df.to_dict(orient="records")
