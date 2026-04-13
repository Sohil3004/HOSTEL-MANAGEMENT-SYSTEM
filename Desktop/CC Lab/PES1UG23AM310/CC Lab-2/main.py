from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from database import get_db
from checkout import checkout_logic
import time
from typing import List, Dict

app = FastAPI()
SRN = "PES1UG2XCSXXX"
templates = Jinja2Templates(directory="templates")

# Simple in-memory cache for events list to avoid repeated DB hits under load
# cache structure: {"ts": float, "data": List[Dict]}
EVENTS_CACHE = {"ts": 0.0, "data": None}
EVENTS_CACHE_TTL = 5.0  # seconds
MY_EVENTS_CACHE = {}
MY_EVENTS_CACHE_TTL = 5.0


@app.on_event("startup")
def startup():
    db = get_db()
    db.execute("CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, password TEXT)")
    db.execute("CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, fee INTEGER)")
    db.execute("CREATE TABLE IF NOT EXISTS registrations (username TEXT, event_id INTEGER)")
    db.commit()


@app.get("/register", response_class=HTMLResponse)
def register_page(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})


@app.post("/register")
def register(username: str = Form(...), password: str = Form(...)):
    db = get_db()
    try:
        db.execute("INSERT INTO users VALUES (?,?)", (username, password))
        db.commit()
    except:
        return HTMLResponse("Username already exists. Try a different one.")
    return RedirectResponse("/login", status_code=302)


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@app.post("/login", response_class=HTMLResponse)
def login(request: Request, username: str = Form(...), password: str = Form(...)):
    db = get_db()
    user = db.execute(
        "SELECT * FROM users WHERE username=? AND password=?",
        (username, password)
    ).fetchone()

    if not user:
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": " Invalid username or password", "user": ""}
        )

    return RedirectResponse(f"/events?user={username}", status_code=302)



@app.get("/events", response_class=HTMLResponse)
def events(request: Request, user: str):
    # serve cached events when fresh
    now = time.time()
    if EVENTS_CACHE["data"] is not None and (now - EVENTS_CACHE["ts"]) < EVENTS_CACHE_TTL:
        rows = EVENTS_CACHE["data"]
    else:
        db = get_db()
        # select only needed columns and convert rows to plain dicts for template
        fetched = db.execute("SELECT id, name, fee FROM events").fetchall()
        rows = [dict(r) for r in fetched]
        EVENTS_CACHE["data"] = rows
        EVENTS_CACHE["ts"] = now

    return templates.TemplateResponse(
        "events.html",
        {"request": request, "events": rows, "user": user}
    )


@app.get("/register_event/{event_id}")
def register_event(event_id: int, user: str):
    if event_id == 404:
        1 / 0

    db = get_db()
    db.execute("INSERT INTO registrations VALUES (?,?)", (user, event_id))
    db.commit()

    # invalidate per-user my-events cache so user sees updates quickly
    try:
        MY_EVENTS_CACHE.pop(user, None)
    except Exception:
        pass

    return RedirectResponse(f"/my-events?user={user}", status_code=302)


@app.get("/my-events", response_class=HTMLResponse)
def my_events(request: Request, user: str):
    # serve cached per-user results when fresh
    now = time.time()
    cached = MY_EVENTS_CACHE.get(user)
    if cached is not None and (now - cached.get("ts", 0.0)) < MY_EVENTS_CACHE_TTL:
        rows = cached["data"]
    else:
        db = get_db()
        fetched = db.execute(
            """
            SELECT events.name, events.fee
            FROM events
            JOIN registrations ON events.id = registrations.event_id
            WHERE registrations.username=?
            """,
            (user,)
        ).fetchall()
        rows = [dict(r) for r in fetched]
        MY_EVENTS_CACHE[user] = {"ts": now, "data": rows}

    return templates.TemplateResponse(
        "my_events.html",
        {"request": request, "events": rows, "user": user}
    )


@app.get("/checkout", response_class=HTMLResponse)
def checkout(request: Request):
    total = checkout_logic()
    return templates.TemplateResponse(
        "checkout.html",
        {"request": request, "total": total, "user": ""}
    )
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    # Try to keep user on UI even when it crashes
    user = request.query_params.get("user", "")

    return templates.TemplateResponse(
        "error.html",
        {
            "request": request,
            "status_code": 500,
            "detail": str(exc),
            "user": user
        },
        status_code=500
    )