from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import pandas as pd
from azure.storage.blob import BlobServiceClient
import io
import os

app = FastAPI()

# Mount static HTML folder
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="static")

# Get Blob Storage info from environment
AZURE_STORAGE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
CONTAINER_NAME = "registration-data"
BLOB_NAME = "registered.csv"

# Read CSV from Blob
def read_registered_csv():
    blob_service = BlobServiceClient.from_connection_string(AZURE_STORAGE_CONNECTION_STRING)
    blob_client = blob_service.get_container_client(CONTAINER_NAME).get_blob_client(BLOB_NAME)
    download = blob_client.download_blob()
    df = pd.read_csv(io.BytesIO(download.readall()))
    return df

# Serve the registered guests page
@app.get("/registered", response_class=HTMLResponse)
async def get_registered(request: Request):
    df = read_registered_csv()
    data = df.to_dict(orient="records")
    return templates.TemplateResponse("registered.html", {"request": request, "results": data})

# Search/filter endpoint (AJAX)
@app.post("/search")
async def search_registered(
    customer_code: str = Form(""),
    customer_name: str = Form(""),
    attendee_name: str = Form(""),
    registration_id: str = Form("")
):
    try:
        df = read_registered_csv()
        filtered = df[
            df.apply(lambda row:
                customer_code.lower() in str(row.get("customer_code", "")).lower() and
                customer_name.lower() in str(row.get("customer_name", "")).lower() and
                attendee_name.lower() in str(row.get("attendee_name", "")).lower() and
                registration_id.lower() in str(row.get("registration_id", "")).lower(),
            axis=1
            )
        ]
        return JSONResponse(filtered.to_dict(orient="records"))
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

#login
@app.post("/login")
async def login(username: str = Form(...), password: str = Form(...)):
    expected_user = os.getenv("LOGIN_USERNAME", "fs2025")
    expected_pass = os.getenv("LOGIN_PASSWORD", "icbfs1095")
    
    if username == expected_user and password == expected_pass:
        return JSONResponse({"success": True})
    return JSONResponse({"success": False}, status_code=401)


