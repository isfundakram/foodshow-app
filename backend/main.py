from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from azure.storage.blob import BlobServiceClient
import pandas as pd
import requests
from io import BytesIO
import os

app = FastAPI()
templates = Jinja2Templates(directory="templates")

# Serve static frontend
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

# Replace this with your actual GitHub RAW CSV URL
GITHUB_CSV_URL = "https://github.com/isfundakram/foodshow-app/blob/main/backend/data/registered.csv"

def read_csv_from_github():
    url = "https://github.com/isfundakram/foodshow-app/blob/main/backend/data/registered.csv"  # replace with yours
    try:
        response = requests.get(url)
        response.raise_for_status()
        content = response.content.decode("utf-8")  # decode before reading
        df = pd.read_csv(BytesIO(content.encode()))
        df.columns = [col.strip().lower().replace(" ", "_") for col in df.columns]
        return df
    except Exception as e:
        print(f"❌ Error loading CSV from GitHub: {e}")
        return pd.DataFrame()


@app.post("/login")
async def login(username: str = Form(...), password: str = Form(...)):
    expected_user = os.environ["LOGIN_USERNAME"]
    expected_pass = os.environ["LOGIN_PASSWORD"]
    if username == expected_user and password == expected_pass:
        return JSONResponse({"success": True})
    return JSONResponse({"success": False}, status_code=401)

@app.post("/search")
async def search(
    customer_code: str = Form(""),
    attendee_name: str = Form(""),
    customer_name: str = Form(""),
    registration_id: str = Form("")
):
    df = read_csv_from_github()

    print("🔍 Search Query:")
    print("Customer Code:", customer_code)
    print("Customer Name:", customer_name)
    print("Attendee Name:", attendee_name)
    print("Registration ID:", registration_id)
    print("📄 DataFrame preview:")
    print(df.head().to_dict(orient="records"))

    results = df[df.apply(lambda row:
        (customer_code.lower() in str(row.get("customer_code", "")).lower()) or
        (attendee_name.lower() in str(row.get("attendee_name", "")).lower()) or
        (customer_name.lower() in str(row.get("customer_name", "")).lower()) or
        (registration_id.lower() in str(row.get("registration_id", "")).lower()),
        axis=1
    )]

    print("✅ Results found:", len(results))
    return results.to_dict(orient="records")

@app.post("/mark_attendance")
async def mark_attendance(data: dict):
    # You can leave this unimplemented or later connect to Azure/DB/CSV
    print("Attendance logged:", data)
    return {"status": "Logged (but not saved yet)"}

@app.post("/walkin")
async def register_walkin(data: dict):
    print("Walk-in registered:", data)
    return {"status": "Walk-in Registered (but not saved yet)"}

@app.get("/booth_queue")
async def get_booth_queue():
    return []  # Placeholder for now
