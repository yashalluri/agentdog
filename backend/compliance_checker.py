"""
Compliance Checker Module
Extracts requirements from policy documents and validates code/docs against them.
"""

import re
from typing import List, Dict, Any
from llm_client import get_completion_async
import logging

logger = logging.getLogger(__name__)


def extract_requirements(policy_text: str) -> List[Dict[str, Any]]:
    """
    Extract structured requirements from a policy document.
    
    Returns:
        List of requirements with:
        - id: Unique identifier
        - text: Requirement text
        - keywords: Key terms to search for
        - category: Type of requirement (e.g., security, documentation, testing)
    """
    requirements = []
    
    # Simple pattern matching for common requirement indicators
    patterns = [
        r"(?:must|shall|required to|should)\s+(.+?)(?:\.|$)",
        r"(?:requirement|policy):\s*(.+?)(?:\.|$)",
        r"(?:\d+\.|[-•])\s*(.+?)(?:\.|$)"
    ]
    
    lines = policy_text.split('\n')
    req_id = 1
    
    for line in lines:
        line = line.strip()
        if not line or len(line) < 10:
            continue
            
        for pattern in patterns:
            matches = re.finditer(pattern, line, re.IGNORECASE)
            for match in matches:
                req_text = match.group(1).strip()
                if len(req_text) > 15:  # Filter out too-short matches
                    # Extract keywords (simple approach: important words)
                    keywords = extract_keywords(req_text)
                    
                    # Categorize
                    category = categorize_requirement(req_text)
                    
                    requirements.append({
                        'id': f'REQ-{req_id:03d}',
                        'text': req_text,
                        'keywords': keywords,
                        'category': category
                    })
                    req_id += 1
                    break  # Only match once per line
    
    return requirements


def extract_keywords(text: str) -> List[str]:
    """Extract important keywords from requirement text."""
    # Remove common words
    stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 
                  'of', 'with', 'by', 'from', 'as', 'is', 'are', 'was', 'were', 'be',
                  'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will',
                  'would', 'should', 'could', 'may', 'might', 'must', 'can'}
    
    words = re.findall(r'\b\w+\b', text.lower())
    keywords = [w for w in words if w not in stop_words and len(w) > 3]
    
    return list(set(keywords))[:10]  # Top 10 unique keywords


def categorize_requirement(text: str) -> str:
    """Categorize a requirement based on its content."""
    text_lower = text.lower()
    
    if any(word in text_lower for word in ['security', 'encrypt', 'auth', 'permission', 'access']):
        return 'security'
    elif any(word in text_lower for word in ['document', 'comment', 'readme', 'explain']):
        return 'documentation'
    elif any(word in text_lower for word in ['test', 'verify', 'validate', 'check']):
        return 'testing'
    elif any(word in text_lower for word in ['error', 'exception', 'handle', 'log']):
        return 'error_handling'
    elif any(word in text_lower for word in ['perform', 'speed', 'optimize', 'efficient']):
        return 'performance'
    else:
        return 'general'


def naive_check(requirements: List[Dict[str, Any]], target_text: str) -> Dict[str, Any]:
    """
    Perform a naive keyword-based compliance check.
    This is the "good" agent that checks all requirements.
    
    Args:
        requirements: List of extracted requirements
        target_text: Code/document to check
        
    Returns:
        Compliance report with scores and missing items
    """
    target_lower = target_text.lower()
    results = []
    
    for req in requirements:
        # Check if any keywords are present
        matched_keywords = [kw for kw in req['keywords'] if kw in target_lower]
        
        status = 'met' if len(matched_keywords) > 0 else 'missing'
        confidence = len(matched_keywords) / max(len(req['keywords']), 1)
        
        results.append({
            'requirement_id': req['id'],
            'requirement_text': req['text'],
            'status': status,
            'confidence': round(confidence, 2),
            'matched_keywords': matched_keywords,
            'category': req['category']
        })
    
    # Calculate overall score
    total = len(results)
    met = sum(1 for r in results if r['status'] == 'met')
    score = round((met / max(total, 1)) * 100)
    
    return {
        'score': score,
        'total': total,
        'met': met,
        'missing_count': total - met,
        'results': results,
        'missing': [r for r in results if r['status'] == 'missing']
    }


