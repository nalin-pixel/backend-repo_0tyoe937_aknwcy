import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, List, Dict
from datetime import date

from database import db, create_document, get_documents
from schemas import CheckIn, TriggerJournal, Goal

app = FastAPI(title="Habit Breaker API", version="1.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"message": "Habit Breaker Backend is running"}

@app.get("/api/hello")
def hello():
    return {"message": "Hello from the backend API!"}

@app.get("/test")
def test_database():
    """Test endpoint to check if database is available and accessible"""
    response = {
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
    
    import os
    response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"
    
    return response

# -------------------------
# Habit-focused Endpoints
# -------------------------

class JournalCreate(BaseModel):
    note: str = Field(..., min_length=1, max_length=2000)
    intensity: Optional[int] = Field(None, ge=1, le=10)
    feeling: Optional[str] = Field(None, max_length=100)
    user_id: Optional[str] = None

@app.post("/api/journal")
def create_journal(entry: JournalCreate):
    doc = TriggerJournal(**entry.model_dump())
    inserted_id = create_document("triggerjournal", doc)
    return {"id": inserted_id, "message": "Journal saved"}

@app.get("/api/journal")
def list_journal(limit: int = 20):
    items = get_documents("triggerjournal", {}, limit)
    # Convert ObjectId and datetime for JSON friendliness
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
def create_checkin(payload: CheckInCreate):
    doc = CheckIn(**payload.model_dump())
    inserted_id = create_document("checkin", doc)
    return {"id": inserted_id, "message": "Check-in recorded"}

@app.get("/api/streak")
def get_streak(user_id: Optional[str] = None):
    # Basic streak calculation: count distinct days of check-ins
    items = get_documents("checkin", {"user_id": user_id} if user_id else {}, None)
    days = {str(it.get("day")) for it in items}
    return {"days_logged": len(days)}

class GoalCreate(BaseModel):
    title: str = Field(..., min_length=3, max_length=100)
    target_days: int = Field(..., ge=1, le=3650)
    start_date: date = Field(default_factory=date.today)
    user_id: Optional[str] = None

@app.post("/api/goals")
def create_goal(goal: GoalCreate):
    doc = Goal(**goal.model_dump())
    inserted_id = create_document("goal", doc)
    return {"id": inserted_id, "message": "Goal created"}

@app.get("/api/goals")
def list_goals(user_id: Optional[str] = None, limit: int = 20):
    q = {"user_id": user_id} if user_id else {}
    items = get_documents("goal", q, limit)
    for it in items:
        it["_id"] = str(it.get("_id"))
        for k in ("created_at", "updated_at", "start_date"):
            if k in it and hasattr(it[k], "isoformat"):
                it[k] = it[k].isoformat()
    return {"items": items}

# Educational tips by habit (non-graphic, supportive content)
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

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
