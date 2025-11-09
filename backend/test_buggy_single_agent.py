"""
Test Single Agent with Intentional Bugs

This agent has multiple intentional bugs to test the coordination failure detection:
1. HALLUCINATION: Claims to use invalid model (gpt-5)
2. HALLUCINATION: References non-existent API endpoint
3. LOGICAL_INCONSISTENCY: Token counts don't add up
4. LOGICAL_INCONSISTENCY: Marks as success but has error message
5. MISSING_CONTEXT: Makes claims not backed by input
6. CONTRACT_VIOLATION: Exceeds duration limits
"""

import asyncio
import os
import time
from datetime import datetime, timezone
from typing import Optional
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


class BuggySummarizerAgent:
    """Single agent with multiple intentional bugs for testing"""
    
    def __init__(self, run_id: str):
        self.run_id = run_id
        self.agentdog = AgentDog(api_url="http://localhost:8001/api")
        self.tracer = ObservabilityTracer(run_id=run_id)
        
    async def summarize_text(self, user_text: str) -> dict:
        """Summarize text with intentional bugs"""
        agent_name = "buggy_summarizer"
        
        print(f"\n{'='*60}")
        print(f"Buggy Summarizer Agent: {self.run_id}")
        print(f"Text: {user_text[:50]}...")
        print(f"{'='*60}\n")
        
        # Start root span
        root_span = self.tracer.start_root_span(
            name="buggy_summarizer_workflow",
            metadata={"workflow_type": "test_buggy", "text_length": len(user_text)}
        )
        root_span.input_data = user_text
        
        # Create agent span
        agent_span = self.tracer.start_span(
            name=agent_name,
            span_type=SpanType.AGENT,
            parent_span_id=root_span.span_id,
            metadata={"agent_type": "summarizer"}
        )
        agent_span.input_data = user_text
        
        start_time = time.time()
        
        # BUG 1: Create LLM span with INVALID MODEL (gpt-5 doesn't exist)
        llm_span = self.tracer.start_span(
            name="gpt5_summarization",  # Invalid model
            span_type=SpanType.LLM_CALL,
            parent_span_id=agent_span.span_id,
            metadata={"model": "gpt-5"}  # HALLUCINATION: Invalid model
        )
        llm_span.input_data = user_text
        
        # Simulate processing (make it take longer than allowed)
        await asyncio.sleep(2.0)
        
        # Generate fake summary with bugs
        summary = """Summary of the text:

This analysis was performed using our advanced /api/magic-summarize endpoint which doesn't exist.

Key findings based on the detailed market research data:
- Point 1: Something that wasn't in the input
- Point 2: Another claim without basis
- Point 3: According to the competitor analysis we never did

BUG: This text references data that was never provided in the input!"""
        
        # BUG 2: Token counts don't add up (LOGICAL_INCONSISTENCY)
        input_tokens = 50
        output_tokens = 30
        total_tokens = 100  # Should be 80, not 100!
        
        # BUG 3: Add LLM details with invalid model and wrong token math
        llm_span.output_data = summary
        llm_span.add_llm_details(
            model="gpt-5",  # HALLUCINATION: This model doesn't exist
            tokens_input=input_tokens,
            tokens_output=output_tokens,
            cost_usd=0.005
        )
        llm_span.tokens_total = total_tokens  # Manually set wrong total
        
        # BUG 4: Mark LLM as success
        self.tracer.end_span(llm_span.span_id, SpanStatus.SUCCESS)
        
        duration_ms = int((time.time() - start_time) * 1000)
        
        # Emit event to AgentDog
        agent_id = self.agentdog.emit_event(
            run_id=self.run_id,
            agent_name=agent_name,
            status="success",
            prompt=user_text[:500],
            output=summary[:1000],
            tokens=total_tokens,
            cost_usd=0.005,
            latency_ms=duration_ms,
            parent_step_id=None
        )
        
        # BUG 5: Mark agent as SUCCESS but add error message (LOGICAL_INCONSISTENCY)
        agent_span.output_data = summary
        agent_span.error = "KeyError: missing validation field"  # Has error but marked success
        self.tracer.end_span(agent_span.span_id, SpanStatus.SUCCESS)  # Inconsistent!
        
        # Complete root span
        root_span.output_data = summary
        self.tracer.end_span(root_span.span_id, SpanStatus.SUCCESS)
        
        print(f"[{agent_name}] Completed with intentional bugs")
        
        return {
            "response": summary,
            "trace": self.tracer.get_trace(),
            "agent_id": agent_id
        }


async def test_buggy_agent():
    """Test function to run the buggy agent"""
    run_id = f"test-buggy-{int(time.time())}"
    agent = BuggySummarizerAgent(run_id)
    
    test_text = "Analyze the quarterly sales performance and provide insights."
    
    result = await agent.summarize_text(test_text)
    
    print("\n" + "="*60)
    print("BUGGY AGENT TEST COMPLETE")
    print("="*60)
    print(f"Run ID: {run_id}")
    print("\nExpected Failures:")
    print("1. HALLUCINATION: Invalid model 'gpt-5'")
    print("2. HALLUCINATION: References /api/magic-summarize")
    print("3. LOGICAL_INCONSISTENCY: Token math (50+30≠100)")
    print("4. LOGICAL_INCONSISTENCY: Success status with error message")
    print("5. MISSING_CONTEXT: Claims about 'market research' not in input")
    print("6. MISSING_CONTEXT: References 'competitor analysis' not provided")
    
    return result


if __name__ == "__main__":
    asyncio.run(test_buggy_agent())
