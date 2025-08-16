# main.py (FastAPI backend for Food Show app)
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import pandas as pd
import os

app = FastAPI()

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

DATA_PATH = "./backend/data"

@app.post("/login")
async def login(username: str = Form(...), password: str = Form(...)):
    expected_user = os.getenv("LOGIN_USERNAME", "fs2025")
    expected_pass = os.getenv("LOGIN_PASSWORD", "icbfs1095")
    if username == expected_user and password == expected_pass:
        return JSONResponse({"success": True})
    return JSONResponse({"success": False}, status_code=401)

@app.get("/registered")
def load_registered():
    path = f"{DATA_PATH}/registered.csv"
    if not os.path.exists(path):
        return []
    df = pd.read_csv(path, encoding="ISO-8859-1")
    return df.to_dict(orient="records")

@app.post("/search")
async def search(
    account: str = Form(""),
    first: str = Form(""),
    last: str = Form(""),
    company: str = Form(""),
    regname: str = Form("")
):
    df = pd.read_csv(f"{DATA_PATH}/registered.csv", encoding="ISO-8859-1")
    filtered = df[
        df.apply(lambda row:
            account.lower() in str(row["Customer Code"]).lower() or
            first.lower() in str(row["Attendee Name"]).split()[0].lower() or
            last.lower() in str(row["Attendee Name"]).split()[-1].lower() or
            company.lower() in str(row["Customer Name"]).lower() or
            regname.lower() in str(row["Attendee Name"]).lower(), axis=1)
    ]
    return filtered.to_dict(orient="records")

@app.post("/mark_attendance")
async def mark_attendance(data: dict):
    df = pd.DataFrame([data])
    df.to_csv(f"{DATA_PATH}/attendance_log.csv", mode='a', header=not os.path.exists(f"{DATA_PATH}/attendance_log.csv"), index=False)
    df.to_csv(f"{DATA_PATH}/booth_queue.csv", mode='a', header=not os.path.exists(f"{DATA_PATH}/booth_queue.csv"), index=False)
    return {"status": "Logged & Sent to Booth"}

@app.post("/walkin")
async def register_walkin(data: dict):
    df = pd.DataFrame([data])
    df.to_csv(f"{DATA_PATH}/walkins.csv", mode='a', header=not os.path.exists(f"{DATA_PATH}/walkins.csv"), index=False)
    df.to_csv(f"{DATA_PATH}/booth_queue.csv", mode='a', header=not os.path.exists(f"{DATA_PATH}/booth_queue.csv"), index=False)
    return {"status": "Walk-in Registered & Sent to Booth"}

@app.get("/booth_queue")
async def booth_queue():
    path = f"{DATA_PATH}/booth_queue.csv"
    if not os.path.exists(path):
        return []
    df = pd.read_csv(path)
    return df.to_dict(orient="records")
