"""
Advanced Observability Tracer for Multi-Agent Systems

Provides detailed tracing similar to Langfuse/LangSmith:
- Hierarchical spans (root -> agent -> LLM call -> sub-operations)
- Complete request/response capture
- Timing breakdown for every operation
- Token and cost tracking per API call
- Streaming status monitoring
- Database operation tracking
"""

import time
import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, List, Any
from enum import Enum
import asyncio


class SpanType(Enum):
    """Types of spans for categorization"""
    ROOT = "root"
    AGENT = "agent"
    LLM_CALL = "llm_call"
    API_CALL = "api_call"
    DATABASE = "database"
    TOOL = "tool"
    RETRIEVAL = "retrieval"


class SpanStatus(Enum):
    """Status of a span"""
    RUNNING = "running"
    SUCCESS = "success"
    ERROR = "error"


class Span:
    """Represents a single traced operation"""
    
    def __init__(
        self,
        name: str,
        span_type: SpanType,
        parent_span_id: Optional[str] = None,
        metadata: Optional[Dict] = None
    ):
        self.span_id = str(uuid.uuid4())[:12]  # Short ID
        self.name = name
        self.span_type = span_type
        self.parent_span_id = parent_span_id
        self.status = SpanStatus.RUNNING
        self.start_time = time.time()
        self.end_time = None
        self.duration_ms = None
        self.metadata = metadata or {}
        self.input_data = None
        self.output_data = None
        self.error = None
        self.children = []
        
        # LLM-specific fields
        self.model = None
        self.tokens_input = None
        self.tokens_output = None
        self.tokens_total = None
        self.cost_usd = None
        self.temperature = None
        self.max_tokens = None
        self.streaming = False
        
        # API-specific fields
        self.http_method = None
        self.http_url = None
        self.http_status = None
        
        # Database-specific fields
        self.db_operation = None
        self.db_collection = None
        
    def end(self, status: SpanStatus = SpanStatus.SUCCESS, error: Optional[str] = None):
        """End the span and calculate duration"""
        self.end_time = time.time()
        self.duration_ms = int((self.end_time - self.start_time) * 1000)
        self.status = status
        if error:
            self.error = error
            self.status = SpanStatus.ERROR
            
    def add_llm_details(
        self,
        model: str,
        tokens_input: int,
        tokens_output: int,
        cost_usd: float,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        streaming: bool = False
    ):
        """Add LLM-specific details"""
        self.model = model
        self.tokens_input = tokens_input
        self.tokens_output = tokens_output
        self.tokens_total = tokens_input + tokens_output
        self.cost_usd = cost_usd
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.streaming = streaming
        
    def add_api_details(self, method: str, url: str, status_code: int):
        """Add API call details"""
        self.http_method = method
        self.http_url = url
        self.http_status = status_code
        
    def add_database_details(self, operation: str, collection: str):
        """Add database operation details"""
        self.db_operation = operation
        self.db_collection = collection
        
    def to_dict(self) -> Dict:
        """Convert span to dictionary for storage"""
        return {
            "span_id": self.span_id,
            "name": self.name,
            "span_type": self.span_type.value,
            "parent_span_id": self.parent_span_id,
            "status": self.status.value,
            "start_time": datetime.fromtimestamp(self.start_time, tz=timezone.utc).isoformat(),
            "end_time": datetime.fromtimestamp(self.end_time, tz=timezone.utc).isoformat() if self.end_time else None,
            "duration_ms": self.duration_ms,
            "metadata": self.metadata,
            "input": self.input_data,
            "output": self.output_data,
            "error": self.error,
            
            # LLM fields
            "model": self.model,
            "tokens_input": self.tokens_input,
            "tokens_output": self.tokens_output,
            "tokens_total": self.tokens_total,
            "cost_usd": self.cost_usd,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "streaming": self.streaming,
            
            # API fields
            "http_method": self.http_method,
            "http_url": self.http_url,
            "http_status": self.http_status,
            
            # Database fields
            "db_operation": self.db_operation,
            "db_collection": self.db_collection,
            
            "children": [child.to_dict() for child in self.children]
        }


