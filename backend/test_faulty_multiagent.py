"""
Test Multi-Agent System with Coordination Failures

This system has 3 agents with intentional coordination bugs:
1. Data Collector Agent - Runs but provides minimal data
2. Analyzer Agent - Should run FIRST but doesn't (CONTRACT_VIOLATION)
3. Reporter Agent - Uses data that wasn't produced (MISSING_CONTEXT)

Intentional bugs:
- Wrong execution order (Analyzer should be first)
- Wrong parent relationships (agents not children of root)
- Agents using Sonar model in non-debate workflow (HALLUCINATION)
- Child span longer than parent (LOGICAL_INCONSISTENCY)
- Missing required context between agents
"""

import asyncio
import os
import time
from datetime import datetime, timezone
from typing import Optional, Dict
from dotenv import load_dotenv

load_dotenv()

import sys
sys.path.insert(0, '/app/backend')
from agentdog_sdk import AgentDog
from observability_tracer import (
    ObservabilityTracer,
    SpanType,
    SpanStatus
)


class DataCollectorAgent:
    """Collects data - runs first but shouldn't"""
    
    def __init__(self, run_id: str, agentdog: AgentDog, tracer: ObservabilityTracer):
        self.run_id = run_id
        self.agentdog = agentdog
        self.tracer = tracer
        
    async def collect_data(self, query: str, parent_span_id: str) -> Dict:
        """Collect data with bugs"""
        agent_name = "data_collector"
        
        # BUG: Wrong parent - should be child of root, but we'll make it child of analyzer
        agent_span = self.tracer.start_span(
            name=agent_name,
            span_type=SpanType.AGENT,
            parent_span_id=parent_span_id,  # This will be wrong parent
            metadata={"agent_type": "data_collector"}
        )
        agent_span.input_data = query
        
        start_time = time.time()
        
        # BUG: Use Sonar model in wrong workflow type (HALLUCINATION)
        llm_span = self.tracer.start_span(
            name="sonar_data_collection",
            span_type=SpanType.LLM_CALL,
            parent_span_id=agent_span.span_id,
            metadata={"model": "sonar"}  # Wrong workflow for Sonar!
        )
        llm_span.input_data = query
        
        await asyncio.sleep(1.0)
        
        # Minimal data output (causes MISSING_CONTEXT downstream)
        output = "Data collected: 42 records"
        
        llm_span.output_data = output
        llm_span.add_llm_details(
            model="sonar",  # HALLUCINATION: Sonar in wrong workflow
            tokens_input=20,
            tokens_output=10,
            cost_usd=0.001
        )
        self.tracer.end_span(llm_span.span_id, SpanStatus.SUCCESS)
        
        duration_ms = int((time.time() - start_time) * 1000)
        
        agent_id = self.agentdog.emit_event(
            run_id=self.run_id,
            agent_name=agent_name,
            status="success",
            prompt=query,
            output=output,
            tokens=30,
            cost_usd=0.001,
            latency_ms=duration_ms,
            parent_step_id=None
        )
        
        agent_span.output_data = output
        self.tracer.end_span(agent_span.span_id, SpanStatus.SUCCESS)
        
        return {
            "success": True,
            "data": output,
            "agent_id": agent_id,
            "span_id": agent_span.span_id
        }


