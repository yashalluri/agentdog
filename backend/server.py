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

class EventRequest(BaseModel):
    """Request model for telemetry event ingestion"""
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

class EventResponse(BaseModel):
    """Response model for event ingestion"""
    status: str
    agent_id: str

# API Routes
@api_router.get("/runs")
async def get_runs(status: Optional[str] = None, limit: int = 100):
    """Get all workflow runs"""
    workflows_coll = get_workflows_collection()
    
    query = {}
    if status:
        query['final_status'] = status
    
    # Get workflows sorted by created_at descending
    cursor = workflows_coll.find(query).sort('created_at', -1).limit(limit)
    workflows = await cursor.to_list(length=limit)
    
    # Convert MongoDB documents to response format
    result = []
    for wf in workflows:
        # Convert _id to string if needed
        wf['_id'] = str(wf.get('_id', ''))
        
        # Create response with both old and new fields for compatibility
        response_data = {
            "id": wf['run_id'],
            "run_id": wf['run_id'],
            "title": wf['run_id'],
            "start_time": wf['created_at'],
            "created_at": wf['created_at'],
            "updated_at": wf['updated_at'],
            "status": wf['final_status'],
            "final_status": wf['final_status'],
            "num_steps": wf.get('total_agents', 0),
            "total_agents": wf.get('total_agents', 0),
            "num_success": wf.get('total_agents', 0) - wf.get('failed_agents', 0),
            "num_failed": wf.get('failed_agents', 0),
            "failed_agents": wf.get('failed_agents', 0),
            "coordination_health": wf.get('coordination_health'),
            "summary": wf.get('summary'),
            "initiator": wf.get('initiator')
        }
        
        # Calculate duration
        try:
            created = datetime.fromisoformat(wf['created_at'].replace('Z', '+00:00'))
            updated = datetime.fromisoformat(wf['updated_at'].replace('Z', '+00:00'))
            response_data['duration'] = (updated - created).total_seconds()
        except:
            response_data['duration'] = 0.0
        
        # Calculate total cost from agent runs
        agent_runs_coll = get_agent_runs_collection()
        agents = await agent_runs_coll.find({"run_id": wf['run_id']}).to_list(length=None)
        total_cost = sum(agent.get('cost_usd', 0) for agent in agents)
        response_data['cost'] = total_cost
        
        result.append(response_data)
    
    return result

@api_router.get("/run/{run_id}")
async def get_run(run_id: str):
    """Get a specific workflow run by ID"""
    workflows_coll = get_workflows_collection()
    
    workflow = await workflows_coll.find_one({"run_id": run_id})
    if not workflow:
        raise HTTPException(status_code=404, detail="Run not found")
    
    # Convert _id to string
    workflow['_id'] = str(workflow.get('_id', ''))
    
    # Create response with both old and new fields for compatibility
    response_data = {
        "id": workflow['run_id'],
        "run_id": workflow['run_id'],
        "title": workflow['run_id'],
        "start_time": workflow['created_at'],
        "created_at": workflow['created_at'],
        "updated_at": workflow['updated_at'],
        "status": workflow['final_status'],
        "final_status": workflow['final_status'],
        "num_steps": workflow.get('total_agents', 0),
        "total_agents": workflow.get('total_agents', 0),
        "num_success": workflow.get('total_agents', 0) - workflow.get('failed_agents', 0),
        "num_failed": workflow.get('failed_agents', 0),
        "failed_agents": workflow.get('failed_agents', 0),
        "coordination_health": workflow.get('coordination_health'),
        "summary": workflow.get('summary'),
        "initiator": workflow.get('initiator')
    }
    
    # Calculate duration
    try:
        created = datetime.fromisoformat(workflow['created_at'].replace('Z', '+00:00'))
        updated = datetime.fromisoformat(workflow['updated_at'].replace('Z', '+00:00'))
        response_data['duration'] = (updated - created).total_seconds()
    except:
        response_data['duration'] = 0.0
    
    # Calculate total cost
    agent_runs_coll = get_agent_runs_collection()
    agents = await agent_runs_coll.find({"run_id": run_id}).to_list(length=None)
    total_cost = sum(agent.get('cost_usd', 0) for agent in agents)
    response_data['cost'] = total_cost
    
    return response_data

