"""
AgentDog SDK - Easy instrumentation for multi-agent systems

Usage:
    from agentdog_sdk import AgentDog
    
    agentdog = AgentDog(api_url="http://localhost:8001/api")
    
    # Start agent
    agent_id = agentdog.emit_event(
        run_id="my-workflow-001",
        agent_name="data_collector",
        status="started",
        prompt="Collect data from sources"
    )
    
    # Complete agent
    agentdog.emit_event(
        run_id="my-workflow-001",
        agent_name="data_collector",
        status="success",
        output="Successfully collected 100 records",
        tokens=250,
        cost_usd=0.005
    )
"""

import requests
import logging
from typing import Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class AgentDog:
    """AgentDog SDK for instrumenting multi-agent systems"""
    
    def __init__(self, api_url: str = "http://localhost:8001/api", timeout: int = 5):
        """
        Initialize AgentDog SDK
        
        Args:
            api_url: Base URL of AgentDog API (default: http://localhost:8001/api)
            timeout: Request timeout in seconds (default: 5)
        """
        self.api_url = api_url.rstrip('/')
        self.timeout = timeout
        self.event_endpoint = f"{self.api_url}/event"
    
    def emit_event(
        self,
        run_id: str,
        agent_name: str,
        status: str,
        prompt: Optional[str] = None,
        output: Optional[str] = None,
        parent_step_id: Optional[str] = None,
        error_message: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        tokens: Optional[int] = None,
        cost_usd: Optional[float] = None,
        latency_ms: Optional[int] = None
    ) -> Optional[str]:
        """
        Emit a telemetry event to AgentDog
        
        Args:
            run_id: Unique identifier for this workflow run
            agent_name: Name of the agent
            status: "started", "success", or "error"
            prompt: Input/prompt to the agent (optional)
            output: Agent's output (optional)
            parent_step_id: ObjectId of parent agent (optional, null for root)
            error_message: Error text if status is "error" (optional)
            start_time: When agent started (ISO format, optional)
            end_time: When agent finished (ISO format, optional)
            tokens: Token count (optional)
            cost_usd: Cost in USD (optional)
            latency_ms: Latency in milliseconds (optional)
        
        Returns:
            agent_id: The ID of the created agent run, or None if failed
        """
        
        # Build event payload
        event_data = {
            "run_id": run_id,
            "agent_name": agent_name,
            "status": status
        }
        
        # Add optional fields
        if prompt:
            event_data["prompt"] = prompt
        if output:
            event_data["output"] = output
        if parent_step_id:
            event_data["parent_step_id"] = parent_step_id
        if error_message:
            event_data["error_message"] = error_message
        if start_time:
            event_data["start_time"] = start_time
        if end_time:
            event_data["end_time"] = end_time
        if tokens is not None:
            event_data["tokens"] = tokens
        if cost_usd is not None:
            event_data["cost_usd"] = cost_usd
        if latency_ms is not None:
            event_data["latency_ms"] = latency_ms
        
        try:
            response = requests.post(
                self.event_endpoint,
                json=event_data,
                timeout=self.timeout
            )
            response.raise_for_status()
            
            result = response.json()
            agent_id = result.get("agent_id")
            
            logger.info(f"Event emitted: run_id={run_id}, agent={agent_name}, status={status}, agent_id={agent_id}")
            return agent_id
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to emit event: {e}")
            return None
    
    def start_agent(
        self,
        run_id: str,
        agent_name: str,
        prompt: str,
        parent_step_id: Optional[str] = None
    ) -> Optional[str]:
        """
        Convenience method to start an agent
        
        Returns:
            agent_id: The ID of the created agent run
        """
        return self.emit_event(
            run_id=run_id,
            agent_name=agent_name,
            status="started",
            prompt=prompt,
            parent_step_id=parent_step_id,
            start_time=datetime.now(timezone.utc).isoformat()
        )
    
    def complete_agent(
        self,
        run_id: str,
        agent_name: str,
        output: str,
        tokens: int,
        cost_usd: float,
        latency_ms: int,
        parent_step_id: Optional[str] = None
    ) -> Optional[str]:
        """
        Convenience method to complete an agent successfully
        
        Returns:
            agent_id: The ID of the created agent run
        """
        return self.emit_event(
            run_id=run_id,
            agent_name=agent_name,
            status="success",
            output=output,
            tokens=tokens,
            cost_usd=cost_usd,
            latency_ms=latency_ms,
            parent_step_id=parent_step_id,
            end_time=datetime.now(timezone.utc).isoformat()
        )
    
    def fail_agent(
        self,
        run_id: str,
        agent_name: str,
        error_message: str,
        latency_ms: int,
        parent_step_id: Optional[str] = None
    ) -> Optional[str]:
        """
        Convenience method to mark an agent as failed
        
        Returns:
            agent_id: The ID of the created agent run
        """
        return self.emit_event(
            run_id=run_id,
            agent_name=agent_name,
            status="error",
            error_message=error_message,
            latency_ms=latency_ms,
            parent_step_id=parent_step_id,
            end_time=datetime.now(timezone.utc).isoformat()
        )