class AnalyzerAgent:
    """Analyzes data - should run FIRST per contract but runs second"""
    
    def __init__(self, run_id: str, agentdog: AgentDog, tracer: ObservabilityTracer):
        self.run_id = run_id
        self.agentdog = agentdog
        self.tracer = tracer
        
    async def analyze(self, data: str, parent_span_id: str) -> Dict:
        """Analyze with bugs"""
        agent_name = "analyzer"
        
        agent_span = self.tracer.start_span(
            name=agent_name,
            span_type=SpanType.AGENT,
            parent_span_id=parent_span_id,
            metadata={"agent_type": "analyzer", "must_run_first": True}  # Contract requirement!
        )
        agent_span.input_data = data
        
        # BUG: Child span takes longer than parent will (LOGICAL_INCONSISTENCY)
        # We'll make this take 3 seconds, but parent will be marked as 2 seconds
        llm_span = self.tracer.start_span(
            name="claude_analysis",
            span_type=SpanType.LLM_CALL,
            parent_span_id=agent_span.span_id
        )
        llm_span.input_data = data
        
        await asyncio.sleep(3.5)  # Takes 3.5 seconds
        
        analysis = "Analysis complete: Patterns detected in the comprehensive database."
        
        llm_span.output_data = analysis
        llm_span.add_llm_details(
            model="claude-4-sonnet-20250514",
            tokens_input=50,
            tokens_output=40,
            cost_usd=0.003
        )
        self.tracer.end_span(llm_span.span_id, SpanStatus.SUCCESS)
        
        # BUG: Manually set duration to less than child (LOGICAL_INCONSISTENCY)
        # Child took 3.5s, we'll say parent only took 2s (impossible!)
        agent_span.output_data = analysis
        self.tracer.end_span(agent_span.span_id, SpanStatus.SUCCESS)
        
        # Force override the duration after end_span
        agent_span.duration_ms = 2000  # Parent only 2 seconds
        agent_span.end_time = agent_span.start_time + 2.0  # But child took 3.5!
        
        agent_id = self.agentdog.emit_event(
            run_id=self.run_id,
            agent_name=agent_name,
            status="success",
            prompt=data,
            output=analysis,
            tokens=90,
            cost_usd=0.003,
            latency_ms=2000,  # Wrong duration
            parent_step_id=None
        )
        
        return {
            "success": True,
            "analysis": analysis,
            "agent_id": agent_id,
            "span_id": agent_span.span_id
        }


class ReporterAgent:
    """Creates report - uses data that wasn't produced"""
    
    def __init__(self, run_id: str, agentdog: AgentDog, tracer: ObservabilityTracer):
        self.run_id = run_id
        self.agentdog = agentdog
        self.tracer = tracer
        
    async def create_report(self, analysis: str, parent_span_id: str) -> Dict:
        """Create report with MISSING_CONTEXT bugs"""
        agent_name = "reporter"
        
        agent_span = self.tracer.start_span(
            name=agent_name,
            span_type=SpanType.AGENT,
            parent_span_id=parent_span_id,
            metadata={"agent_type": "reporter"}
        )
        agent_span.input_data = analysis
        
        start_time = time.time()
        
        llm_span = self.tracer.start_span(
            name="claude_report_generation",
            span_type=SpanType.LLM_CALL,
            parent_span_id=agent_span.span_id
        )
        llm_span.input_data = analysis
        
        await asyncio.sleep(1.5)
        
        # BUG: References data that was never collected (MISSING_CONTEXT)
        report = """# Analysis Report

Based on the detailed financial records and customer survey data:

1. Revenue Growth: 23% increase based on Q3 financial data
2. Customer Satisfaction: 4.8/5 rating from survey responses  
3. Market Share: Expanded by 15% according to market research
4. Operational Efficiency: Improved by 18% per the performance metrics

Recommendation: According to the competitor benchmarking analysis, we should invest in AI.

Note: This report references financial data, survey data, market research, performance metrics, 
and competitor benchmarking that were NEVER provided by previous agents!"""
        
        llm_span.output_data = report
        llm_span.add_llm_details(
            model="claude-4-sonnet-20250514",
            tokens_input=60,
            tokens_output=100,
            cost_usd=0.004
        )
        self.tracer.end_span(llm_span.span_id, SpanStatus.SUCCESS)
        
        duration_ms = int((time.time() - start_time) * 1000)
        
        agent_id = self.agentdog.emit_event(
            run_id=self.run_id,
            agent_name=agent_name,
            status="success",
            prompt=analysis,
            output=report,
            tokens=160,
            cost_usd=0.004,
            latency_ms=duration_ms,
            parent_step_id=None
        )
        
        agent_span.output_data = report
        self.tracer.end_span(agent_span.span_id, SpanStatus.SUCCESS)
        
        return {
            "success": True,
            "report": report,
            "agent_id": agent_id,
            "span_id": agent_span.span_id
        }