@api_router.get("/run/{run_id}/steps")
async def get_run_steps(run_id: str):
    """Get all agent steps for a specific run"""
    agent_runs_coll = get_agent_runs_collection()
    
    # Get all agents for this run
    cursor = agent_runs_coll.find({"run_id": run_id}).sort('created_at', 1)
    agents = await cursor.to_list(length=None)
    
    # Convert to frontend format
    result = []
    for agent in agents:
        agent['_id'] = str(agent.get('_id', ''))
        
        response_data = {
            "id": agent['_id'],
            "run_id": agent['run_id'],
            "parent_step_id": agent.get('parent_step_id'),
            "name": agent['agent_name'],
            "agent_name": agent['agent_name'],
            "status": agent['status'],
            "latency_ms": agent.get('latency_ms', 0),
            "cost": agent.get('cost_usd', 0),
            "cost_usd": agent.get('cost_usd', 0),
            "prompt": agent.get('prompt', ''),
            "output": agent.get('output', ''),
            "tokens": agent.get('tokens', 0),
            "start_time": agent.get('start_time'),
            "end_time": agent.get('end_time'),
            "error_message": agent.get('error_message'),
            "coordination_status": agent.get('coordination_status'),
            "coordination_issue": agent.get('coordination_issue'),
            "suggested_fix": agent.get('suggested_fix'),
            "created_at": agent.get('created_at')
        }
        result.append(response_data)
    
    return result

@api_router.get("/step/{step_id}")
async def get_step(step_id: str):
    """Get detailed information about a specific step"""
    from bson import ObjectId
    agent_runs_coll = get_agent_runs_collection()
    
    try:
        agent = await agent_runs_coll.find_one({"_id": ObjectId(step_id)})
    except:
        # If not a valid ObjectId, return 404
        raise HTTPException(status_code=404, detail="Step not found")
    
    if not agent:
        raise HTTPException(status_code=404, detail="Step not found")
    
    agent['_id'] = str(agent.get('_id', ''))
    
    response_data = {
        "id": agent['_id'],
        "run_id": agent['run_id'],
        "parent_step_id": agent.get('parent_step_id'),
        "name": agent['agent_name'],
        "agent_name": agent['agent_name'],
        "status": agent['status'],
        "latency_ms": agent.get('latency_ms', 0),
        "cost": agent.get('cost_usd', 0),
        "cost_usd": agent.get('cost_usd', 0),
        "prompt": agent.get('prompt', ''),
        "output": agent.get('output', ''),
        "tokens": agent.get('tokens', 0),
        "start_time": agent.get('start_time'),
        "end_time": agent.get('end_time'),
        "error_message": agent.get('error_message'),
        "coordination_status": agent.get('coordination_status'),
        "coordination_issue": agent.get('coordination_issue'),
        "suggested_fix": agent.get('suggested_fix'),
        "created_at": agent.get('created_at')
    }
    
    return response_data

@api_router.post("/step/{step_id}/replay")
async def replay_step(step_id: str):
    """Replay a specific agent step"""
    from bson import ObjectId
    agent_runs_coll = get_agent_runs_collection()
    
    try:
        agent = await agent_runs_coll.find_one({"_id": ObjectId(step_id)})
    except:
        raise HTTPException(status_code=404, detail="Step not found")
    
    if not agent:
        raise HTTPException(status_code=404, detail="Step not found")
    
    # Simulate replay: set to running, then success after a delay
    await agent_runs_coll.update_one(
        {"_id": ObjectId(step_id)},
        {"$set": {"status": "running", "updated_at": datetime.now(timezone.utc).isoformat()}}
    )
    
    # Simulate async processing
    async def process_replay():
        await asyncio.sleep(1)
        await agent_runs_coll.update_one(
            {"_id": ObjectId(step_id)},
            {"$set": {"status": "success", "updated_at": datetime.now(timezone.utc).isoformat()}}
        )
    
    asyncio.create_task(process_replay())
    
    return {"message": "Replay initiated", "step_id": step_id}

