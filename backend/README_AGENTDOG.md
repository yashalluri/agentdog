# AgentDog Integration Guide

## Quick Start

AgentDog automatically captures telemetry from your multi-agent systems with minimal code changes.

### 1. Install Dependencies

```bash
pip install requests langgraph  # or your framework of choice
```

### 2. Get Your Ingestion URL

From AgentDog UI → Settings → Copy your ingestion URL:
```
https://your-agentdog.emergent.run/api/agentdog/event
```

### 3. LangGraph Integration (Automatic)

```python
from agentdog_client import AgentDogClient
from agentdog_langgraph import agentdog_node
import time

# Initialize client
agentdog = AgentDogClient(
    ingestion_url="https://your-agentdog.emergent.run/api/agentdog/event",
    run_id=f"my-workflow-{int(time.time())}"
)

# Decorate your nodes
@agentdog_node(agentdog, "collector")
def collector(state):
    # Your logic here
    return {"docs": ["doc1", "doc2"]}

@agentdog_node(agentdog, "summarizer", parent_step_id="collector")
def summarizer(state):
    # Your logic here
    return {"summary": "Summary text"}

# Build and run your graph normally
# Telemetry is automatically sent to AgentDog!
```

### 4. Manual Integration (Any Framework)

```python
from agentdog_client import AgentDogClient
import time

agentdog = AgentDogClient(
    ingestion_url="https://your-agentdog.emergent.run/api/agentdog/event",
    run_id=f"my-workflow-{int(time.time())}"
)

# Log each agent step
agentdog.log_step(
    agent_name="my_agent",
    status="success",  # or "error", "running"
    prompt="User query: What is the weather?",
    output="It's sunny today",
    parent_step_id=None,  # or parent agent name
    latency_ms=150,
    cost=0.002,
    tokens=50
)
```

## Features

### ✅ Automatic Telemetry
- Node execution status (success/error/running)
- Latency tracking (milliseconds)
- Cost and token tracking
- Parent-child relationships for hierarchical flows

### ✅ Hallucination Detection
AgentDog automatically detects:
- `TOOL_NOT_AVAILABLE`: Agent claims to use unavailable tool
- `CLAIMED_WITHOUT_ACTION`: Agent says "done" but performed no action

### ✅ AI-Powered Insights
- Claude Sonnet 4 summarizes your runs
- Integrity scoring (0.0-1.0)
- Performance analytics

## Advanced: Instrument Entire Graph

```python
from agentdog_langgraph import instrument_langgraph

# Define parent relationships
node_parents = {
    "summarizer": "collector",
    "synthesizer": "collector",
    "validator": "synthesizer"
}

# Automatically wrap all nodes
graph = instrument_langgraph(graph, agentdog, node_parents)
```

## Examples

See `example_langgraph_usage.py` for a complete working example.

## Support

For issues or questions:
- View logs in AgentDog UI
- Check hallucination flags in agent details
- Generate AI summaries for debugging

---

**Pro Tip:** Set `AGENTDOG_URL` environment variable to avoid hardcoding:

```python
import os
agentdog = AgentDogClient(
    ingestion_url=os.getenv("AGENTDOG_URL"),
    run_id="my-run"
)
```
