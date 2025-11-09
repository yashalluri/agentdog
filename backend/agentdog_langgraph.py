import time
from functools import wraps
from agentdog_client import AgentDogClient

def agentdog_node(agentdog_client: AgentDogClient, agent_name: str, parent_step_id: str | None = None):
    """Decorator to wrap LangGraph nodes for automatic telemetry logging."""
    def decorator(fn):
        @wraps(fn)
        def wrapper(state):
            start = time.time()
            try:
                result = fn(state)
                latency_ms = (time.time() - start) * 1000
                prompt = state.get("input", "") if isinstance(state, dict) else ""
                output = result.get("output", "") if isinstance(result, dict) else str(result)
                agentdog_client.log_step(
                    agent_name=agent_name,
                    status="success",
                    prompt=prompt,
                    output=output,
                    parent_step_id=parent_step_id,
                    latency_ms=latency_ms,
                )
                return result
            except Exception as e:
                latency_ms = (time.time() - start) * 1000
                prompt = state.get("input", "") if isinstance(state, dict) else ""
                agentdog_client.log_step(
                    agent_name=agent_name,
                    status="error",
                    prompt=prompt,
                    output="",
                    parent_step_id=parent_step_id,
                    latency_ms=latency_ms,
                    error_message=str(e),
                )
                raise
        return wrapper
    return decorator


def instrument_langgraph(graph, agentdog_client: AgentDogClient, node_parents: dict[str, str | None]):
    """
    Wrap every node in a LangGraph graph so all steps automatically log to AgentDog.
    Example: instrument_langgraph(graph, agentdog_client, {"summarizer": "collector"})
    """
    for node_name, node_fn in graph.nodes.items():
        parent_id = node_parents.get(node_name)
        wrapped = agentdog_node(agentdog_client, agent_name=node_name, parent_step_id=parent_id)(node_fn)
        graph.nodes[node_name] = wrapped
    return graph
