from fastapi import FastAPI, APIRouter, HTTPException
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime, timezone
from emergentintegrations.llm.chat import LlmChat, UserMessage
import asyncio
import json
from database import (
    connect_to_mongo, 
    close_mongo_connection, 
    get_workflows_collection,
    get_agent_runs_collection
)

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# Create the main app without a prefix
app = FastAPI()

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# Startup and shutdown events
@app.on_event("startup")
async def startup_db_client():
    """Connect to MongoDB on startup"""
    await connect_to_mongo()
    logging.info("AgentDog backend started - MongoDB connected")

@app.on_event("shutdown")
async def shutdown_db_client():
    """Close MongoDB connection on shutdown"""
    await close_mongo_connection()
    logging.info("AgentDog backend shutdown - MongoDB disconnected")

# Pydantic Models for API
class Workflow(BaseModel):
    """Workflow (Run) model matching MongoDB schema"""
    run_id: str
    created_at: str
    updated_at: str
    final_status: str  # "running" | "success" | "error"
    initiator: Optional[str] = None
    summary: Optional[str] = None
    coordination_health: Optional[int] = None
    total_agents: int = 0
    failed_agents: int = 0
    
    # For backwards compatibility with frontend
    @property
    def id(self):
        return self.run_id
    
    @property
    def title(self):
        return self.run_id
    
    @property
    def start_time(self):
        return self.created_at
    
    @property
    def status(self):
        return self.final_status
    
    @property
    def num_steps(self):
        return self.total_agents
    
    @property
    def num_success(self):
        return self.total_agents - self.failed_agents
    
    @property
    def num_failed(self):
        return self.failed_agents
    
    @property
    def duration(self):
        # Calculate from created_at and updated_at
        try:
            created = datetime.fromisoformat(self.created_at.replace('Z', '+00:00'))
            updated = datetime.fromisoformat(self.updated_at.replace('Z', '+00:00'))
            return (updated - created).total_seconds()
        except:
            return 0.0
    
    @property
    def cost(self):
        # Will be calculated from agent runs
        return 0.0

class AgentRun(BaseModel):
    """Agent Run model matching MongoDB schema"""
    run_id: str
    agent_name: str
    parent_step_id: Optional[str] = None
    status: str  # "started" | "success" | "error"
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    latency_ms: Optional[int] = None
    prompt: Optional[str] = None
    output: Optional[str] = None
    tokens: Optional[int] = None
    cost_usd: Optional[float] = None
    error_message: Optional[str] = None
    coordination_status: Optional[str] = None  # "passed" | "failed" | "warning" | null
    coordination_issue: Optional[str] = None
    suggested_fix: Optional[str] = None
    created_at: Optional[str] = None
    
    # For backwards compatibility with frontend
    @property
    def id(self):
        return str(getattr(self, '_id', ''))
    
    @property
    def name(self):
        return self.agent_name
    
    @property
    def cost(self):
        return self.cost_usd or 0.0

class SummaryResponse(BaseModel):
    summary: str

# API Routes
@api_router.get("/runs", response_model=List[Run])
async def get_runs():
    """Get all runs"""
    runs = store.get_all_runs()
    # Sort by start_time descending
    runs.sort(key=lambda x: x['start_time'], reverse=True)
    return runs

@api_router.get("/run/{run_id}", response_model=Run)
async def get_run(run_id: str):
    """Get a specific run by ID"""
    run = store.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return run

@api_router.get("/run/{run_id}/steps", response_model=List[AgentStep])
async def get_run_steps(run_id: str):
    """Get all steps for a specific run"""
    steps = store.get_steps_by_run(run_id)
    return steps

@api_router.get("/step/{step_id}", response_model=AgentStep)
async def get_step(step_id: str):
    """Get detailed information about a specific step"""
    step = store.get_step(step_id)
    if not step:
        raise HTTPException(status_code=404, detail="Step not found")
    return step

@api_router.post("/step/{step_id}/replay")
async def replay_step(step_id: str):
    """Replay a specific agent step"""
    step = store.get_step(step_id)
    if not step:
        raise HTTPException(status_code=404, detail="Step not found")
    
    # Simulate replay: set to running, then success after a delay
    store.update_step(step_id, {"status": "running"})
    
    # Simulate async processing
    async def process_replay():
        await asyncio.sleep(1)
        store.update_step(step_id, {"status": "success"})
    
    asyncio.create_task(process_replay())
    
    return {"message": "Replay initiated", "step_id": step_id}

