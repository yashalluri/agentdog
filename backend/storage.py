"""
In-memory storage layer for AgentDog
Easily swappable to MongoDB later
"""
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
import uuid


class InMemoryStorage:
    def __init__(self):
        self.runs: Dict[str, Dict[str, Any]] = {}
        self.steps: Dict[str, List[Dict[str, Any]]] = {}
    
    # Run operations
    def create_run(self, run_id: str) -> Dict[str, Any]:
        """Create a new run"""
        run = {
            "run_id": run_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "status": "running",
            "total_steps": 0,
            "success_steps": 0,
            "failed_steps": 0,
            "duration_ms": 0,
            "cost": 0.0,
            "integrity_score": 1.0,
            "summary": ""
        }
        self.runs[run_id] = run
        self.steps[run_id] = []
        return run
    
    def get_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        """Get a run by ID"""
        return self.runs.get(run_id)
    
    def get_all_runs(self, sort_by: str = "created_at", descending: bool = True) -> List[Dict[str, Any]]:
        """Get all runs sorted"""
        runs = list(self.runs.values())
        runs.sort(key=lambda x: x.get(sort_by, ""), reverse=descending)
        return runs
    
    def update_run(self, run_id: str, updates: Dict[str, Any]):
        """Update run fields"""
        if run_id in self.runs:
            self.runs[run_id].update(updates)
    
    # Step operations
    def add_step(self, run_id: str, step: Dict[str, Any]) -> Dict[str, Any]:
        """Add a step to a run"""
        if run_id not in self.steps:
            self.steps[run_id] = []
        
        # Generate ID if not provided
        if "id" not in step:
            step["id"] = str(uuid.uuid4())
        
        # Add timestamp
        if "created_at" not in step:
            step["created_at"] = datetime.now(timezone.utc).isoformat()
        
        self.steps[run_id].append(step)
        
        # Update run stats
        self._update_run_stats(run_id)
        
        return step
    
    def get_steps(self, run_id: str) -> List[Dict[str, Any]]:
        """Get all steps for a run"""
        return self.steps.get(run_id, [])
    
    def get_step_by_id(self, step_id: str) -> Optional[Dict[str, Any]]:
        """Find a step by its ID across all runs"""
        for steps_list in self.steps.values():
            for step in steps_list:
                if step.get("id") == step_id:
                    return step
        return None
    
    def _update_run_stats(self, run_id: str):
        """Update run statistics based on its steps"""
        if run_id not in self.runs or run_id not in self.steps:
            return
        
        steps = self.steps[run_id]
        run = self.runs[run_id]
        
        # Count stats
        total = len(steps)
        success = sum(1 for s in steps if s.get("status") == "success")
        failed = sum(1 for s in steps if s.get("status") == "error")
        
        # Calculate totals
        total_duration = sum(s.get("latency_ms", 0) for s in steps)
        total_cost = sum(s.get("cost", 0) for s in steps)
        
        # Calculate integrity score
        hallucinated = sum(1 for s in steps if s.get("hallucination_flags"))
        integrity = 1.0 - (hallucinated / total) if total > 0 else 1.0
        
        # Determine run status
        status = "running"
        if total > 0:
            if failed > 0:
                status = "error"
            elif all(s.get("status") in ["success", "error"] for s in steps):
                status = "success"
        
        # Update run
        run.update({
            "total_steps": total,
            "success_steps": success,
            "failed_steps": failed,
            "duration_ms": total_duration,
            "cost": total_cost,
            "integrity_score": round(integrity, 2),
            "status": status
        })


# Global storage instance
storage = InMemoryStorage()