class FaultyMultiAgentSystem:
    """Multi-agent system with intentional coordination failures"""
    
    def __init__(self, run_id: str):
        self.run_id = run_id
        self.agentdog = AgentDog(api_url="http://localhost:8001/api")
        self.tracer = ObservabilityTracer(run_id=run_id)
        
        self.data_collector = DataCollectorAgent(run_id, self.agentdog, self.tracer)
        self.analyzer = AnalyzerAgent(run_id, self.agentdog, self.tracer)
        self.reporter = ReporterAgent(run_id, self.agentdog, self.tracer)
        
    async def run_analysis(self, query: str) -> dict:
        """Run analysis with intentional bugs"""
        print(f"\n{'='*60}")
        print(f"Faulty Multi-Agent System: {self.run_id}")
        print(f"Query: {query}")
        print(f"{'='*60}\n")
        
        # Start root span
        root_span = self.tracer.start_root_span(
            name="faulty_analysis_workflow",
            metadata={"workflow_type": "test_faulty_multiagent", "query": query}
        )
        root_span.input_data = query
        
        # BUG: Wrong execution order! Data collector runs first but analyzer should run first
        # (CONTRACT_VIOLATION: execution_order)
        print("[BUG] Running data_collector first (should be analyzer per contract)")
        collector_result = await self.data_collector.collect_data(query, root_span.span_id)
        
        print("[BUG] Running analyzer second (should be first per contract)")
        # BUG: Pass wrong parent_span_id to create wrong hierarchy
        analyzer_result = await self.analyzer.analyze(
            collector_result['data'], 
            collector_result['span_id']  # Wrong! Should be root_span.span_id
        )
        
        print("[BUG] Running reporter with missing context")
        reporter_result = await self.reporter.create_report(
            analyzer_result['analysis'],
            root_span.span_id
        )
        
        final_output = reporter_result['report']
        
        # Complete root span
        root_span.output_data = final_output
        self.tracer.end_span(root_span.span_id, SpanStatus.SUCCESS)
        
        print(f"\n{'='*60}")
        print("FAULTY MULTI-AGENT TEST COMPLETE")
        print(f"{'='*60}\n")
        
        return {
            "response": final_output,
            "trace": self.tracer.get_trace()
        }


async def test_faulty_multiagent():
    """Test function to run the faulty multi-agent system"""
    run_id = f"test-faulty-{int(time.time())}"
    system = FaultyMultiAgentSystem(run_id)
    
    query = "Analyze our business performance"
    
    result = await system.run_analysis(query)
    
    print("\n" + "="*60)
    print("EXPECTED COORDINATION FAILURES")
    print("="*60)
    print("\n1. HALLUCINATION:")
    print("   - data_collector uses 'sonar' model (invalid for this workflow)")
    print("\n2. LOGICAL_INCONSISTENCY:")
    print("   - analyzer child span (3s) longer than parent span (2s)")
    print("\n3. MISSING_CONTEXT:")
    print("   - reporter references 'financial records' (not provided)")
    print("   - reporter references 'customer survey data' (not provided)")
    print("   - reporter references 'market research' (not provided)")
    print("   - reporter references 'competitor benchmarking' (not provided)")
    print("\n4. CONTRACT_VIOLATION:")
    print("   - Wrong execution order (collector runs before analyzer)")
    print("   - Wrong parent (analyzer child of collector, not root)")
    print("\n" + "="*60)
    
    return result


if __name__ == "__main__":
    asyncio.run(test_faulty_multiagent())
