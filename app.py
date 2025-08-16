import os
import uuid
import csv
from datetime import datetime
from io import StringIO

from fastapi import FastAPI, Request, Form, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from starlette.status import HTTP_302_FOUND

from azure.storage.blob import BlobServiceClient
from azure.core.exceptions import ResourceNotFoundError

# ------------------ ENV ------------------
AZ_CONN = os.getenv("AZURE_STORAGE_CONNECTION_STRING", "")
CONTAINER = os.getenv("AZURE_BLOB_CONTAINER", "registration-data")
REGISTERED_BLOB = os.getenv("REGISTERED_BLOB", "registered.csv")
ATTENDANCE_BLOB = os.getenv("ATTENDANCE_BLOB", "attendance.csv")
WALKINS_BLOB = os.getenv("WALKINS_BLOB", "walkins.csv")
QUEUE_BLOB = os.getenv("QUEUE_BLOB", "print_queue.csv")

LOGIN_USERNAME = os.getenv("LOGIN_USERNAME", "fs2025")
LOGIN_PASSWORD = os.getenv("LOGIN_PASSWORD", "icbfs1095")

SESSION_SECRET = os.getenv("SESSION_SECRET", "dev-secret-change-me")

# ------------------ APP ------------------
app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key=SESSION_SECRET, same_site="lax")

templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="."), name="static")

# ------------------ AZURE HELPERS ------------------
blob_service = BlobServiceClient.from_connection_string(AZ_CONN) if AZ_CONN else None


def _container_client():
    if not blob_service:
        raise RuntimeError("AZURE_STORAGE_CONNECTION_STRING not configured.")
    return blob_service.get_container_client(CONTAINER)


def _get_blob_text(blob_name: str) -> str:
    cc = _container_client()
    bc = cc.get_blob_client(blob_name)
    try:
        data = bc.download_blob().readall()
        return data.decode("utf-8")
    except ResourceNotFoundError:
        raise


def _upload_blob_text(blob_name: str, text: str):
    cc = _container_client()
    bc = cc.get_blob_client(blob_name)
    bc.upload_blob(text.encode("utf-8"), overwrite=True)


def ensure_blob_with_header(blob_name: str, headers: list[str]):
    try:
        _get_blob_text(blob_name)
    except ResourceNotFoundError:
        sio = StringIO()
        writer = csv.DictWriter(sio, fieldnames=headers)
        writer.writeheader()
        _upload_blob_text(blob_name, sio.getvalue())


def read_csv_dicts(blob_name: str) -> list[dict]:
    text = _get_blob_text(blob_name)
    sio = StringIO(text)
    reader = csv.DictReader(sio)
    rows = [dict({k: (v or "") for k, v in r.items()}) for r in reader]
    return rows


def write_csv_dicts(blob_name: str, headers: list[str], rows: list[dict]):
    sio = StringIO()
    writer = csv.DictWriter(sio, fieldnames=headers)
    writer.writeheader()
    for r in rows:
        writer.writerow({h: r.get(h, "") for h in headers})
    _upload_blob_text(blob_name, sio.getvalue())


def append_csv_row(blob_name: str, headers: list[str], row: dict):
    try:
        existing = read_csv_dicts(blob_name)
    except ResourceNotFoundError:
        existing = []
    existing.append({h: row.get(h, "") for h in headers})
    write_csv_dicts(blob_name, headers, existing)


# ------------------ STARTUP ------------------
@app.on_event("startup")
def startup():
    # create aux CSVs with headers if missing
    ensure_blob_with_header(ATTENDANCE_BLOB, ["registration_id", "source", "marked_at_iso"])
    ensure_blob_with_header(WALKINS_BLOB, [
        "walkin_id","walkin_type","customer_code","customer_name","attendee_name","email","phone","how_heard","created_at_iso"
    ])
    ensure_blob_with_header(QUEUE_BLOB, [
        "queue_id","source","registration_id","walkin_id","customer_code","customer_name","attendee_name","status","created_at_iso"
    ])


# ------------------ AUTH ------------------

def require_login(request: Request):
    if request.session.get("authed") is True:
        return
    raise HTTPException(status_code=401, detail="Not authenticated")


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "error": None})


@app.post("/login")
def login(request: Request, username: str = Form(...), password: str = Form(...)):
    if username == LOGIN_USERNAME and password == LOGIN_PASSWORD:
        request.session["authed"] = True
        return RedirectResponse(url="/dashboard", status_code=HTTP_302_FOUND)
    return templates.TemplateResponse("login.html", {"request": request, "error": "Invalid credentials"})


@app.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=HTTP_302_FOUND)


# ------------------ PAGES ------------------
@app.get("/", response_class=HTMLResponse)
def root(request: Request):
    if request.session.get("authed"):
        return RedirectResponse("/dashboard", status_code=HTTP_302_FOUND)
    return RedirectResponse("/login", status_code=HTTP_302_FOUND)


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request, _: None = Depends(require_login)):
    return templates.TemplateResponse("dashboard.html", {"request": request})


@app.get("/registered", response_class=HTMLResponse)
def registered_page(request: Request, _: None = Depends(require_login)):
    return templates.TemplateResponse("registered.html", {"request": request})


@app.get("/walkin", response_class=HTMLResponse)
def walkin_page(request: Request, _: None = Depends(require_login)):
    return templates.TemplateResponse("walkin.html", {"request": request})


@app.get("/booth", response_class=HTMLResponse)
def booth_page(request: Request, _: None = Depends(require_login)):
    return templates.TemplateResponse("booth.html", {"request": request})


