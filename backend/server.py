from fastapi import FastAPI, APIRouter, HTTPException, Depends, Request, Query
from fastapi.responses import HTMLResponse
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

# MongoDB Viewer Route
@api_router.get("/mongo-viewer", response_class=HTMLResponse)
async def mongo_viewer():
    from fastapi.responses import HTMLResponse
    import json
    
    # Get all data
    users = await db.users.find({}, {"password_hash": 0}).to_list(100)
    runs = await db.runs.find({}).to_list(100)
    steps = await db.steps.find({}).to_list(100)
    
    def json_serial(obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, ObjectId):
            return str(obj)
        return str(obj)
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>AgentDog MongoDB Viewer</title>
        <style>
            * {{ margin: 0; padding: 0; box-sizing: border-box; }}
            body {{ font-family: 'Inter', -apple-system, sans-serif; background: #f9fafb; padding: 20px; }}
            .container {{ max-width: 1400px; margin: 0 auto; }}
            h1 {{ font-size: 28px; font-weight: 700; color: #0F172A; margin-bottom: 8px; }}
            .subtitle {{ color: #6B7280; margin-bottom: 32px; font-size: 14px; }}
            .stats {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; margin-bottom: 32px; }}
            .stat-card {{ background: white; border: 1px solid #e5e7eb; border-radius: 8px; padding: 20px; }}
            .stat-label {{ font-size: 12px; font-weight: 600; color: #6B7280; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 8px; }}
            .stat-value {{ font-size: 32px; font-weight: 700; color: #0F172A; }}
            .section {{ background: white; border: 1px solid #e5e7eb; border-radius: 8px; padding: 24px; margin-bottom: 24px; }}
            .section-title {{ font-size: 16px; font-weight: 600; color: #0F172A; margin-bottom: 16px; padding-bottom: 12px; border-bottom: 1px solid #e5e7eb; }}
            .json-container {{ background: #f9fafb; border: 1px solid #e5e7eb; border-radius: 6px; padding: 16px; overflow-x: auto; max-height: 400px; overflow-y: auto; }}
            pre {{ margin: 0; font-family: 'SF Mono', 'Courier New', monospace; font-size: 13px; line-height: 1.6; color: #374151; }}
            .badge {{ display: inline-block; padding: 4px 8px; border-radius: 4px; font-size: 11px; font-weight: 600; }}
            .badge-success {{ background: #DEF7EC; color: #03543F; }}
            .badge-error {{ background: #FDE8E8; color: #9B1C1C; }}
            .refresh-btn {{ background: #2563EB; color: white; border: none; padding: 8px 16px; border-radius: 6px; font-size: 14px; font-weight: 500; cursor: pointer; float: right; }}
            .refresh-btn:hover {{ background: #1D4ED8; }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 16px; }}
            th, td {{ text-align: left; padding: 12px; border-bottom: 1px solid #e5e7eb; font-size: 13px; }}
            th {{ font-weight: 600; color: #6B7280; background: #f9fafb; }}
            td {{ color: #374151; }}
            .code {{ font-family: 'SF Mono', monospace; background: #f3f4f6; padding: 2px 6px; border-radius: 4px; font-size: 12px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>AgentDog MongoDB Viewer</h1>
            <p class="subtitle">Live view of your AgentDog database</p>
            <button class="refresh-btn" onclick="location.reload()">Refresh</button>
            
            <div class="stats">
                <div class="stat-card"><div class="stat-label">Total Users</div><div class="stat-value">{len(users)}</div></div>
                <div class="stat-card"><div class="stat-label">Total Runs</div><div class="stat-value">{len(runs)}</div></div>
                <div class="stat-card"><div class="stat-label">Total Steps</div><div class="stat-value">{len(steps)}</div></div>
            </div>
            
            <div class="section">
                <div class="section-title">👥 Users ({len(users)})</div>
                <table><thead><tr><th>Name</th><th>Email</th><th>Ingestion Key</th><th>Created</th></tr></thead><tbody>
                {"".join([f'<tr><td>{u.get("name")}</td><td>{u.get("email")}</td><td><span class="code">{u.get("ingestion_key", "")[:16]}...</span></td><td>{str(u.get("created_at", ""))[:19]}</td></tr>' for u in users])}
                </tbody></table>
            </div>
            
            <div class="section">
                <div class="section-title">🏃 Runs ({len(runs)})</div>
                <table><thead><tr><th>Run ID</th><th>Status</th><th>Steps</th><th>Success</th><th>Failed</th><th>Integrity</th><th>Cost</th></tr></thead><tbody>
                {"".join([f'<tr><td><span class="code">{r.get("run_id")}</span></td><td><span class="badge badge-{r.get("status")}">{r.get("status", "").upper()}</span></td><td>{r.get("total_steps")}</td><td>{r.get("success_steps")}</td><td>{r.get("failed_steps")}</td><td>{r.get("integrity_score", 0):.2f}</td><td>${r.get("cost", 0):.3f}</td></tr>' for r in runs])}
                </tbody></table>
            </div>
            
            <div class="section">
                <div class="section-title">🔧 Steps ({len(steps)})</div>
                <div class="json-container"><pre>{json.dumps(steps, indent=2, default=json_serial)}</pre></div>
            </div>
        </div>
    </body>
    </html>
    """
    return HTMLResponse(content=html)

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
