from fastapi import FastAPI, APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Set
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
from debate_multiagent_system import DebateMultiAgentSystem

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)

    async def broadcast(self, message: dict):
        """Broadcast message to all connected clients"""
        dead_connections = set()
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except:
                dead_connections.add(connection)
        
        # Clean up dead connections
        self.active_connections -= dead_connections

manager = ConnectionManager()

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

# Coordination Analysis Functions
def quick_coordination_check(error_message: str) -> Optional[str]:
    """
    Phase 1: Quick rule-based coordination check (< 50ms)
    Instantly flags obvious coordination issues without AI
    """
    if not error_message:
        return None
    
    error_lower = error_message.lower()
    
    # Rule 1: KeyError Detection
    if 'keyerror' in error_lower:
        # Try to extract field name
        import re
        match = re.search(r"keyerror[:\s]+['\"]([^'\"]+)['\"]", error_lower)
        if match:
            field_name = match.group(1)
            return f"Missing expected field '{field_name}'"
        return "Missing expected field in data handoff"
    
    # Rule 2: TypeError Detection
    if 'typeerror' in error_lower:
        return "Data type mismatch between agents"
    
    # Rule 3: Timeout Detection
    if 'timeout' in error_lower:
        return "Handoff timeout - agent took too long to respond"
    
    # Rule 4: Default for errors with parent
    return "Coordination failure detected"

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
        total_cost = sum(agent.get('cost_usd') or 0 for agent in agents)
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
    total_cost = sum(agent.get('cost_usd') or 0 for agent in agents)
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
            "prompt": (agent.get('prompt') or '')[:300],  # Truncate for brevity
            "output": (agent.get('output') or '')[:300],
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

