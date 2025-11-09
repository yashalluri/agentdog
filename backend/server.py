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
import random

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# Create the main app without a prefix
app = FastAPI()

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# In-memory storage (easily swappable to MongoDB)
class InMemoryStore:
    def __init__(self):
        self.runs: Dict[str, Dict[str, Any]] = {}
        self.steps: Dict[str, Dict[str, Any]] = {}
    
    def add_run(self, run_data: Dict[str, Any]):
        self.runs[run_data['id']] = run_data
    
    def get_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        return self.runs.get(run_id)
    
    def get_all_runs(self) -> List[Dict[str, Any]]:
        return list(self.runs.values())
    
    def add_step(self, step_data: Dict[str, Any]):
        self.steps[step_data['id']] = step_data
    
    def get_step(self, step_id: str) -> Optional[Dict[str, Any]]:
        return self.steps.get(step_id)
    
    def get_steps_by_run(self, run_id: str) -> List[Dict[str, Any]]:
        return [step for step in self.steps.values() if step['run_id'] == run_id]
    
    def update_step(self, step_id: str, updates: Dict[str, Any]):
        if step_id in self.steps:
            self.steps[step_id].update(updates)

store = InMemoryStore()

# Models
class Run(BaseModel):
    id: str
    title: str
    start_time: str
    status: str  # "running" | "success" | "error"
    num_steps: int
    num_success: int
    num_failed: int
    duration: float
    cost: float
    integrity_score: Optional[float] = None

class AgentStep(BaseModel):
    id: str
    run_id: str
    parent_step_id: Optional[str] = None
    name: str
    status: str  # "running" | "success" | "error"
    latency_ms: int
    cost: float
    prompt: str
    output: str
    tokens: int
    claimed_actions: Optional[List[str]] = []
    actual_actions: Optional[List[str]] = []
    hallucination_flags: Optional[List[str]] = []

class SummaryResponse(BaseModel):
    summary: str

class VerificationResponse(BaseModel):
    is_truthful: bool
    reason: str
    updated_flags: List[str]

class SystemStats(BaseModel):
    runs_over_time: List[Dict[str, Any]]
    avg_latency: List[Dict[str, Any]]
    success_failure_rate: Dict[str, Any]
    cost_per_run: List[Dict[str, Any]]

class HallucinationStats(BaseModel):
    integrity_over_time: List[Dict[str, Any]]
    top_hallucinating_agents: List[Dict[str, Any]]
    hallucination_rate: float
    agent_stats: List[Dict[str, Any]]

# Helper functions
def compute_hallucination_flags(step: Dict[str, Any]) -> List[str]:
    """Compute hallucination flags for a step"""
    flags = []
    claimed = set(step.get('claimed_actions', []))
    actual = set(step.get('actual_actions', []))
    output = step.get('output', '').lower()
    
    # TOOL_NOT_AVAILABLE
    for tool in claimed:
        if tool not in actual and tool not in ['read', 'write', 'api_call']:  # Simplified capability check
            flags.append('TOOL_NOT_AVAILABLE')
            break
    
    # CLAIMED_WITHOUT_ACTION
    completion_words = ['done', 'completed', 'updated', 'finished', 'success']
    if any(word in output for word in completion_words) and len(actual) == 0:
        flags.append('CLAIMED_WITHOUT_ACTION')
    
    return flags

def compute_integrity_score(run_id: str) -> float:
    """Compute integrity score for a run"""
    steps = store.get_steps_by_run(run_id)
    if not steps:
        return 1.0
    
    total_steps = len(steps)
    hallucinated_steps = sum(1 for step in steps if step.get('hallucination_flags', []))
    
    return 1.0 - (hallucinated_steps / total_steps) if total_steps > 0 else 1.0

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
            "prompt": step['prompt'][:300],
            "output": step['output'][:300],
            "latency_ms": step['latency_ms'],
            "cost": step['cost']
        })
    
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