@api_router.post("/summary/{run_id}", response_model=SummaryResponse)
async def generate_summary(run_id: str):
    """Generate AI summary for a run using Anthropic Claude Sonnet 4"""
    run = store.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    
    steps = store.get_steps_by_run(run_id)
    
    # Build structured agent steps for summary
    agent_steps = []
    for step in steps:
        agent_steps.append({
            "name": step['name'],
            "status": step['status'],
            "prompt": step['prompt'][:300],  # Truncate for brevity
            "output": step['output'][:300],
            "latency_ms": step['latency_ms'],
            "cost": step['cost']
        })
    
    # Use Anthropic Claude Sonnet 4 via Emergent LLM key
    try:
        chat = LlmChat(
            api_key=os.environ.get('EMERGENT_LLM_KEY'),
            session_id=f"summary-{run_id}",
            system_message="You are AgentDog, a reasoning observability assistant. Your job is to analyze multi-agent runs and provide clear, concise summaries."
        ).with_model("anthropic", "claude-4-sonnet-20250514")
        
        summary_prompt = f"""You are AgentDog, a reasoning observability assistant.
Summarize the following multi-agent run concisely.

Run: {run['title']}
Status: {run['status']}
Total Steps: {run['num_steps']}
Succeeded: {run['num_success']}
Failed: {run['num_failed']}

Steps:
{json.dumps(agent_steps, indent=2)}

Provide a concise summary explaining what the agents collectively did, any failures or retries, and the overall outcome."""
        
        user_message = UserMessage(text=summary_prompt)
        
        response = await chat.send_message(user_message)
        
        return {"summary": response}
    except Exception as e:
        logging.error(f"Error generating summary: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate summary: {str(e)}")

@api_router.post("/ingest-sample")
async def ingest_sample_data():
    """Ingest sample data for demonstration"""
    # Clear existing data
    store.runs.clear()
    store.steps.clear()
    
    # Create sample run
    run_id = str(uuid.uuid4())
    run = {
        "id": run_id,
        "title": "data-sync-2025-11-08-02",
        "start_time": datetime.now(timezone.utc).isoformat(),
        "status": "error",
        "num_steps": 5,
        "num_success": 4,
        "num_failed": 1,
        "duration": 1.38,
        "cost": 0.013
    }
    store.add_run(run)
    
    # Create sample steps
    steps = [
        {
            "id": str(uuid.uuid4()),
            "run_id": run_id,
            "parent_step_id": None,
            "name": "collector",
            "status": "success",
            "latency_ms": 210,
            "cost": 0.002,
            "prompt": "Collect data from sources A, B, and C. Ensure data integrity and validate format.",
            "output": "Successfully collected 3 documents. Total size: 2.4MB. All validations passed.",
            "tokens": 150
        },
        {
            "id": str(uuid.uuid4()),
            "run_id": run_id,
            "parent_step_id": None,
            "name": "summarizer-1",
            "status": "success",
            "latency_ms": 320,
            "cost": 0.003,
            "prompt": "Summarize the collected documents focusing on key metrics and insights.",
            "output": "Generated summary with 5 key insights and 12 metrics. Confidence: 0.94",
            "tokens": 420
        },
        {
            "id": str(uuid.uuid4()),
            "run_id": run_id,
            "parent_step_id": None,
            "name": "summarizer-2",
            "status": "error",
            "latency_ms": 190,
            "cost": 0.001,
            "prompt": "Analyze secondary data sources and extract trends.",
            "output": "Error: Context length exceeded. Unable to process document.",
            "tokens": 80
        },
        {
            "id": str(uuid.uuid4()),
            "run_id": run_id,
            "parent_step_id": None,
            "name": "summarizer-2-retry",
            "status": "success",
            "latency_ms": 180,
            "cost": 0.003,
            "prompt": "Analyze secondary data sources with chunking strategy.",
            "output": "Successfully processed with chunking. Identified 8 trends across 3 categories.",
            "tokens": 380
        },
        {
            "id": str(uuid.uuid4()),
            "run_id": run_id,
            "parent_step_id": None,
            "name": "synthesizer",
            "status": "success",
            "latency_ms": 480,
            "cost": 0.004,
            "prompt": "Synthesize all summaries into a cohesive final report.",
            "output": "Final report generated with executive summary, detailed findings, and recommendations.",
            "tokens": 680
        }
    ]
    
    for step in steps:
        store.add_step(step)
    
    return {"message": "Sample data ingested successfully", "run_id": run_id}

# Include the router in the main app
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