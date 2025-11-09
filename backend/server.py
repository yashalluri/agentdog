from fastapi import FastAPI, APIRouter, HTTPException
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from emergentintegrations.llm.chat import LlmChat, UserMessage
import json

from storage import storage

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# Create the main app
app = FastAPI()
api_router = APIRouter(prefix="/api")

# Models
class IngestEvent(BaseModel):
    run_id: str
    agent_name: str
    parent_step_id: Optional[str] = None
    status: str  # "running", "success", "error"
    prompt: str = ""
    output: str = ""
    latency_ms: int = 0
    cost: float = 0.0
    tokens: int = 0
    claimed_actions: List[str] = []
    actual_actions: List[str] = []
    error_message: Optional[str] = None

class Run(BaseModel):
    run_id: str
    created_at: str
    status: str
    total_steps: int
    success_steps: int
    failed_steps: int
    duration_ms: int
    cost: float
    integrity_score: float
    summary: str

class Step(BaseModel):
    id: str
    run_id: str
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

class SummaryResponse(BaseModel):
    summary: str

# Helper: Detect hallucinations
def detect_hallucinations(step: Dict[str, Any], agent_capabilities: Dict[str, List[str]] = None) -> List[str]:
    """Detect hallucination flags in a step"""
    flags = []
    
    if agent_capabilities is None:
        agent_capabilities = {}
    
    claimed = step.get("claimed_actions", [])
    actual = step.get("actual_actions", [])
    output = step.get("output", "")
    agent_name = step.get("agent_name", "")
    
    # TOOL_NOT_AVAILABLE: claimed tool not in actual and not in capabilities
    if claimed:
        allowed = agent_capabilities.get(agent_name, [])
        for c in claimed:
            if c not in actual:
                # If we have capabilities defined and tool not in them
                if allowed and c not in allowed:
                    flags.append("TOOL_NOT_AVAILABLE")
                    break
    
    # CLAIMED_WITHOUT_ACTION: says completed but no actual actions
    completion_patterns = ["done", "completed", "updated", "task finished", "successfully"]
    if output and any(pattern in output.lower() for pattern in completion_patterns):
        if not actual or len(actual) == 0:
            flags.append("CLAIMED_WITHOUT_ACTION")
    
    return flags

# API Routes

@api_router.post("/agentdog/event")
async def ingest_event(event: IngestEvent):
    """Main ingestion endpoint for agent events"""
    try:
        # Check if run exists, create if not
        run = storage.get_run(event.run_id)
        if not run:
            run = storage.create_run(event.run_id)
        
        # Detect hallucinations
        step_dict = event.model_dump()
        hallucination_flags = detect_hallucinations(step_dict)
        step_dict["hallucination_flags"] = hallucination_flags
        
        # Add step to storage
        storage.add_step(event.run_id, step_dict)
        
        return {"ok": True}
    
    except Exception as e:
        logging.error(f"Error ingesting event: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/runs", response_model=List[Run])
async def get_runs():
    """Get all runs sorted by created_at descending"""
    runs = storage.get_all_runs(sort_by="created_at", descending=True)
    return runs

@api_router.get("/run/{run_id}", response_model=Run)
async def get_run(run_id: str):
    """Get a specific run"""
    run = storage.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return run

@api_router.get("/run/{run_id}/steps", response_model=List[Step])
async def get_run_steps(run_id: str):
    """Get all steps for a run"""
    steps = storage.get_steps(run_id)
    return steps

@api_router.get("/step/{step_id}", response_model=Step)
async def get_step(step_id: str):
    """Get a single step by ID"""
    step = storage.get_step_by_id(step_id)
    if not step:
        raise HTTPException(status_code=404, detail="Step not found")
    return step

@api_router.post("/summary/{run_id}", response_model=SummaryResponse)
async def generate_summary(run_id: str):
    """Generate AI summary for a run using Claude Sonnet 4"""
    run = storage.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    
    steps = storage.get_steps(run_id)
    
    # Build context
    step_summaries = []
    for step in steps:
        step_summaries.append({
            "agent": step["agent_name"],
            "status": step["status"],
            "output": step["output"][:200],
            "error": step.get("error_message", "")
        })
    
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
        
        # Save summary to run
        storage.update_run(run_id, {"summary": response})
        
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