@api_router.post("/verify_step/{step_id}", response_model=VerificationResponse)
async def verify_step(step_id: str):
    """Verify step integrity using Claude Sonnet 4"""
    step = store.get_step(step_id)
    if not step:
        raise HTTPException(status_code=404, detail="Step not found")
    
    try:
        chat = LlmChat(
            api_key=os.environ.get('EMERGENT_LLM_KEY'),
            session_id=f"verify-{step_id}",
            system_message="You are an AI integrity verifier. Analyze agent outputs and actions to detect discrepancies."
        ).with_model("anthropic", "claude-4-sonnet-20250514")
        
        verify_prompt = f"""Given this agent's output and actual actions, did it truthfully report what it did?

Agent: {step['name']}
Output: {step['output']}
Claimed Actions: {step.get('claimed_actions', [])}
Actual Actions: {step.get('actual_actions', [])}

Answer with 'yes' or 'no' and provide a brief reason (max 50 words)."""
        
        user_message = UserMessage(text=verify_prompt)
        response = await chat.send_message(user_message)
        
        is_truthful = 'yes' in response.lower()[:10]
        flags = list(step.get('hallucination_flags', []))
        
        if not is_truthful and 'LLM_VERIFIER_NO' not in flags:
            flags.append('LLM_VERIFIER_NO')
            store.update_step(step_id, {'hallucination_flags': flags})
        
        return {
            "is_truthful": is_truthful,
            "reason": response,
            "updated_flags": flags
        }
    except Exception as e:
        logging.error(f"Error verifying step: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to verify step: {str(e)}")

@api_router.post("/agentdog/event")
async def ingest_event(event_data: Dict[str, Any]):
    """Generic event ingestion endpoint"""
    # This would normally process real agent events
    # For now, just acknowledge
    return {"message": "Event ingested", "event_id": str(uuid.uuid4())}

@api_router.post("/ingest-sample")
async def ingest_sample_data():
    """Ingest sample data for demonstration"""
    # Clear existing data
    store.runs.clear()
    store.steps.clear()
    
    # Create sample run
    run_id = str(uuid.uuid4())
    
    # Create sample steps with integrity data
    steps_data = [
        {
            "name": "collector",
            "parent_step_id": None,
            "status": "success",
            "latency_ms": 210,
            "cost": 0.002,
            "prompt": "Collect data from sources A, B, and C. Ensure data integrity and validate format.",
            "output": "Successfully collected 3 documents. Total size: 2.4MB. All validations passed.",
            "tokens": 150,
            "claimed_actions": ["read_source_a", "read_source_b", "read_source_c"],
            "actual_actions": ["read_source_a", "read_source_b", "read_source_c"],
        },
        {
            "name": "summarizer-1",
            "parent_step_id": None,
            "status": "success",
            "latency_ms": 320,
            "cost": 0.003,
            "prompt": "Summarize the collected documents focusing on key metrics and insights.",
            "output": "Generated summary with 5 key insights and 12 metrics. Confidence: 0.94",
            "tokens": 420,
            "claimed_actions": ["analyze", "summarize"],
            "actual_actions": ["analyze", "summarize"],
        },
        {
            "name": "summarizer-2",
            "parent_step_id": None,
            "status": "error",
            "latency_ms": 190,
            "cost": 0.001,
            "prompt": "Analyze secondary data sources and extract trends.",
            "output": "Error: Context length exceeded. Unable to process document. I have successfully completed the analysis.",
            "tokens": 80,
            "claimed_actions": ["analyze", "extract_trends"],
            "actual_actions": [],  # Failed, no actions
        },
        {
            "name": "summarizer-2-retry",
            "parent_step_id": None,
            "status": "success",
            "latency_ms": 180,
            "cost": 0.003,
            "prompt": "Analyze secondary data sources with chunking strategy.",
            "output": "Successfully processed with chunking. Identified 8 trends across 3 categories.",
            "tokens": 380,
            "claimed_actions": ["chunk_data", "analyze", "extract_trends"],
            "actual_actions": ["chunk_data", "analyze", "extract_trends"],
        },
        {
            "name": "synthesizer",
            "parent_step_id": None,
            "status": "success",
            "latency_ms": 480,
            "cost": 0.004,
            "prompt": "Synthesize all summaries into a cohesive final report.",
            "output": "Final report generated with executive summary, detailed findings, and recommendations.",
            "tokens": 680,
            "claimed_actions": ["synthesize", "generate_report"],
            "actual_actions": ["synthesize", "generate_report"],
        }
    ]
    
    step_ids = []
    for step_data in steps_data:
        step_id = str(uuid.uuid4())
        step_ids.append(step_id)
        
        # Compute hallucination flags
        flags = compute_hallucination_flags(step_data)
        
        step = {
            "id": step_id,
            "run_id": run_id,
            **step_data,
            "hallucination_flags": flags
        }
        store.add_step(step)
    
    # Compute integrity score
    integrity_score = compute_integrity_score(run_id)
    
    run = {
        "id": run_id,
        "title": "data-sync-2025-11-08-02",
        "start_time": datetime.now(timezone.utc).isoformat(),
        "status": "error",
        "num_steps": 5,
        "num_success": 4,
        "num_failed": 1,
        "duration": 1.38,
        "cost": 0.013,
        "integrity_score": integrity_score
    }
    store.add_run(run)
    
    return {"message": "Sample data ingested successfully", "run_id": run_id}

