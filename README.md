AgentLens

Observability for AI agents. Think Datadog, but for multi-agent systems.

## What it does

- Watch your agents execute in real-time
- See the full trace of who called who
- Catch when agents hallucinate or break coordination
- Track tokens, costs, and latency per agent
- Chat with different multi-agent systems

## Setup

You need Python 3.10+, Node 18+, MongoDB, and an OpenAI API key.

### Backend

```
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Create `backend/.env`:
```
OPENAI_API_KEY=your-key-here
MONGO_URL=mongodb://localhost:27017
DB_NAME=agentdog
CORS_ORIGINS=http://localhost:3000
```

Start MongoDB, then run:
```
uvicorn server:app --host 0.0.0.0 --port 8001 --reload
```

### Frontend

```
cd frontend
echo "REACT_APP_BACKEND_URL=http://localhost:8001" > .env
npm install --legacy-peer-deps
npm start
```

Open http://localhost:3000

## Project layout

```
backend/
  server.py              - main API
  llm_client.py          - OpenAI wrapper
  agentdog_sdk.py        - SDK to instrument your agents
  observability_tracer.py - tracing spans
  coordination_failure_detector.py - catches agent failures
  debate_multiagent_system.py - debate agent
  social_media_multiagent_system.py - content creator agent

frontend/
  src/App.js             - main UI
  src/components/TraceTimeline.js - execution visualization
  src/components/CoordinationAnalysis.js - failure analysis
```

## Using the SDK

Add observability to your own agents:

```python
from agentdog_sdk import AgentDog

agentdog = AgentDog(api_url="http://localhost:8001/api")

agentdog.emit_event(
    run_id="my-workflow-001",
    agent_name="my_agent",
    status="success",
    prompt="what the agent received",
    output="what it produced",
    tokens=250,
    cost_usd=0.005,
    latency_ms=1200
)
```

## Built with

Python, FastAPI, MongoDB, React, OpenAI
