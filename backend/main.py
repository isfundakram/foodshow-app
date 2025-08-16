from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import pandas as pd
import os

app = FastAPI()

# Serve static frontend files
app.mount("/static", StaticFiles(directory="frontend"), name="static")

@app.get("/", response_class=FileResponse)
async def root():
    return FileResponse("frontend/login.html")

# Enable CORS (for frontend access)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Replace with domain in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Path to data directory
DATA_PATH = "./backend/data"

# In-memory queue for booth badge printing
booth_queue = []

# --- LOGIN ---
@app.post("/login")
async def login(username: str = Form(...), password: str = Form(...)):
    expected_user = os.getenv("LOGIN_USERNAME", "fs2025")
    expected_pass = os.getenv("LOGIN_PASSWORD", "icbfs1095")
    if username == expected_user and password == expected_pass:
        return JSONResponse({"success": True})
    return JSONResponse({"success": False}, status_code=401)

# --- REGISTERED SEARCH ---
def load_registered():
    try:
        return pd.read_csv(f"{DATA_PATH}/registered.csv", encoding="ISO-8859-1")
    except:
        return pd.DataFrame()

@app.post("/search")
async def search(
    account: str = Form(""),
    company: str = Form(""),
    regname: str = Form(""),
    attendee: str = Form("")
):
    df = load_registered()

    def match_row(row):
        return (
            account.lower() in str(row["Customer Code"]).lower()
            or company.lower() in str(row["Customer Name"]).lower()
            or regname.lower() in str(row["Registration ID"]).lower()
            or attendee.lower() in str(row["Attendee Name"]).lower()
        )

    matched = df[df.apply(match_row, axis=1)]
    return matched.to_dict(orient="records")


# --- LOG ATTENDANCE ---
@app.post("/mark_attendance")
async def mark_attendance(data: dict):
    df = pd.DataFrame([data])
    path = f"{DATA_PATH}/attendance_log.csv"
    df.to_csv(path, mode='a', header=not os.path.exists(path), index=False)
    return {"status": "Logged"}

# --- WALK-IN REGISTRATION ---
@app.post("/walkin")
async def register_walkin(data: dict):
    df = pd.DataFrame([data])
    path = f"{DATA_PATH}/walkins.csv"
    df.to_csv(path, mode='a', header=not os.path.exists(path), index=False)

    # Also send to booth
    booth_queue.append({"name": data.get("first_name", "") + " " + data.get("last_name", "")})
    return {"status": "Walk-in Registered"}

# --- BOOTH QUEUE ---
@app.post("/booth_queue")
async def booth_queue_add(data: dict):
    booth_queue.append(data)
    return {"status": "added"}

@app.get("/booth_queue")
async def booth_queue_get():
    return booth_queue

@app.post("/booth_queue/remove")
async def booth_queue_remove(data: dict):
    name = data.get("name")
    global booth_queue
    booth_queue = [entry for entry in booth_queue if entry.get("name") != name]
    return {"status": "removed"}
