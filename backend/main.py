from fastapi import FastAPI, Form, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from azure.storage.blob import BlobServiceClient
import pandas as pd
import os
import io

app = FastAPI()

app.mount("/static", StaticFiles(directory="frontend"), name="static")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# === Azure Blob Config ===
CONN_STR = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
CONTAINER = "foodshow-csv"
blob_service_client = BlobServiceClient.from_connection_string(CONN_STR)

def download_csv(blob_name):
    try:
        blob_client = blob_service_client.get_blob_client(container=CONTAINER, blob=blob_name)
        stream = io.BytesIO()
        blob_data = blob_client.download_blob()
        blob_data.readinto(stream)
        stream.seek(0)
        return pd.read_csv(stream, encoding="ISO-8859-1")
    except:
        return pd.DataFrame()

def upload_csv(df, blob_name):
    blob_client = blob_service_client.get_blob_client(container=CONTAINER, blob=blob_name)
    stream = io.BytesIO()
    df.to_csv(stream, index=False)
    stream.seek(0)
    blob_client.upload_blob(stream, overwrite=True)

@app.get("/", response_class=FileResponse)
async def root():
    return FileResponse("frontend/login.html")

@app.post("/login")
async def login(username: str = Form(...), password: str = Form(...)):
    expected_user = os.getenv("LOGIN_USERNAME", "fs2025")
    expected_pass = os.getenv("LOGIN_PASSWORD", "icbfs1095")
    if username == expected_user and password == expected_pass:
        return JSONResponse({"success": True})
    return JSONResponse({"success": False}, status_code=401)

@app.post("/search")
async def search(account: str = Form(""), first: str = Form(""), last: str = Form(""), company: str = Form(""), regname: str = Form("")):
    df = download_csv("registered.csv")
    match = df[
        df.apply(lambda row:
            account.lower() in str(row["Customer Code"]).lower() or
            first.lower() in str(row["Attendee Name"]).lower().split()[0] or
            last.lower() in str(row["Attendee Name"]).lower().split()[-1] or
            company.lower() in str(row["Customer Name"]).lower() or
            regname.lower() in str(row["Attendee Name"]).lower(), axis=1)
    ]
    return match.to_dict(orient="records")

@app.post("/mark_attendance")
async def mark_attendance(data: dict):
    df = download_csv("attendance_log.csv")
    df = pd.concat([df, pd.DataFrame([data])], ignore_index=True)
    upload_csv(df, "attendance_log.csv")

    # Also add to booth queue
    queue = download_csv("booth_queue.csv")
    queue = pd.concat([queue, pd.DataFrame([data])], ignore_index=True)
    upload_csv(queue, "booth_queue.csv")

    return {"status": "Logged and Queued"}

@app.post("/walkin")
async def register_walkin(data: dict):
    df = download_csv("walkins.csv")
    df = pd.concat([df, pd.DataFrame([data])], ignore_index=True)
    upload_csv(df, "walkins.csv")

    # Also add to booth queue
    queue = download_csv("booth_queue.csv")
    queue = pd.concat([queue, pd.DataFrame([data])], ignore_index=True)
    upload_csv(queue, "booth_queue.csv")

    return {"status": "Walk-in Registered and Queued"}

@app.get("/booth_queue")
async def get_booth_queue():
    queue = download_csv("booth_queue.csv")
    return queue.to_dict(orient="records")
