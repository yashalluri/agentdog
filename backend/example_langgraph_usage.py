"""Example: Using AgentDog with LangGraph

This example shows how to automatically instrument a LangGraph graph
to send telemetry to AgentDog without manual API calls.
"""

from langgraph.graph import StateGraph
from agentdog_client import AgentDogClient
from agentdog_langgraph import agentdog_node, instrument_langgraph
import os
import time

# Configure AgentDog
INGEST_URL = os.getenv("AGENTDOG_URL", "http://localhost:8001/api/agentdog/event")
run_id = f"demo-run-{int(time.time())}"

agentdog = AgentDogClient(ingestion_url=INGEST_URL, run_id=run_id)

# Define sample LangGraph nodes
@agentdog_node(agentdog, "collector")
def collector(state):
    """Collect documents from various sources"""
    return {"docs": ["doc1", "doc2"], **state}

@agentdog_node(agentdog, "summarizer", parent_step_id="collector")
def summarizer(state):
    """Summarize collected documents"""
    return {"summary": f"summarized {len(state['docs'])} docs", **state}

@agentdog_node(agentdog, "synthesizer", parent_step_id="collector")
def synthesizer(state):
    """Synthesize final report"""
    return {"final": f"final report: {state.get('summary', 'N/A')}", **state}

# Build the graph
graph = StateGraph()
graph.add_node("collector", collector)
graph.add_node("summarizer", summarizer)
graph.add_node("synthesizer", synthesizer)
graph.set_entry_point("collector")
graph.add_edge("collector", "summarizer")
graph.add_edge("collector", "synthesizer")

# Instrument the graph (alternative to decorators)
# graph = instrument_langgraph(graph, agentdog, {"summarizer": "collector", "synthesizer": "collector"})

app = graph.compile()

# Run the graph - telemetry automatically sent to AgentDog
if __name__ == "__main__":
    result = app.invoke({"input": "analyze support tickets"})
    print(result)
    print(f"\n✅ Run logged to AgentDog with ID: {run_id}")
