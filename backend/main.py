from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import pandas as pd
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
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DATA_PATH = "./backend/data"

# Login
@app.post("/login")
async def login(username: str = Form(...), password: str = Form(...)):
    expected_user = os.getenv("LOGIN_USERNAME", "fs2025")
    expected_pass = os.getenv("LOGIN_PASSWORD", "icbfs1095")
    if username == expected_user and password == expected_pass:
        return JSONResponse({"success": True})
    return JSONResponse({"success": False}, status_code=401)

# Load registered CSV
def load_registered():
    try:
        return pd.read_csv(f"{DATA_PATH}/registered.csv", encoding="ISO-8859-1")
    except:
        return pd.DataFrame()

# Search
@app.post("/search")
async def search(
    account: str = Form(""),
    first: str = Form(""),
    last: str = Form(""),
    company: str = Form(""),
    regname: str = Form("")
):
    df = load_registered()
    match = df[
        df.apply(lambda row:
            account.lower() in row["Customer Code"].lower() or
            first.lower() in row["Attendee Name"].lower().split()[0] or
            last.lower() in row["Attendee Name"].lower().split()[-1] or
            company.lower() in row["Customer Name"].lower() or
            regname.lower() in row["Attendee Name"].lower(), axis=1)
    ]
    return match.to_dict(orient="records")

# Attendance log
@app.post("/mark_attendance")
async def mark_attendance(data: dict):
    df = pd.DataFrame([data])
    path = f"{DATA_PATH}/attendance_log.csv"
    df.to_csv(path, mode='a', header=not os.path.exists(path), index=False)
    return {"status": "Logged"}

# Walk-in form
@app.post("/walkin")
async def register_walkin(data: dict):
    df = pd.DataFrame([data])
    path = f"{DATA_PATH}/walkins.csv"
    df.to_csv(path, mode='a', header=not os.path.exists(path), index=False)
    return {"status": "Walk-in Registered"}