@api_router.post("/summary/{run_id}", response_model=SummaryResponse)
async def generate_summary(run_id: str):
    """Generate AI summary for a run using Anthropic Claude Sonnet 4"""
    workflows_coll = get_workflows_collection()
    agent_runs_coll = get_agent_runs_collection()
    
    workflow = await workflows_coll.find_one({"run_id": run_id})
    if not workflow:
        raise HTTPException(status_code=404, detail="Run not found")
    
    agents = await agent_runs_coll.find({"run_id": run_id}).to_list(length=None)
    
    # Build structured agent steps for summary
    agent_steps = []
    for agent in agents:
        agent_steps.append({
            "name": agent['agent_name'],
            "status": agent['status'],
            "prompt": agent.get('prompt', '')[:300],  # Truncate for brevity
            "output": agent.get('output', '')[:300],
            "latency_ms": agent.get('latency_ms', 0),
            "cost": agent.get('cost_usd', 0)
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

Run: {workflow['run_id']}
Status: {workflow['final_status']}
Total Steps: {workflow.get('total_agents', 0)}
Succeeded: {workflow.get('total_agents', 0) - workflow.get('failed_agents', 0)}
Failed: {workflow.get('failed_agents', 0)}

Steps:
{json.dumps(agent_steps, indent=2)}

Provide a concise summary explaining what the agents collectively did, any failures or retries, and the overall outcome."""
        
        user_message = UserMessage(text=summary_prompt)
        
        response = await chat.send_message(user_message)
        
        # Update workflow with summary
        await workflows_coll.update_one(
            {"run_id": run_id},
            {"$set": {"summary": response, "updated_at": datetime.now(timezone.utc).isoformat()}}
        )
        
        return {"summary": response}
    except Exception as e:
        logging.error(f"Error generating summary: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate summary: {str(e)}")

@api_router.post("/ingest-sample")
async def ingest_sample_data():
    """Ingest sample data for demonstration"""
    workflows_coll = get_workflows_collection()
    agent_runs_coll = get_agent_runs_collection()
    
    # Generate unique run_id
    run_id = f"data-sync-{datetime.now(timezone.utc).strftime('%Y-%m-%d-%H%M%S')}"
    current_time = datetime.now(timezone.utc).isoformat()
    
    # Create sample workflow
    workflow = {
        "run_id": run_id,
        "created_at": current_time,
        "updated_at": current_time,
        "final_status": "error",
        "initiator": "sample_ingestion",
        "summary": None,
        "coordination_health": None,
        "total_agents": 5,
        "failed_agents": 1
    }
    
    # Insert workflow
    await workflows_coll.insert_one(workflow)
    
    # Create sample agent runs
    agents = [
        {
            "run_id": run_id,
            "agent_name": "collector",
            "parent_step_id": None,
            "status": "success",
            "start_time": current_time,
            "end_time": current_time,
            "latency_ms": 210,
            "cost_usd": 0.002,
            "prompt": "Collect data from sources A, B, and C. Ensure data integrity and validate format.",
            "output": "Successfully collected 3 documents. Total size: 2.4MB. All validations passed.",
            "tokens": 150,
            "error_message": None,
            "coordination_status": None,
            "coordination_issue": None,
            "suggested_fix": None,
            "created_at": current_time
        },
        {
            "run_id": run_id,
            "agent_name": "summarizer-1",
            "parent_step_id": None,
            "status": "success",
            "start_time": current_time,
            "end_time": current_time,
            "latency_ms": 320,
            "cost_usd": 0.003,
            "prompt": "Summarize the collected documents focusing on key metrics and insights.",
            "output": "Generated summary with 5 key insights and 12 metrics. Confidence: 0.94",
            "tokens": 420,
            "error_message": None,
            "coordination_status": None,
            "coordination_issue": None,
            "suggested_fix": None,
            "created_at": current_time
        },
        {
            "run_id": run_id,
            "agent_name": "summarizer-2",
            "parent_step_id": None,
            "status": "error",
            "start_time": current_time,
            "end_time": current_time,
            "latency_ms": 190,
            "cost_usd": 0.001,
            "prompt": "Analyze secondary data sources and extract trends.",
            "output": None,
            "tokens": 80,
            "error_message": "Context length exceeded. Unable to process document.",
            "coordination_status": None,
            "coordination_issue": None,
            "suggested_fix": None,
            "created_at": current_time
        },
        {
            "run_id": run_id,
            "agent_name": "summarizer-2-retry",
            "parent_step_id": None,
            "status": "success",
            "start_time": current_time,
            "end_time": current_time,
            "latency_ms": 180,
            "cost_usd": 0.003,
            "prompt": "Analyze secondary data sources with chunking strategy.",
            "output": "Successfully processed with chunking. Identified 8 trends across 3 categories.",
            "tokens": 380,
            "error_message": None,
            "coordination_status": None,
            "coordination_issue": None,
            "suggested_fix": None,
            "created_at": current_time
        },
        {
            "run_id": run_id,
            "agent_name": "synthesizer",
            "parent_step_id": None,
            "status": "success",
            "start_time": current_time,
            "end_time": current_time,
            "latency_ms": 480,
            "cost_usd": 0.004,
            "prompt": "Synthesize all summaries into a cohesive final report.",
            "output": "Final report generated with executive summary, detailed findings, and recommendations.",
            "tokens": 680,
            "error_message": None,
            "coordination_status": None,
            "coordination_issue": None,
            "suggested_fix": None,
            "created_at": current_time
        }
    ]
    
    # Insert all agents
    await agent_runs_coll.insert_many(agents)
    
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