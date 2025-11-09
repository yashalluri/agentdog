"""
Simple Multi-Agent Demo - Simulated for Testing

This creates a simulated multi-agent workflow to demonstrate AgentDog observability.
No actual LLM calls - just simulated work with realistic telemetry.
"""

import time
import sys
from datetime import datetime, timezone

# Add backend to path to import SDK
sys.path.insert(0, '/app/backend')
from agentdog_sdk import AgentDog


def run_multiagent_workflow():
    """Run a simulated multi-agent workflow"""
    
    # Generate unique run ID
    timestamp = datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')
    run_id = f"research-workflow-{timestamp}"
    
    print(f"\n{'='*70}")
    print(f"🚀 Starting Multi-Agent Research Workflow: {run_id}")
    print(f"{'='*70}\n")
    
    # Initialize AgentDog SDK
    agentdog = AgentDog(api_url="http://localhost:8001/api")
    
    # AGENT 1: Query Generator
    print("[1/6] Query Generator - Starting...")
    start_time = time.time()
    time.sleep(0.5)  # Simulate work
    
    query_generator_id = agentdog.emit_event(
        run_id=run_id,
        agent_name="query_generator",
        status="success",
        prompt="Generate search queries for: AI multi-agent systems",
        output="Generated 3 queries: 1) Latest AI agent frameworks, 2) Multi-agent coordination patterns, 3) Agent communication protocols",
        tokens=180,
        cost_usd=0.002,
        latency_ms=int((time.time() - start_time) * 1000)
    )
    print(f"      ✅ Complete - ID: {query_generator_id}\n")
    
    # AGENT 2: Web Searcher 1
    print("[2/6] Web Searcher 1 - Starting...")
    start_time = time.time()
    time.sleep(0.7)  # Simulate work
    
    searcher1_id = agentdog.emit_event(
        run_id=run_id,
        agent_name="web_searcher_1",
        status="success",
        prompt="Search: Latest AI agent frameworks",
        output="Found: LangChain, AutoGen, CrewAI are popular frameworks. LangChain has 70k+ stars on GitHub.",
        tokens=220,
        cost_usd=0.003,
        latency_ms=int((time.time() - start_time) * 1000),
        parent_step_id=query_generator_id
    )
    print(f"      ✅ Complete - ID: {searcher1_id}\n")
    
    # AGENT 3: Web Searcher 2
    print("[3/6] Web Searcher 2 - Starting...")
    start_time = time.time()
    time.sleep(0.6)  # Simulate work
    
    searcher2_id = agentdog.emit_event(
        run_id=run_id,
        agent_name="web_searcher_2",
        status="success",
        prompt="Search: Multi-agent coordination patterns",
        output="Found: Common patterns include hierarchical, peer-to-peer, and blackboard architectures.",
        tokens=190,
        cost_usd=0.0025,
        latency_ms=int((time.time() - start_time) * 1000),
        parent_step_id=query_generator_id
    )
    print(f"      ✅ Complete - ID: {searcher2_id}\n")
    
    # AGENT 4: Web Searcher 3 (with coordination failure)
    print("[4/6] Web Searcher 3 - Starting...")
    start_time = time.time()
    time.sleep(0.4)  # Simulate work
    
    searcher3_id = agentdog.emit_event(
        run_id=run_id,
        agent_name="web_searcher_3",
        status="error",
        prompt="Search: Agent communication protocols",
        error_message="KeyError: 'search_results' - parent output missing expected field",
        tokens=50,
        cost_usd=0.001,
        latency_ms=int((time.time() - start_time) * 1000),
        parent_step_id=query_generator_id
    )
    print(f"      ❌ Failed - Coordination error detected - ID: {searcher3_id}\n")
    
    # AGENT 5: Content Analyzer
    print("[5/6] Content Analyzer - Starting...")
    start_time = time.time()
    time.sleep(0.9)  # Simulate work
    
    analyzer_id = agentdog.emit_event(
        run_id=run_id,
        agent_name="content_analyzer",
        status="success",
        prompt="Analyze search results from 3 web searchers",
        output="Analysis complete: Identified 5 key themes, 12 important concepts, and 3 emerging trends in AI agent systems.",
        tokens=380,
        cost_usd=0.004,
        latency_ms=int((time.time() - start_time) * 1000),
        parent_step_id=searcher2_id
    )
    print(f"      ✅ Complete - ID: {analyzer_id}\n")
    
    # AGENT 6: Report Writer
    print("[6/6] Report Writer - Starting...")
    start_time = time.time()
    time.sleep(1.2)  # Simulate work
    
    writer_id = agentdog.emit_event(
        run_id=run_id,
        agent_name="report_writer",
        status="success",
        prompt="Write final research report",
        output="Research Report: AI multi-agent systems are rapidly evolving. Key frameworks like LangChain and AutoGen enable complex agent coordination. Future trends point to more sophisticated communication protocols.",
        tokens=520,
        cost_usd=0.005,
        latency_ms=int((time.time() - start_time) * 1000),
        parent_step_id=analyzer_id
    )
    print(f"      ✅ Complete - ID: {writer_id}\n")
    
    print(f"{'='*70}")
    print(f"✅ Multi-Agent Workflow Complete!")
    print(f"{'='*70}")
    print(f"\n🔍 View in AgentDog: https://social-trace-agent.preview.emergentagent.com")
    print(f"   Look for run: {run_id}\n")
    print(f"Summary:")
    print(f"  • Total Agents: 6")
    print(f"  • Successful: 5")
    print(f"  • Failed: 1 (coordination failure detected)")
    print(f"  • Run ID: {run_id}\n")


if __name__ == "__main__":
    run_multiagent_workflow()