@api_router.get("/stats/system", response_model=SystemStats)
async def get_system_stats():
    """Get system-wide performance statistics"""
    runs = store.get_all_runs()
    
    # Generate mock time-series data
    runs_over_time = [
        {"timestamp": "2025-11-08T10:00:00Z", "count": 5},
        {"timestamp": "2025-11-08T11:00:00Z", "count": 8},
        {"timestamp": "2025-11-08T12:00:00Z", "count": 6},
        {"timestamp": "2025-11-08T13:00:00Z", "count": 10},
    ]
    
    avg_latency = [
        {"timestamp": "2025-11-08T10:00:00Z", "avg_duration": 1.2},
        {"timestamp": "2025-11-08T11:00:00Z", "avg_duration": 1.5},
        {"timestamp": "2025-11-08T12:00:00Z", "avg_duration": 1.3},
        {"timestamp": "2025-11-08T13:00:00Z", "avg_duration": 1.4},
    ]
    
    total_runs = len(runs)
    success_count = sum(1 for r in runs if r['status'] == 'success')
    failure_count = total_runs - success_count
    
    success_failure_rate = {
        "success": success_count,
        "failure": failure_count,
        "success_rate": (success_count / total_runs * 100) if total_runs > 0 else 0
    }
    
    cost_per_run = [
        {"timestamp": "2025-11-08T10:00:00Z", "total_cost": 0.045},
        {"timestamp": "2025-11-08T11:00:00Z", "total_cost": 0.062},
        {"timestamp": "2025-11-08T12:00:00Z", "total_cost": 0.038},
        {"timestamp": "2025-11-08T13:00:00Z", "total_cost": 0.071},
    ]
    
    return {
        "runs_over_time": runs_over_time,
        "avg_latency": avg_latency,
        "success_failure_rate": success_failure_rate,
        "cost_per_run": cost_per_run
    }

@api_router.get("/stats/hallucination", response_model=HallucinationStats)
async def get_hallucination_stats():
    """Get hallucination detection statistics"""
    all_steps = list(store.steps.values())
    
    # Integrity over time (mock data)
    integrity_over_time = [
        {"timestamp": "2025-11-08T10:00:00Z", "integrity": 0.95},
        {"timestamp": "2025-11-08T11:00:00Z", "integrity": 0.88},
        {"timestamp": "2025-11-08T12:00:00Z", "integrity": 0.92},
        {"timestamp": "2025-11-08T13:00:00Z", "integrity": 0.85},
    ]
    
    # Top hallucinating agents
    agent_hallucination_map = {}
    for step in all_steps:
        agent_name = step['name']
        if agent_name not in agent_hallucination_map:
            agent_hallucination_map[agent_name] = {"total": 0, "hallucinated": 0}
        
        agent_hallucination_map[agent_name]["total"] += 1
        if step.get('hallucination_flags', []):
            agent_hallucination_map[agent_name]["hallucinated"] += 1
    
    top_hallucinating_agents = [
        {
            "agent": name,
            "rate": (stats["hallucinated"] / stats["total"] * 100) if stats["total"] > 0 else 0
        }
        for name, stats in agent_hallucination_map.items()
    ]
    top_hallucinating_agents.sort(key=lambda x: x["rate"], reverse=True)
    
    # Overall hallucination rate
    total_steps = len(all_steps)
    hallucinated_steps = sum(1 for step in all_steps if step.get('hallucination_flags', []))
    hallucination_rate = (hallucinated_steps / total_steps * 100) if total_steps > 0 else 0
    
    # Agent stats table
    agent_stats = [
        {
            "agent": name,
            "total_steps": stats["total"],
            "hallucinated": stats["hallucinated"],
            "rate": (stats["hallucinated"] / stats["total"] * 100) if stats["total"] > 0 else 0
        }
        for name, stats in agent_hallucination_map.items()
    ]
    
    return {
        "integrity_over_time": integrity_over_time,
        "top_hallucinating_agents": top_hallucinating_agents[:5],
        "hallucination_rate": hallucination_rate,
        "agent_stats": agent_stats
    }

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