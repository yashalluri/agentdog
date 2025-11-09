import requests
import time

class AgentDogClient:
    """Minimal client for sending telemetry to AgentDog ingestion API."""
    def __init__(self, ingestion_url: str, run_id: str):
        self.ingestion_url = ingestion_url
        self.run_id = run_id

    def log_step(
        self,
        agent_name: str,
        status: str,
        prompt: str = "",
        output: str = "",
        parent_step_id: str | None = None,
        latency_ms: float | None = None,
        cost: float | None = None,
        tokens: int | None = None,
        error_message: str | None = None,
    ):
        payload = {
            "run_id": self.run_id,
            "agent_name": agent_name,
            "parent_step_id": parent_step_id,
            "status": status,
            "prompt": prompt,
            "output": output,
            "latency_ms": latency_ms or 0,
            "cost": cost or 0,
            "tokens": tokens or 0,
            "error_message": error_message,
            "claimed_actions": [],
            "actual_actions": [],
        }
        try:
            requests.post(self.ingestion_url, json=payload, timeout=3)
        except Exception:
            # Never crash user workflows on logging errors
            pass
