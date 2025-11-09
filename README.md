# 🐕 AgentDog

**Datadog for AI Agents** - A comprehensive monitoring and observability platform for multi-agent AI systems.

## Overview

AgentDog is a telemetry and monitoring solution designed specifically for AI agent workflows. It provides real-time visibility into agent coordination, performance tracking, and failure detection across complex multi-agent systems.

## Features

### 🔍 **Workflow Monitoring**
- Real-time tracking of agent workflows and execution runs
- Visual timeline of agent interactions and dependencies
- Status monitoring (success, error, running)
- Coordination health scoring

### 🤖 **Agent Coordination Analysis**
- Automatic detection of coordination failures
- Parent-child agent relationship tracking
- Error propagation analysis
- Coordination issue identification

### ✨ **AI-Powered Insights**
- Generate intelligent summaries of workflow runs using Claude Sonnet 4
- Automated analysis of agent performance and bottlenecks
- Natural language insights into system behavior

### 📊 **Telemetry & Analytics**
- Event ingestion API for seamless integration
- Performance metrics (duration, cost, token usage)
- Failed agent detection and reporting
- WebSocket real-time updates

### 🔄 **Step Replay**
- Replay individual agent steps for debugging
- Asynchronous replay execution
- Status tracking during replay

## Tech Stack

- **Backend**: FastAPI (Python)
- **Frontend**: React with Tailwind CSS
- **Database**: MongoDB
- **AI Integration**: Claude Sonnet 4 via Emergent Integrations
- **Real-time**: WebSocket support

## Getting Started

### Prerequisites
- Python 3.8+
- Node.js 14+
- MongoDB
- Yarn package manager

### Installation

1. **Backend Setup**
```bash
cd backend
pip install -r requirements.txt
```

2. **Frontend Setup**
```bash
cd frontend
yarn install
```

3. **Environment Configuration**
```bash
# Backend .env
MONGO_URL=<your-mongodb-connection-string>
EMERGENT_LLM_KEY=<your-emergent-llm-key>

# Frontend .env
REACT_APP_BACKEND_URL=<your-backend-url>
```

### Running the Application

**Start Backend:**
```bash
sudo supervisorctl restart backend
```

**Start Frontend:**
```bash
sudo supervisorctl restart frontend
```

**Restart All Services:**
```bash
sudo supervisorctl restart all
```

## API Documentation

### Telemetry Ingestion
```bash
POST /api/event
```
Ingest telemetry events from your AI agents. Supports workflow creation, agent tracking, and coordination analysis.

### Workflow Management
```bash
GET /api/runs              # List all workflow runs
GET /api/run/{run_id}      # Get specific workflow details
GET /api/run/{run_id}/steps  # Get all agent steps in a workflow
```

### AI Features
```bash
POST /api/summary/{run_id}  # Generate AI-powered workflow summary
```

### Testing & Demo
```bash
POST /api/ingest-sample     # Generate sample workflow data
POST /api/step/{step_id}/replay  # Replay a specific agent step
```

## Usage Example

### Ingesting Telemetry Events

```python
import requests

# Create a workflow
event = {
    "event_type": "workflow_start",
    "run_id": "workflow_123",
    "agent_name": "coordinator",
    "status": "success",
    "metadata": {
        "model": "claude-sonnet-4",
        "duration_ms": 1200
    }
}

response = requests.post(
    "http://your-backend-url/api/event",
    json=event
)
```

### Generating AI Summary

```javascript
// Frontend example
const generateSummary = async (runId) => {
  const response = await fetch(
    `${process.env.REACT_APP_BACKEND_URL}/api/summary/${runId}`,
    { method: 'POST' }
  );
  const data = await response.json();
  return data.summary;
};
```

## Key Concepts

### Workflows (Runs)
A workflow represents a complete execution of your multi-agent system. Each workflow has:
- Unique `run_id`
- Status (success, error, running)
- Multiple agent steps
- Coordination health score
- Performance metrics

### Agent Steps
Individual agents within a workflow. Each step tracks:
- Agent name and role
- Input/output data
- Execution status
- Parent agent relationships
- Coordination issues

### Coordination Failure Detection
AgentDog automatically detects coordination failures by analyzing:
- Error patterns in agent outputs
- Missing expected fields
- Agent communication breakdowns
- Dependency failures

## Features in Detail

### Real-Time Updates
AgentDog uses WebSocket connections to provide live updates as your agents execute. No polling required!

### Coordination Health
Automatic scoring (0-100) based on:
- Success rate of agent steps
- Presence of coordination failures
- Error propagation patterns

### Sample Data
Use the "Ingest Sample" button to generate demo workflow data with 5 agents including successful and failed scenarios.

## Development

### Project Structure
```
/app
├── backend/
│   ├── server.py                          # Main FastAPI application
│   ├── database.py                        # MongoDB connection
│   ├── coordination_failure_detector.py   # Failure detection logic
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   └── App.js                        # Main React component
│   └── package.json
└── README.md
```

### Adding New Features

1. Backend endpoints go in `server.py` with `/api` prefix
2. Frontend components in `frontend/src/`
3. Database models defined in Pydantic classes
4. All agent coordination logic in `coordination_failure_detector.py`

## Monitoring Your Agents

AgentDog is designed to integrate seamlessly with your AI agent systems:

1. **Instrument Your Agents**: Add telemetry events at key points in your agent execution
2. **Track Relationships**: Use parent IDs to map agent coordination
3. **Monitor Health**: Review coordination scores and failure patterns
4. **Debug Issues**: Use AI summaries and step replay to understand problems

## Contributing

This is an MVP-level application. Contributions and improvements are welcome!

## License

MIT License

## Support

For issues and questions, please refer to the application documentation or create an issue in the repository.

---

**Built with ❤️ for the AI Agent community**
