from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from azure.storage.blob import BlobServiceClient, BlobClient
import pandas as pd
import os
import io

app = FastAPI()

# Mount static HTML pages
app.mount("/static", StaticFiles(directory="frontend"), name="static")

@app.get("/", response_class=FileResponse)
async def root():
    return FileResponse("frontend/login.html")

# CORS (update allowed_origins for production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Azure Blob Config ---
STORAGE_ACCOUNT_NAME = os.getenv("STORAGE_ACCOUNT_NAME")
STORAGE_ACCOUNT_KEY = os.getenv("STORAGE_ACCOUNT_KEY")
CONTAINER_NAME = "registration-data"

BLOB_CONNECTION_STRING = (
    f"DefaultEndpointsProtocol=https;"
    f"AccountName={STORAGE_ACCOUNT_NAME};"
    f"AccountKey={STORAGE_ACCOUNT_KEY};"
    f"EndpointSuffix=core.windows.net"
)

# --- Blob Utility Functions ---
def read_csv_blob(blob_name: str) -> pd.DataFrame:
    blob_service = BlobServiceClient.from_connection_string(BLOB_CONNECTION_STRING)
    blob_client = blob_service.get_container_client(CONTAINER_NAME).get_blob_client(blob_name)
    stream = blob_client.download_blob().readall()
    return pd.read_csv(io.BytesIO(stream))

def append_to_blob_csv(blob_name: str, new_data: dict):
    df_new = pd.DataFrame([new_data])
    blob_service = BlobServiceClient.from_connection_string(BLOB_CONNECTION_STRING)
    container_client = blob_service.get_container_client(CONTAINER_NAME)
    blob_client = container_client.get_blob_client(blob_name)

    # Try to read existing blob or create new
    try:
        existing_data = blob_client.download_blob().readall()
        df_existing = pd.read_csv(io.BytesIO(existing_data))
        df_combined = pd.concat([df_existing, df_new], ignore_index=True)
    except:
        df_combined = df_new

    out_buffer = io.BytesIO()
    df_combined.to_csv(out_buffer, index=False)
    out_buffer.seek(0)
    blob_client.upload_blob(out_buffer, overwrite=True)

# --- Login Endpoint ---
@app.post("/login")
async def login(username: str = Form(...), password: str = Form(...)):
    expected_user = os.getenv("LOGIN_USERNAME", "fs2025")
    expected_pass = os.getenv("LOGIN_PASSWORD", "icbfs1095")
    if username == expected_user and password == expected_pass:
        return JSONResponse({"success": True})
    return JSONResponse({"success": False}, status_code=401)

# --- Search Registered Guests ---
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
            customer_code.lower() in str(row.get("customer_code", "")).lower() and
            attendee_name.lower() in str(row.get("attendee_name", "")).lower() and
            customer_name.lower() in str(row.get("customer_name", "")).lower() and
            registration_id.lower() in str(row.get("registration_id", "")).lower(),
            axis=1
        )
    ]
    return match.to_dict(orient="records")

# --- Log Attendance (Registered) ---
@app.post("/mark_attendance")
async def mark_attendance(data: dict):
    append_to_blob_csv("booth_queue.csv", data)
    return {"status": "Registered guest logged for badge print"}

# --- Walk-in Submission ---
@app.post("/walkin")
async def register_walkin(data: dict):
    append_to_blob_csv("walkins.csv", data)
    append_to_blob_csv("booth_queue.csv", data)
    return {"status": "Walk-in guest logged and queued"}
