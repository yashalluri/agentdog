from fastapi import FastAPI, APIRouter, HTTPException, Depends, Request, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
import os
import logging
from pathlib import Path
from pydantic import BaseModel, EmailStr
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from emergentintegrations.llm.chat import LlmChat, UserMessage
import json
from bson import ObjectId

from auth import hash_password, verify_password, create_access_token, decode_access_token, generate_ingestion_key
from db import get_db

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# Create the main app
app = FastAPI()
api_router = APIRouter(prefix="/api")
security = HTTPBearer(auto_error=False)

# Models
class SignupRequest(BaseModel):
    name: str
    email: EmailStr
    password: str

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class AuthResponse(BaseModel):
    token: str
    user: Dict[str, Any]

class UserResponse(BaseModel):
    id: str
    name: str
    email: str
    ingestion_key: str

class IngestEvent(BaseModel):
    run_id: str
    agent_name: str
    parent_step_id: Optional[str] = None
    status: str
    prompt: str = ""
    output: str = ""
    latency_ms: int = 0
    cost: float = 0.0
    tokens: int = 0
    claimed_actions: List[str] = []
    actual_actions: List[str] = []
    error_message: Optional[str] = None

class Run(BaseModel):
    id: str
    run_id: str
    user_id: str
    status: str
    total_steps: int
    success_steps: int
    failed_steps: int
    duration_ms: int
    cost: float
    integrity_score: float
    summary: str
    created_at: str

class Step(BaseModel):
    id: str
    run_id: str
    user_id: str
    agent_name: str
    parent_step_id: Optional[str] = None
    status: str
    prompt: str
    output: str
    latency_ms: int
    cost: float
    tokens: int
    claimed_actions: List[str]
    actual_actions: List[str]
    hallucination_flags: List[str]
    error_message: Optional[str] = None
    created_at: str

# Helper: Get current user from JWT
async def get_current_user(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)) -> Optional[Dict[str, Any]]:
    if not credentials:
        return None
    
    user_id = decode_access_token(credentials.credentials)
    if not user_id:
        return None
    
    db = get_db()
    user = await db.users.find_one({"_id": ObjectId(user_id)})
    if not user:
        return None
    
    user["id"] = str(user["_id"])
    return user

async def require_auth(user: Optional[Dict[str, Any]] = Depends(get_current_user)) -> Dict[str, Any]:
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user

# Helper: Detect hallucinations
def detect_hallucinations(step: Dict[str, Any]) -> List[str]:
    flags = []
    
    claimed = step.get("claimed_actions", [])
    actual = step.get("actual_actions", [])
    output = step.get("output", "")
    
    # TOOL_NOT_AVAILABLE
    if claimed:
        for c in claimed:
            if c not in actual:
                flags.append("TOOL_NOT_AVAILABLE")
                break
    
    # CLAIMED_WITHOUT_ACTION
    completion_patterns = ["done", "completed", "updated", "task finished", "successfully"]
    if output and any(pattern in output.lower() for pattern in completion_patterns):
        if not actual or len(actual) == 0:
            flags.append("CLAIMED_WITHOUT_ACTION")
    
    return flags

# Auth Routes
@api_router.post("/auth/signup", response_model=AuthResponse)
async def signup(req: SignupRequest):
    db = get_db()
    
    # Check if user exists
    existing = await db.users.find_one({"email": req.email})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Create user
    user_doc = {
        "name": req.name,
        "email": req.email,
        "password_hash": hash_password(req.password),
        "ingestion_key": generate_ingestion_key(),
        "created_at": datetime.now(timezone.utc)
    }
    
    result = await db.users.insert_one(user_doc)
    user_id = str(result.inserted_id)
    
    # Create token
    token = create_access_token(user_id)
    
    return {
        "token": token,
        "user": {
            "id": user_id,
            "name": req.name,
            "email": req.email,
            "ingestion_key": user_doc["ingestion_key"]
        }
    }

