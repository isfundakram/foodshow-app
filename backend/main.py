from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from azure.storage.blob import BlobServiceClient
import pandas as pd
from io import BytesIO
import os

app = FastAPI()

# Serve frontend
app.mount("/static", StaticFiles(directory="frontend"), name="static")

@app.get("/", response_class=FileResponse)
async def root():
    return FileResponse("frontend/login.html")

# CORS setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Azure Blob setup
AZURE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
CONTAINER_NAME = "registration-data"
blob_service_client = BlobServiceClient.from_connection_string(AZURE_CONNECTION_STRING)
container_client = blob_service_client.get_container_client(CONTAINER_NAME)

def read_csv_blob(blob_name):
    try:
        blob_client = container_client.get_blob_client(blob_name)
        download = blob_client.download_blob()
        return pd.read_csv(BytesIO(download.readall()))
    except Exception as e:
        print(f"Error reading {blob_name}:", e)
        return pd.DataFrame()

def append_to_csv_blob(blob_name, new_data: dict):
    df_new = pd.DataFrame([new_data])
    try:
        df_existing = read_csv_blob(blob_name)
        df_combined = pd.concat([df_existing, df_new], ignore_index=True)

        buffer = BytesIO()
        df_combined.to_csv(buffer, index=False)
        buffer.seek(0)

        blob_client = container_client.get_blob_client(blob_name)
        blob_client.upload_blob(buffer, overwrite=True)
    except Exception as e:
        print(f"Error writing to {blob_name}:", e)

# Login endpoint
@app.post("/login")
async def login(username: str = Form(...), password: str = Form(...)):
    expected_user = os.getenv["LOGIN_USERNAME"]
    expected_pass = os.getenv["LOGIN_PASSWORD"]
    if username == expected_user and password == expected_pass:
        return JSONResponse({"success": True})
    return JSONResponse({"success": False}, status_code=401)

# Search registered guests
@app.post("/search")
async def search(
    customer_code: str = Form(""),
    attendee_name: str = Form(""),
    customer_name: str = Form(""),
    registration_id: str = Form("")
):
    df = read_csv_blob("registered.csv")
    match = df[
        df.apply(lambda row:
        (customer_code.lower() in str(row.get("customer_code", "")).lower()) or
        (attendee_name.lower() in str(row.get("attendee_name", "")).lower()) or
        (customer_name.lower() in str(row.get("customer_name", "")).lower()) or
        (registration_id.lower() in str(row.get("registration_id", "")).lower()),
        axis=1
    )]
    return match.to_dict(orient="records")

# Mark registered as attended
@app.post("/mark_attendance")
async def mark_attendance(data: dict):
    append_to_csv_blob("attendance_log.csv", data)
    append_to_csv_blob("booth_queue.csv", {"name": data.get("Attendee Name", "")})
    return {"status": "Logged"}

# Handle walk-ins
@app.post("/walkin")
async def register_walkin(data: dict):
    append_to_csv_blob("walkins.csv", data)
    append_to_csv_blob("booth_queue.csv", {"name": data.get("Attendee Name", "")})
    return {"status": "Walk-in Registered"}

# Serve booth queue
@app.get("/queue")
async def booth_queue():
    df = read_csv_blob("booth_queue.csv")
    return df.to_dict(orient="records")
