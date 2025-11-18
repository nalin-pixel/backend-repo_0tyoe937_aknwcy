import os
from datetime import date, datetime, timedelta
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, EmailStr
from jose import JWTError, jwt
from passlib.context import CryptContext
from bson import ObjectId

from database import db, create_document, get_documents
from schemas import CheckIn, TriggerJournal, Goal, AuthUser

# -------------------------
# App and CORS
# -------------------------
app = FastAPI(title="Habit Breaker API", version="1.2.1")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------------
# Auth/JWT Utilities
# -------------------------
SECRET_KEY = os.getenv("SECRET_KEY", "change-this-secret-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "43200"))  # 30 days
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password: str, password_hash: str) -> bool:
    return pwd_context.verify(plain_password, password_hash)

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

class RegisterBody(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=6)
    display_name: Optional[str] = None

class LoginBody(BaseModel):
    email: EmailStr
    password: str

class MeResponse(BaseModel):
    id: str
    email: EmailStr
    display_name: Optional[str] = None

async def get_current_user(authorization: Optional[str] = Header(default=None)) -> Optional[dict]:
    if not authorization:
        return None
    try:
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not token:
            return None
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if not user_id:
            return None
        user = None
        try:
            user = db["authuser"].find_one({"_id": ObjectId(user_id)})
        except Exception:
            user = db["authuser"].find_one({"_id": user_id})
        if user:
            user["_id"] = str(user.get("_id"))
        return user
    except Exception:
        return None

# -------------------------
# Health & status
# -------------------------
@app.get("/")
def read_root():
    return {"message": "Habit Breaker Backend is running"}

@app.get("/api/hello")
def hello():
    return {"message": "Hello from the backend API!"}

@app.get("/test")
def test_database():
    """Test endpoint to check if database is available and accessible"""
    response: Dict[str, Any] = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }
    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Configured"
            response["database_name"] = db.name if hasattr(db, 'name') else "✅ Connected"
            response["connection_status"] = "Connected"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"

    response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"
    return response

# -------------------------
# Auth Endpoints
# -------------------------
@app.post("/api/auth/register", response_model=Token)
def register(body: RegisterBody):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    existing = db["authuser"].find_one({"email": body.email.lower()})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    user_doc = AuthUser(email=body.email.lower(), password_hash=hash_password(body.password), display_name=body.display_name)
    inserted_id = db["authuser"].insert_one(user_doc.model_dump()).inserted_id
    token = create_access_token({"sub": str(inserted_id)})
    return Token(access_token=token)

@app.post("/api/auth/login", response_model=Token)
def login(body: LoginBody):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    user = db["authuser"].find_one({"email": body.email.lower()})
    if not user or not verify_password(body.password, user.get("password_hash", "")):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    token = create_access_token({"sub": str(user.get("_id"))})
    return Token(access_token=token)

@app.get("/api/auth/me", response_model=MeResponse)
def me(current_user: Optional[dict] = Depends(get_current_user)):
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return MeResponse(id=str(current_user.get("_id")), email=current_user.get("email"), display_name=current_user.get("display_name"))

# -------------------------
# Habit-focused Endpoints
# -------------------------
class JournalCreate(BaseModel):
    note: str = Field(..., min_length=1, max_length=2000)
    intensity: Optional[int] = Field(None, ge=1, le=10)
    feeling: Optional[str] = Field(None, max_length=100)
    user_id: Optional[str] = None

@app.post("/api/journal")
def create_journal(entry: JournalCreate, current_user: Optional[dict] = Depends(get_current_user)):
    uid = str(current_user.get("_id")) if current_user else entry.user_id
    doc = TriggerJournal(**{**entry.model_dump(), "user_id": uid})
    inserted_id = create_document("triggerjournal", doc)
    return {"id": inserted_id, "message": "Journal saved"}

@app.get("/api/journal")
def list_journal(limit: int = 20, current_user: Optional[dict] = Depends(get_current_user)):
    q: Dict[str, Any] = {"user_id": str(current_user.get("_id"))} if current_user else {}
    items = get_documents("triggerjournal", q, limit)
    for it in items:
        it["_id"] = str(it.get("_id"))
        for k in ("created_at", "updated_at"):
            if k in it and hasattr(it[k], "isoformat"):
                it[k] = it[k].isoformat()
    return {"items": items}

class CheckInCreate(BaseModel):
    day: date = Field(default_factory=date.today)
    user_id: Optional[str] = None

@app.post("/api/checkin")
def create_checkin(payload: CheckInCreate, current_user: Optional[dict] = Depends(get_current_user)):
    uid = str(current_user.get("_id")) if current_user else payload.user_id
    doc = CheckIn(**{**payload.model_dump(), "user_id": uid})
    inserted_id = create_document("checkin", doc)
    return {"id": inserted_id, "message": "Check-in recorded"}

@app.get("/api/checkins")
def list_checkins(limit: int = 60, current_user: Optional[dict] = Depends(get_current_user)):
    q: Dict[str, Any] = {"user_id": str(current_user.get("_id"))} if current_user else {}
    items = get_documents("checkin", q, limit)
    for it in items:
        it["_id"] = str(it.get("_id"))
        if "day" in it and hasattr(it["day"], "isoformat"):
            it["day"] = it["day"].isoformat()
    return {"items": items}

