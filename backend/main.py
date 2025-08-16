from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from azure.storage.blob import BlobServiceClient, BlobClient
import pandas as pd
import io
import os

app = FastAPI()

# Serve frontend
app.mount("/static", StaticFiles(directory="frontend"), name="static")

@app.get("/", response_class=FileResponse)
async def root():
    return FileResponse("frontend/login.html")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Replace with your actual frontend domain for security
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ENV vars for blob
BLOB_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
CONTAINER_NAME = os.getenv["registration-data"]

# Read blob as DataFrame
def read_csv_blob(blob_name: str) -> pd.DataFrame:
    blob_service_client = BlobServiceClient.from_connection_string(BLOB_CONNECTION_STRING)
    blob_client = blob_service_client.get_container_client(CONTAINER_NAME).get_blob_client(blob_name)
    stream = blob_client.download_blob()
    return pd.read_csv(io.BytesIO(stream.readall()))

# Append row to blob CSV
def append_to_csv_blob(blob_name: str, new_row: dict):
    df = pd.DataFrame([new_row])

    try:
        existing_df = read_csv_blob(blob_name)
        combined_df = pd.concat([existing_df, df], ignore_index=True)
    except:
        combined_df = df  # File might not exist yet

    # Save back to blob
    blob_service_client = BlobServiceClient.from_connection_string(BLOB_CONNECTION_STRING)
    blob_client = blob_service_client.get_container_client(CONTAINER_NAME).get_blob_client(blob_name)
    output = io.StringIO()
    combined_df.to_csv(output, index=False)
    blob_client.upload_blob(output.getvalue(), overwrite=True)

# LOGIN
@app.post("/login")
async def login(username: str = Form(...), password: str = Form(...)):
    expected_user = os.getenv("LOGIN_USERNAME", "fs2025")
    expected_pass = os.getenv("LOGIN_PASSWORD", "icbfs1095")
    if username == expected_user and password == expected_pass:
        return JSONResponse({"success": True})
    return JSONResponse({"success": False}, status_code=401)

# SEARCH Registered Guests
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
            customer_code.lower() in str(row.get("customer_code", "")).lower() or
            attendee_name.lower() in str(row.get("attendee_name", "")).lower() or
            customer_name.lower() in str(row.get("customer_name", "")).lower() or
            registration_id.lower() in str(row.get("registration_id", "")).lower(),
        axis=1)
    ]
    return match.to_dict(orient="records")

# MARK attendance (registered guests)
@app.post("/mark_attendance")
async def mark_attendance(data: dict):
    append_to_csv_blob("attendance_log.csv", data)
    append_to_csv_blob("booth_print_queue.csv", data)
    return {"status": "Attendance Logged"}

# REGISTER walk-in guest
@app.post("/walkin")
async def register_walkin(data: dict):
    append_to_csv_blob("walkins.csv", data)
    append_to_csv_blob("booth_print_queue.csv", data)
    return {"status": "Walk-in Registered"}

# GET booth queue
@app.get("/booth_queue")
async def booth_queue():
    try:
        df = read_csv_blob("booth_print_queue.csv")
        return df.to_dict(orient="records")
    except:
        return []