# ------------------ API: REGISTERED ------------------
@app.get("/api/registered")
def api_registered(_: None = Depends(require_login)):
    try:
        reg_rows = read_csv_dicts(REGISTERED_BLOB)
        att_rows = read_csv_dicts(ATTENDANCE_BLOB)
        here_ids = {(a.get("registration_id") or "") for a in att_rows}
        for r in reg_rows:
            rid = (r.get("registration_id") or "")
            r["here"] = "true" if rid in here_ids else "false"
        return {"items": reg_rows}
    except Exception as e:
        # Temporary visibility to help diagnose; remove once everything works.
        return JSONResponse(status_code=500, content={
            "error": type(e).__name__,
            "message": str(e)
        })



@app.post("/api/attendance")
def api_mark_here(registration_id: str = Form(...), _: None = Depends(require_login)):
    # Idempotent: only append if not already present
    att = read_csv_dicts(ATTENDANCE_BLOB)
    if not any(a.get("registration_id") == registration_id for a in att):
        append_csv_row(ATTENDANCE_BLOB,
                       ["registration_id","source","marked_at_iso"],
                       {"registration_id": registration_id, "source": "registered", "marked_at_iso": datetime.utcnow().isoformat()})
    return {"ok": True}


# ------------------ API: PRINT QUEUE ------------------
@app.get("/api/queue")
def api_queue(_: None = Depends(require_login)):
    rows = read_csv_dicts(QUEUE_BLOB)
    # only pending
    pending = [r for r in rows if r.get("status") == "pending"]
    # sort by created time
    pending.sort(key=lambda x: x.get("created_at_iso", ""))
    return {"items": pending}


@app.post("/api/queue/add")
def api_queue_add(
    source: str = Form(...),
    registration_id: str = Form("") ,
    walkin_id: str = Form(""),
    customer_code: str = Form(""),
    customer_name: str = Form(...),
    attendee_name: str = Form(...),
    _: None = Depends(require_login)
):
    qid = str(uuid.uuid4())
    append_csv_row(QUEUE_BLOB,
                   ["queue_id","source","registration_id","walkin_id","customer_code","customer_name","attendee_name","status","created_at_iso"],
                   {
                       "queue_id": qid,
                       "source": source,
                       "registration_id": registration_id,
                       "walkin_id": walkin_id,
                       "customer_code": customer_code,
                       "customer_name": customer_name,
                       "attendee_name": attendee_name,
                       "status": "pending",
                       "created_at_iso": datetime.utcnow().isoformat()
                   })
    return {"ok": True, "queue_id": qid}


@app.post("/api/queue/mark_printed")
def api_queue_mark_printed(queue_id: str = Form(...), _: None = Depends(require_login)):
    rows = read_csv_dicts(QUEUE_BLOB)
    changed = False
    for r in rows:
        if r.get("queue_id") == queue_id and r.get("status") == "pending":
            r["status"] = "printed"
            changed = True
            break
    if changed:
        write_csv_dicts(QUEUE_BLOB,
                        ["queue_id","source","registration_id","walkin_id","customer_code","customer_name","attendee_name","status","created_at_iso"],
                        rows)
    return {"ok": True}


# ------------------ API: WALK-IN ------------------
@app.post("/api/walkins")
def api_add_walkin(
    walkin_type: str = Form(...),
    customer_code: str = Form(""),
    customer_name: str = Form(...),
    attendee_name: str = Form(...),
    email: str = Form(""),
    phone: str = Form(""),
    how_heard: str = Form(""),
    auto_queue: str = Form("true"),
    _: None = Depends(require_login)
):
    wid = str(uuid.uuid4())
    append_csv_row(WALKINS_BLOB,
                   ["walkin_id","walkin_type","customer_code","customer_name","attendee_name","email","phone","how_heard","created_at_iso"],
                   {
                       "walkin_id": wid,
                       "walkin_type": walkin_type,
                       "customer_code": customer_code,
                       "customer_name": customer_name,
                       "attendee_name": attendee_name,
                       "email": email,
                       "phone": phone,
                       "how_heard": how_heard,
                       "created_at_iso": datetime.utcnow().isoformat()
                   })

    # By definition, walk-ins are present; also add to queue
    qid = None
    if auto_queue.lower() == "true":
        qid = str(uuid.uuid4())
        append_csv_row(QUEUE_BLOB,
                       ["queue_id","source","registration_id","walkin_id","customer_code","customer_name","attendee_name","status","created_at_iso"],
                       {
                           "queue_id": qid,
                           "source": "walkin",
                           "registration_id": "",
                           "walkin_id": wid,
                           "customer_code": customer_code,
                           "customer_name": customer_name,
                           "attendee_name": attendee_name,
                           "status": "pending",
                           "created_at_iso": datetime.utcnow().isoformat()
                       })

    return {"ok": True, "walkin_id": wid, "queue_id": qid}


# ------------------ BADGE PAGE ------------------
@app.get("/badge/{queue_id}", response_class=HTMLResponse)
def badge_page(queue_id: str, request: Request, _: None = Depends(require_login)):
    items = read_csv_dicts(QUEUE_BLOB)
    match = next((r for r in items if r.get("queue_id") == queue_id), None)
    if not match:
        raise HTTPException(404, "Badge not found")
    return templates.TemplateResponse("badge.html", {
        "request": request,
        "customer_code": match.get("customer_code", ""),
        "customer_name": match.get("customer_name", ""),
        "attendee_name": match.get("attendee_name", ""),
        "queue_id": queue_id
    })


# -------------- LOCAL DEV QUICK START --------------
# if __name__ == "__main__":
#     import uvicorn
#     uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