@app.get("/api/streak")
def get_streak(user_id: Optional[str] = None, current_user: Optional[dict] = Depends(get_current_user)):
    uid = str(current_user.get("_id")) if current_user else user_id
    items = get_documents("checkin", {"user_id": uid} if uid else {}, None)
    days = {str(it.get("day")) for it in items}
    # compute current streak ending today
    streak = 0
    today = date.today()
    d = today
    while str(d) in days:
        streak += 1
        d = d - timedelta(days=1)
    return {"days_logged": len(days), "current_streak": streak}

class GoalCreate(BaseModel):
    title: str = Field(..., min_length=3, max_length=100)
    target_days: int = Field(..., ge=1, le=3650)
    start_date: date = Field(default_factory=date.today)
    user_id: Optional[str] = None

@app.post("/api/goals")
def create_goal(goal: GoalCreate, current_user: Optional[dict] = Depends(get_current_user)):
    uid = str(current_user.get("_id")) if current_user else goal.user_id
    doc = Goal(**{**goal.model_dump(), "user_id": uid})
    inserted_id = create_document("goal", doc)
    return {"id": inserted_id, "message": "Goal created"}

@app.get("/api/goals")
def list_goals(user_id: Optional[str] = None, limit: int = 20, current_user: Optional[dict] = Depends(get_current_user)):
    uid = str(current_user.get("_id")) if current_user else user_id
    q = {"user_id": uid} if uid else {}
    items = get_documents("goal", q, limit)
    for it in items:
        it["_id"] = str(it.get("_id"))
        for k in ("created_at", "updated_at", "start_date"):
            if k in it and hasattr(it[k], "isoformat"):
                it[k] = it[k].isoformat()
    return {"items": items}

# Educational tips by habit
GENERAL_TIPS: List[str] = [
    "Replace the habit loop: identify trigger, routine, reward.",
    "Use the 10-minute rule: delay the urge and do a grounding exercise.",
    "Design your environment to make the bad habit harder and the good one easier.",
    "Build accountability: a friend, coach, or community.",
    "Sleep, food, and exercise improve impulse control and mood.",
]

HABIT_TIPS: Dict[str, List[str]] = {
    "general": GENERAL_TIPS,
    "phone": [
        "Set scheduled Do Not Disturb and remove non-essential notifications.",
        "Keep the phone outside your bedroom; use an alarm clock.",
        "Make your home screen a folder of tools, not temptations.",
    ] + GENERAL_TIPS,
    "junk food": [
        "Shop the perimeter; keep healthy snacks visible and ready.",
        "Pre-commit: don't buy trigger foods; use smaller plates.",
        "Protein at breakfast reduces cravings later.",
    ] + GENERAL_TIPS,
    "procrastination": [
        "Start with a 2-minute version of the task.",
        "Time-box work in 25-minute sprints (Pomodoro).",
        "Write the next actionable step and set a start time.",
    ] + GENERAL_TIPS,
    "smoking": [
        "List your cues and avoid them for the first 30 days.",
        "Use nicotine replacement as advised; track cravings.",
        "Pair urges with deep breathing and a short walk.",
    ] + GENERAL_TIPS,
    "alcohol": [
        "Alcohol-free days: schedule 3-4 per week to reset.",
        "Swap evening drinks for a ritual: tea, shower, stretch.",
        "Avoid 'just one': decide in advance and tell a friend.",
    ] + GENERAL_TIPS,
    "gambling": [
        "Self-exclude from apps and venues; block access.",
        "Delay betting by 15 minutes; call someone instead.",
        "Track wins/losses honestly; set hard financial limits.",
    ] + GENERAL_TIPS,
}

@app.get("/api/tips")
def get_tips(habit: Optional[str] = None):
    key = (habit or "general").strip().lower()
    tips = HABIT_TIPS.get(key, GENERAL_TIPS)
    # Return up to 8 unique tips preserving order
    seen = set()
    ordered = []
    for t in tips:
        if t not in seen:
            seen.add(t)
            ordered.append(t)
        if len(ordered) >= 8:
            break
    return {"tips": ordered, "habit": key}

# Simple metrics (for charts)
@app.get("/api/metrics")
def metrics(current_user: Optional[dict] = Depends(get_current_user)):
    uid = str(current_user.get("_id")) if current_user else None
    items = get_documents("checkin", {"user_id": uid} if uid else {}, None)
    days_map: Dict[str, int] = {}
    for it in items:
        d = str(it.get("day"))
        days_map[d] = days_map.get(d, 0) + 1
    today = date.today()
    series = []
    for i in range(13, -1, -1):
        d = today - timedelta(days=i)
        k = str(d)
        series.append({"day": k, "count": days_map.get(k, 0)})
    journ = get_documents("triggerjournal", {"user_id": uid} if uid else {}, 200)
    ints = [it.get("intensity") for it in journ if isinstance(it.get("intensity"), int)]
    return {"checkins": series, "journal_count": len(journ), "avg_intensity": (sum(ints)/len(ints) if ints else None)}

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