@app.websocket("/api/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time agent execution updates"""
    await manager.connect(websocket)
    logging.info("WebSocket client connected")
    try:
        while True:
            # Keep connection alive and handle any messages from client
            data = await websocket.receive_text()
            logging.debug(f"Received from client: {data}")
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        logging.info("WebSocket client disconnected")
    except Exception as e:
        logging.error(f"WebSocket error: {e}")
        manager.disconnect(websocket)

@api_router.post("/event", response_model=EventResponse)
async def receive_event(event: EventRequest):
    """
    Receive telemetry events from instrumented multi-agent systems
    
    Flow:
    1. Store agent run in MongoDB
    2. Create or update workflow record
    3. Phase 1 - Instant Analysis (< 50ms): Quick rule-based checks
    4. Phase 2 - Deep AI Analysis: Queued for background processing (next phase)
    """
    workflows_coll = get_workflows_collection()
    agent_runs_coll = get_agent_runs_collection()
    
    current_time = datetime.now(timezone.utc).isoformat()
    
    # Check if workflow exists, create if not
    workflow = await workflows_coll.find_one({"run_id": event.run_id})
    
    if not workflow:
        # Create new workflow
        workflow_doc = {
            "run_id": event.run_id,
            "created_at": current_time,
            "updated_at": current_time,
            "final_status": "running",
            "initiator": "sdk",
            "summary": None,
            "coordination_health": None,
            "total_agents": 0,
            "failed_agents": 0
        }
        await workflows_coll.insert_one(workflow_doc)
        logging.info(f"Created new workflow: {event.run_id}")
    
    # Create agent run document
    agent_doc = {
        "run_id": event.run_id,
        "agent_name": event.agent_name,
        "parent_step_id": event.parent_step_id,
        "status": event.status,
        "start_time": event.start_time or current_time,
        "end_time": event.end_time,
        "latency_ms": event.latency_ms,
        "prompt": event.prompt,
        "output": event.output,
        "tokens": event.tokens,
        "cost_usd": event.cost_usd,
        "error_message": event.error_message,
        "coordination_status": None,
        "coordination_issue": None,
        "suggested_fix": None,
        "created_at": current_time
    }
    
    # Phase 1: Quick Coordination Check (< 50ms)
    # If agent has parent AND status is "error", run quick check
    if event.parent_step_id and event.status == "error" and event.error_message:
        coordination_issue = quick_coordination_check(event.error_message)
        if coordination_issue:
            agent_doc["coordination_status"] = "failed"
            agent_doc["coordination_issue"] = coordination_issue
            logging.info(f"Quick coordination failure detected: {coordination_issue}")
    
    # Insert agent run
    result = await agent_runs_coll.insert_one(agent_doc)
    agent_id = str(result.inserted_id)
    
    # Broadcast agent event via WebSocket
    asyncio.create_task(manager.broadcast({
        "type": "agent_update",
        "run_id": event.run_id,
        "agent_id": agent_id,
        "agent_name": event.agent_name,
        "status": event.status,
        "parent_step_id": event.parent_step_id,
        "latency_ms": event.latency_ms,
        "error_message": event.error_message,
        "coordination_status": agent_doc.get("coordination_status"),
        "coordination_issue": agent_doc.get("coordination_issue"),
        "timestamp": current_time
    }))
    
    # Update workflow statistics
    update_ops = {
        "$set": {
            "updated_at": current_time
        },
        "$inc": {
            "total_agents": 1
        }
    }
    
    # Update failed count if status is error
    if event.status == "error":
        update_ops["$inc"]["failed_agents"] = 1
    
    # Update workflow status based on agent status
    if event.status == "error":
        update_ops["$set"]["final_status"] = "error"
    elif event.status == "success":
        # Check if all agents are complete
        agents = await agent_runs_coll.find({"run_id": event.run_id}).to_list(length=None)
        all_complete = all(a["status"] in ["success", "error"] for a in agents)
        has_errors = any(a["status"] == "error" for a in agents)
        
        if all_complete:
            update_ops["$set"]["final_status"] = "error" if has_errors else "success"
    
    await workflows_coll.update_one(
        {"run_id": event.run_id},
        update_ops
    )
    
    logging.info(f"Event processed: run_id={event.run_id}, agent={event.agent_name}, status={event.status}")
    
    return EventResponse(status="ok", agent_id=agent_id)

@api_router.post("/run-multiagent-demo")
async def run_multiagent_demo():
    """
    Run a live multi-agent workflow demo with real execution
    This creates a workflow with multiple agents that coordinate and send telemetry
    """
    import time
    import threading
    from agentdog_sdk import AgentDog
    
    # Generate unique run ID
    timestamp = datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')
    run_id = f"live-demo-{timestamp}"
    
    # Run demo workflow in background thread (not async to avoid blocking)
    def run_demo_workflow():
        agentdog = AgentDog(api_url="http://localhost:8001/api")
        
        try:
            # AGENT 1: Query Generator
            start = time.time()
            time.sleep(0.5)
            q_id = agentdog.emit_event(
                run_id=run_id, agent_name="query_generator", status="success",
                prompt="Generate search queries for: AI multi-agent systems",
                output="Generated 3 queries: 1) Latest AI frameworks, 2) Coordination patterns, 3) Agent protocols", 
                tokens=180, cost_usd=0.002,
                latency_ms=int((time.time() - start) * 1000)
            )
            
            # AGENT 2: Web Searcher 1
            start = time.time()
            time.sleep(0.7)
            s1_id = agentdog.emit_event(
                run_id=run_id, agent_name="web_searcher_1", status="success",
                prompt="Search: Latest AI agent frameworks",
                output="Found: LangChain (70k stars), AutoGen, CrewAI are popular frameworks", 
                tokens=220, cost_usd=0.003,
                latency_ms=int((time.time() - start) * 1000), parent_step_id=q_id
            )
            
            # AGENT 3: Web Searcher 2  
            start = time.time()
            time.sleep(0.6)
            s2_id = agentdog.emit_event(
                run_id=run_id, agent_name="web_searcher_2", status="success",
                prompt="Search: Multi-agent coordination patterns",
                output="Found: Hierarchical, peer-to-peer, and blackboard architectures", 
                tokens=190, cost_usd=0.0025,
                latency_ms=int((time.time() - start) * 1000), parent_step_id=q_id
            )
            
            # AGENT 4: Web Searcher 3 (FAILS - Coordination Error)
            start = time.time()
            time.sleep(0.4)
            s3_id = agentdog.emit_event(
                run_id=run_id, agent_name="web_searcher_3", status="error",
                prompt="Search: Agent communication protocols",
                error_message="KeyError: 'search_results' - parent output missing expected field",
                tokens=50, cost_usd=0.001,
                latency_ms=int((time.time() - start) * 1000), parent_step_id=q_id
            )
            
            # AGENT 5: Content Analyzer
            start = time.time()
            time.sleep(0.9)
            a_id = agentdog.emit_event(
                run_id=run_id, agent_name="content_analyzer", status="success",
                prompt="Analyze search results from web searchers",
                output="Analysis complete: Identified 5 key themes, 12 concepts, 3 emerging trends", 
                tokens=380, cost_usd=0.004,
                latency_ms=int((time.time() - start) * 1000), parent_step_id=s2_id
            )
            
            # AGENT 6: Report Writer
            start = time.time()
            time.sleep(1.2)
            agentdog.emit_event(
                run_id=run_id, agent_name="report_writer", status="success",
                prompt="Write final research report on AI multi-agent systems",
                output="Research Report: AI multi-agent systems are rapidly evolving. Frameworks like LangChain enable complex coordination. Future trends include sophisticated protocols.", 
                tokens=520, cost_usd=0.005,
                latency_ms=int((time.time() - start) * 1000), parent_step_id=a_id
            )
            
            logging.info(f"✅ Demo workflow {run_id} completed - 6 agents, 1 failure")
        except Exception as e:
            logging.error(f"❌ Demo workflow {run_id} failed: {e}")
    
    # Start the workflow in a background thread
    thread = threading.Thread(target=run_demo_workflow, daemon=True)
    thread.start()
    
    return {
        "message": "Multi-agent demo started", 
        "run_id": run_id,
        "note": "Watch the agents execute in real-time! Refresh to see updates."
    }

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

class ChatRequest(BaseModel):
    """Request model for chat interaction"""
    run_id: Optional[str] = None
    message: str
    agent_type: str = "default"

class ChatResponse(BaseModel):
    """Response model for chat interaction"""
    run_id: str
    response: str
    agent_name: str

@api_router.post("/chat", response_model=ChatResponse)
async def chat_with_agent(request: ChatRequest):
    """
    Chat with a multi-agent system
    - Creates a new run if run_id is not provided
    - Processes user message with selected agent
    - Stores conversation history
    - Returns agent response
    """
    workflows_coll = get_workflows_collection()
    current_time = datetime.now(timezone.utc).isoformat()
    
    # If no run_id provided, create a new run
    if not request.run_id:
        run_id = f"chat-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"
        
        # Create workflow with 0 steps - will be updated incrementally as agents complete
        workflow_doc = {
            "run_id": run_id,
            "created_at": current_time,
            "updated_at": current_time,
            "final_status": "running",
            "initiator": "chat",
            "summary": None,
            "coordination_health": None,
            "total_agents": 0,
            "succeeded_agents": 0,
            "failed_agents": 0,
            "messages": []  # Store chat messages
        }
        await workflows_coll.insert_one(workflow_doc)
        logging.info(f"Created new chat run: {run_id}")
    else:
        run_id = request.run_id
    
    # Store user message
    user_message = {
        "role": "user",
        "content": request.message,
        "timestamp": current_time
    }
    
    await workflows_coll.update_one(
        {"run_id": run_id},
        {
            "$push": {"messages": user_message},
            "$set": {"updated_at": current_time}
        }
    )
    
    # Process message with selected agent
    try:
        # Check which multi-agent system is selected
        if request.agent_type == "social_media":
            # Use Social Media Multi-Agent System
            try:
                from social_media_multiagent_system import SocialMediaMultiAgentSystem
                
                # Progress callback for status updates
                async def progress_callback(status: str):
                    # Broadcast progress status
                    await manager.broadcast({
                        "type": "debate_progress",
                        "run_id": run_id,
                        "status": status,
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    })
                    
                    # Also broadcast run update to refresh observability
                    await manager.broadcast({
                        "type": "run_update",
                        "run_id": run_id,
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    })
                
                social_media_system = SocialMediaMultiAgentSystem(run_id=run_id, progress_callback=progress_callback)
                social_media_result = await social_media_system.create_content(request.message)
                
                # Extract response and trace
                if isinstance(social_media_result, dict):
                    response_text = social_media_result.get('response', str(social_media_result))
                    detailed_trace = social_media_result.get('trace', None)
                    
                    # Save detailed trace to workflow
                    if detailed_trace:
                        await workflows_coll.update_one(
                            {"run_id": run_id},
                            {"$set": {"detailed_trace": detailed_trace}}
                        )
                else:
                    response_text = str(social_media_result)
                
                citations = []  # Social media doesn't have citations
                
            except Exception as e:
                logging.error(f"Social media system error: {e}")
                response_text = f"I apologize, but I encountered an error with the social media system: {str(e)}"
                citations = []
        
        elif request.agent_type == 'debate':
            # Use debate multi-agent system
            try:
                # Progress callback for status updates and observability
                async def progress_callback(status: str):
                    # Broadcast progress status
                    await manager.broadcast({
                        "type": "debate_progress",
                        "run_id": run_id,
                        "status": status,
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    })
                    
                    # Also broadcast run update to refresh observability
                    await manager.broadcast({
                        "type": "run_update",
                        "run_id": run_id,
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    })
                
                debate_system = DebateMultiAgentSystem(run_id=run_id, progress_callback=progress_callback)
                debate_result = await debate_system.debate_with_user(request.message)
                
                # Extract response, citations, and trace
                if isinstance(debate_result, dict):
                    response_text = debate_result.get('response', str(debate_result))
                    citations = debate_result.get('citations', [])
                    detailed_trace = debate_result.get('trace', None)
                    
                    # Save detailed trace to workflow
                    if detailed_trace:
                        await workflows_coll.update_one(
                            {"run_id": run_id},
                            {"$set": {"detailed_trace": detailed_trace}}
                        )
                else:
                    response_text = str(debate_result)
                    citations = []
                    
            except Exception as e:
                logging.error(f"Debate system error: {e}")
                response_text = f"I apologize, but I encountered an error with the debate system: {str(e)}"
                citations = []
        else:
            # Use default single agent (Claude)
            chat = LlmChat(
                api_key=os.environ.get('EMERGENT_LLM_KEY'),
                session_id=run_id,
                system_message="You are a helpful AI assistant. Provide clear, concise, and helpful responses to user queries."
            ).with_model("anthropic", "claude-4-sonnet-20250514")
            
            # Get conversation history for context
            workflow = await workflows_coll.find_one({"run_id": run_id})
            messages = workflow.get('messages', [])
            
            # Build context from recent messages (last 10)
            context = ""
            if len(messages) > 1:  # More than just the current message
                recent_messages = messages[-11:-1]  # Exclude the current message
                for msg in recent_messages:
                    role = msg['role'].capitalize()
                    context += f"{role}: {msg['content']}\n\n"
            
            # Generate response
            prompt = f"{context}User: {request.message}" if context else request.message
            user_msg = UserMessage(text=prompt)
            response_text = await chat.send_message(user_msg)
            citations = []  # No citations for default agent
        
        # Store assistant response
        assistant_message = {
            "role": "assistant",
            "content": response_text,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "agent_name": f"{request.agent_type}_agent",
            "citations": citations
        }
        
        await workflows_coll.update_one(
            {"run_id": run_id},
            {
                "$push": {"messages": assistant_message},
                "$set": {"updated_at": datetime.now(timezone.utc).isoformat()}
            }
        )
        
        # Broadcast chat update via WebSocket
        asyncio.create_task(manager.broadcast({
            "type": "chat_update",
            "run_id": run_id,
            "message": assistant_message,
            "timestamp": assistant_message["timestamp"]
        }))
        
        return ChatResponse(
            run_id=run_id,
            response=response_text,
            agent_name=f"{request.agent_type}_agent"
        )
        
    except Exception as e:
        logging.error(f"Error processing chat message: {e}")
        
        # Store error message
        error_message = {
            "role": "assistant",
            "content": "I apologize, but I encountered an error processing your message. Please try again.",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "error": True
        }
        
        await workflows_coll.update_one(
            {"run_id": run_id},
            {
                "$push": {"messages": error_message},
                "$set": {"updated_at": datetime.now(timezone.utc).isoformat()}
            }
        )
        
        raise HTTPException(status_code=500, detail=f"Failed to process message: {str(e)}")

@api_router.get("/run/{run_id}/messages")
async def get_run_messages(run_id: str):
    """Get chat messages for a specific run"""
    workflows_coll = get_workflows_collection()
    
    workflow = await workflows_coll.find_one({"run_id": run_id})
    if not workflow:
        raise HTTPException(status_code=404, detail="Run not found")
    
    messages = workflow.get('messages', [])
    
    return {"messages": messages, "run_id": run_id}

@api_router.get("/run/{run_id}/trace")
async def get_run_trace(run_id: str):
    """Get detailed trace/spans for a specific run"""
    workflows_coll = get_workflows_collection()
    
    workflow = await workflows_coll.find_one({"run_id": run_id})
    if not workflow:
        raise HTTPException(status_code=404, detail="Run not found")
    
    # Get detailed trace if available
    trace = workflow.get('detailed_trace', None)
    
    if not trace:
        # Fallback: build basic trace from agent_runs
        agent_runs_coll = get_agent_runs_collection()
        agents = []
        async for agent in agent_runs_coll.find({"workflow_id": run_id}).sort("created_at", 1):
            agents.append({
                "span_id": str(agent['_id']),
                "name": agent['agent_name'],
                "span_type": "agent",
                "status": agent['status'],
                "start_time": agent['created_at'],
                "end_time": agent.get('updated_at'),
                "duration_ms": agent.get('latency_ms'),
                "input": agent.get('prompt', '')[:500],
                "output": agent.get('output', '')[:500],
                "tokens_total": agent.get('tokens'),
                "cost_usd": agent.get('cost_usd'),
                "model": "claude-4-sonnet-20250514",
                "parent_span_id": agent.get('parent_step_id')
            })
        
        trace = {
            "run_id": run_id,
            "spans": agents,
            "total_spans": len(agents)
        }
    
    return trace

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