class ObservabilityTracer:
    """Main tracer for managing spans and traces"""
    
    def __init__(self, run_id: str):
        self.run_id = run_id
        self.root_span = None
        self.active_spans = {}  # span_id -> Span
        self.all_spans = []  # Flat list for easy access
        
    def start_root_span(self, name: str, metadata: Optional[Dict] = None) -> Span:
        """Start the root span for this trace"""
        self.root_span = Span(
            name=name,
            span_type=SpanType.ROOT,
            parent_span_id=None,
            metadata=metadata
        )
        self.active_spans[self.root_span.span_id] = self.root_span
        self.all_spans.append(self.root_span)
        return self.root_span
        
    def start_span(
        self,
        name: str,
        span_type: SpanType,
        parent_span_id: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> Span:
        """Start a new span"""
        span = Span(
            name=name,
            span_type=span_type,
            parent_span_id=parent_span_id or (self.root_span.span_id if self.root_span else None),
            metadata=metadata
        )
        
        self.active_spans[span.span_id] = span
        self.all_spans.append(span)
        
        # Add to parent's children
        if span.parent_span_id and span.parent_span_id in self.active_spans:
            self.active_spans[span.parent_span_id].children.append(span)
            
        return span
        
    def end_span(self, span_id: str, status: SpanStatus = SpanStatus.SUCCESS, error: Optional[str] = None):
        """End a span"""
        if span_id in self.active_spans:
            span = self.active_spans[span_id]
            span.end(status=status, error=error)
            
    def get_trace(self) -> Dict:
        """Get the complete trace as a hierarchical structure"""
        if self.root_span:
            return {
                "run_id": self.run_id,
                "trace": self.root_span.to_dict(),
                "total_duration_ms": self.root_span.duration_ms,
                "total_spans": len(self.all_spans),
                "total_tokens": sum(s.tokens_total or 0 for s in self.all_spans),
                "total_cost_usd": sum(s.cost_usd or 0 for s in self.all_spans)
            }
        return None
        
    def get_flat_spans(self) -> List[Dict]:
        """Get all spans in a flat list with timing"""
        return [
            {
                **span.to_dict(),
                "depth": self._get_depth(span.span_id),
                "start_offset_ms": int((span.start_time - self.root_span.start_time) * 1000) if self.root_span else 0
            }
            for span in self.all_spans
        ]
        
    def _get_depth(self, span_id: str) -> int:
        """Calculate the depth of a span in the tree"""
        depth = 0
        span = self.active_spans.get(span_id)
        while span and span.parent_span_id:
            depth += 1
            span = self.active_spans.get(span.parent_span_id)
        return depth


# Helper function to create LLM call span
def create_llm_span(
    tracer: ObservabilityTracer,
    name: str,
    model: str,
    parent_span_id: Optional[str] = None,
    metadata: Optional[Dict] = None
) -> Span:
    """Create a span for LLM API call"""
    return tracer.start_span(
        name=name,
        span_type=SpanType.LLM_CALL,
        parent_span_id=parent_span_id,
        metadata={
            "model": model,
            **(metadata or {})
        }
    )


# Helper function to create API call span
def create_api_span(
    tracer: ObservabilityTracer,
    name: str,
    method: str,
    url: str,
    parent_span_id: Optional[str] = None
) -> Span:
    """Create a span for API call"""
    span = tracer.start_span(
        name=name,
        span_type=SpanType.API_CALL,
        parent_span_id=parent_span_id
    )
    span.add_api_details(method=method, url=url, status_code=0)  # Status will be updated
    return span


# Helper function to create database span
def create_database_span(
    tracer: ObservabilityTracer,
    name: str,
    operation: str,
    collection: str,
    parent_span_id: Optional[str] = None
) -> Span:
    """Create a span for database operation"""
    span = tracer.start_span(
        name=name,
        span_type=SpanType.DATABASE,
        parent_span_id=parent_span_id
    )
    span.add_database_details(operation=operation, collection=collection)
    return span