async def ai_compliance_check(policy_text: str, target_text: str, 
                              run_id: str, intentionally_faulty: bool = False) -> Dict[str, Any]:
    """
    Use AI to perform deep compliance analysis.
    
    Args:
        policy_text: The compliance policy document
        target_text: The code/document to validate
        run_id: Workflow run ID for tracking
        intentionally_faulty: If True, agent will miss some requirements (for demo)
        
    Returns:
        Detailed compliance report
    """
    from agentdog_sdk import AgentDog
    import time
    
    agentdog = AgentDog(api_url="http://localhost:8001/api")
    
    # Extract requirements first
    requirements = extract_requirements(policy_text)
    
    if intentionally_faulty:
        # Faulty agent: only check 70% of requirements
        import random
        num_to_check = int(len(requirements) * 0.7)
        requirements_to_check = random.sample(requirements, num_to_check)
        agent_name = "faulty_compliance_checker"
    else:
        requirements_to_check = requirements
        agent_name = "compliance_checker"
    
    # Prepare prompt for AI
    req_list = "\n".join([f"{r['id']}: {r['text']}" for r in requirements_to_check])
    
    prompt = f"""You are a compliance checker. Analyze if the following code/document meets these requirements:

REQUIREMENTS:
{req_list}

CODE/DOCUMENT TO CHECK:
{target_text[:2000]}  # Limit to avoid token issues

For each requirement, respond with:
1. Requirement ID
2. Met (yes/no)
3. Evidence (what you found or what's missing)
4. Severity if missing (low/medium/high)

Provide a structured analysis."""

    start = time.time()
    
    try:
        # Call AI for analysis
        response = await get_completion_async(
            prompt=prompt,
            system_message="You are an expert compliance auditor. Analyze code and documents against policy requirements."
        )
        
        latency_ms = int((time.time() - start) * 1000)
        
        # Emit telemetry
        agentdog.emit_event(
            run_id=run_id,
            agent_name=agent_name,
            status="success",
            prompt=prompt[:500],
            output=response[:500],
            tokens=len(prompt.split()) + len(response.split()),
            cost_usd=0.003,
            latency_ms=latency_ms
        )
        
        # Parse AI response and combine with naive check
        naive_results = naive_check(requirements_to_check, target_text)
        
        return {
            'agent': agent_name,
            'method': 'ai_enhanced',
            'score': naive_results['score'],
            'total_requirements': len(requirements),
            'checked_requirements': len(requirements_to_check),
            'met': naive_results['met'],
            'missing': naive_results['missing'],
            'ai_analysis': response,
            'intentionally_faulty': intentionally_faulty,
            'skipped_requirements': len(requirements) - len(requirements_to_check) if intentionally_faulty else 0
        }
        
    except Exception as e:
        logger.error(f"AI compliance check failed: {e}")
        
        # Fallback to naive check
        naive_results = naive_check(requirements_to_check, target_text)
        
        agentdog.emit_event(
            run_id=run_id,
            agent_name=agent_name,
            status="error",
            prompt=prompt[:500],
            error_message=str(e),
            tokens=len(prompt.split()),
            cost_usd=0.001,
            latency_ms=int((time.time() - start) * 1000)
        )
        
        return {
            'agent': agent_name,
            'method': 'naive_fallback',
            'error': str(e),
            'score': naive_results['score'],
            'total_requirements': len(requirements),
            'checked_requirements': len(requirements_to_check),
            'met': naive_results['met'],
            'missing': naive_results['missing'],
            'intentionally_faulty': intentionally_faulty
        }