@api_router.post("/auth/login", response_model=AuthResponse)
async def login(req: LoginRequest):
    db = get_db()
    
    # Find user
    user = await db.users.find_one({"email": req.email})
    if not user or not verify_password(req.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    user_id = str(user["_id"])
    token = create_access_token(user_id)
    
    return {
        "token": token,
        "user": {
            "id": user_id,
            "name": user["name"],
            "email": user["email"],
            "ingestion_key": user["ingestion_key"]
        }
    }

@api_router.get("/auth/me", response_model=UserResponse)
async def get_me(user: Dict[str, Any] = Depends(require_auth)):
    return {
        "id": user["id"],
        "name": user["name"],
        "email": user["email"],
        "ingestion_key": user["ingestion_key"]
    }

# Ingestion Route (multi-tenant with key)
@api_router.post("/agentdog/event")
async def ingest_event(event: IngestEvent, key: str = Query(...)):
    db = get_db()
    
    # Find user by ingestion key
    user = await db.users.find_one({"ingestion_key": key})
    if not user:
        raise HTTPException(status_code=401, detail="Invalid ingestion key")
    
    user_id = str(user["_id"])
    
    # Detect hallucinations
    step_dict = event.model_dump()
    step_dict["hallucination_flags"] = detect_hallucinations(step_dict)
    step_dict["user_id"] = user_id
    step_dict["created_at"] = datetime.now(timezone.utc)
    
    # Upsert run
    run = await db.runs.find_one({"user_id": user_id, "run_id": event.run_id})
    if not run:
        run = {
            "user_id": user_id,
            "run_id": event.run_id,
            "status": "running",
            "total_steps": 0,
            "success_steps": 0,
            "failed_steps": 0,
            "duration_ms": 0,
            "cost": 0.0,
            "integrity_score": 1.0,
            "summary": "",
            "created_at": datetime.now(timezone.utc)
        }
        await db.runs.insert_one(run)
    
    # Insert step
    await db.steps.insert_one(step_dict)
    
    # Update run stats
    steps = await db.steps.find({"user_id": user_id, "run_id": event.run_id}).to_list(1000)
    
    total = len(steps)
    success = sum(1 for s in steps if s.get("status") == "success")
    failed = sum(1 for s in steps if s.get("status") == "error")
    total_duration = sum(s.get("latency_ms", 0) for s in steps)
    total_cost = sum(s.get("cost", 0) for s in steps)
    hallucinated = sum(1 for s in steps if s.get("hallucination_flags"))
    integrity = 1.0 - (hallucinated / total) if total > 0 else 1.0
    
    status = "running"
    if total > 0:
        if failed > 0:
            status = "error"
        elif all(s.get("status") in ["success", "error"] for s in steps):
            status = "success"
    
    await db.runs.update_one(
        {"user_id": user_id, "run_id": event.run_id},
        {"$set": {
            "total_steps": total,
            "success_steps": success,
            "failed_steps": failed,
            "duration_ms": total_duration,
            "cost": total_cost,
            "integrity_score": round(integrity, 2),
            "status": status
        }}
    )
    
    return {"ok": True}

# Read Routes (user-scoped)
@api_router.get("/runs")
async def get_runs(user: Dict[str, Any] = Depends(require_auth)):
    db = get_db()
    runs = await db.runs.find({"user_id": user["id"]}).sort("created_at", -1).to_list(100)
    
    for run in runs:
        run["id"] = str(run["_id"])
        run["created_at"] = run["created_at"].isoformat()
        del run["_id"]
    
    return runs

@api_router.get("/run/{run_id}")
async def get_run(run_id: str, user: Dict[str, Any] = Depends(require_auth)):
    db = get_db()
    run = await db.runs.find_one({"user_id": user["id"], "run_id": run_id})
    
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    
    run["id"] = str(run["_id"])
    run["created_at"] = run["created_at"].isoformat()
    del run["_id"]
    
    return run

@api_router.get("/run/{run_id}/steps")
async def get_run_steps(run_id: str, user: Dict[str, Any] = Depends(require_auth)):
    db = get_db()
    steps = await db.steps.find({"user_id": user["id"], "run_id": run_id}).to_list(1000)
    
    for step in steps:
        step["id"] = str(step["_id"])
        step["created_at"] = step["created_at"].isoformat()
        del step["_id"]
    
    return steps

@api_router.get("/step/{step_id}")
async def get_step(step_id: str, user: Dict[str, Any] = Depends(require_auth)):
    db = get_db()
    step = await db.steps.find_one({"user_id": user["id"], "_id": ObjectId(step_id)})
    
    if not step:
        raise HTTPException(status_code=404, detail="Step not found")
    
    step["id"] = str(step["_id"])
    step["created_at"] = step["created_at"].isoformat()
    del step["_id"]
    
    return step

@api_router.post("/summary/{run_id}")
async def generate_summary(run_id: str, user: Dict[str, Any] = Depends(require_auth)):
    db = get_db()
    
    run = await db.runs.find_one({"user_id": user["id"], "run_id": run_id})
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    
    steps = await db.steps.find({"user_id": user["id"], "run_id": run_id}).to_list(1000)
    
    step_summaries = [
        {
            "agent": step["agent_name"],
            "status": step["status"],
            "output": step["output"][:200],
            "error": step.get("error_message", "")
        }
        for step in steps
    ]
    
    try:
        chat = LlmChat(
            api_key=os.environ.get('EMERGENT_LLM_KEY'),
            session_id=f"summary-{run_id}",
            system_message="You are an AI observability assistant. Summarize multi-agent runs concisely."
        ).with_model("anthropic", "claude-4-sonnet-20250514")
        
        prompt = f"""Summarize this multi-agent run. Mention which agents ran, which failed, any retries, and overall outcome.

Run ID: {run_id}
Status: {run['status']}
Total Steps: {run['total_steps']}
Failed: {run['failed_steps']}

Steps:
{json.dumps(step_summaries, indent=2)}

Provide a brief 2-3 sentence summary."""
        
        user_message = UserMessage(text=prompt)
        response = await chat.send_message(user_message)
        
        await db.runs.update_one(
            {"user_id": user["id"], "run_id": run_id},
            {"$set": {"summary": response}}
        )
        
        return {"summary": response}
    
    except Exception as e:
        logging.error(f"Error generating summary: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate summary: {str(e)}")

# Include router
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
