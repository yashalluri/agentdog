"""
Debate Multi-Agent System

This system enables debates between users and AI agents with two specialized agents:
1. Research Agent - Searches the web using Perplexity API for facts and evidence
2. Debate Agent - Constructs arguments using research findings with Claude 4 Sonnet

Both agents are instrumented with AgentDog SDK for full observability.
"""

import asyncio
import os
import sys
import time
import httpx
from datetime import datetime, timezone
from typing import List, Optional, Dict
from dotenv import load_dotenv
from emergentintegrations.llm.chat import LlmChat, UserMessage

# Load environment variables
load_dotenv()

# Add backend to path to import SDK
sys.path.insert(0, '/app/backend')
from agentdog_sdk import AgentDog


class ResearchAgent:
    """Agent responsible for web research using Perplexity API"""
    
    def __init__(self, run_id: str, agentdog: AgentDog):
        self.run_id = run_id
        self.agentdog = agentdog
        self.perplexity_api_key = os.environ.get('PERPLEXITY_API_KEY')
        self.agent_id = None
        
    async def research_topic(self, user_position: str, parent_step_id: Optional[str] = None) -> Dict:
        """
        Research a topic using Perplexity API to find counter-arguments and facts
        
        Args:
            user_position: The user's stated position to research against
            parent_step_id: Optional parent agent ID for coordination tracking
            
        Returns:
            Dictionary containing research findings, sources, and metadata
        """
        agent_name = "research_agent"
        prompt = f"Research counter-arguments and facts against this position: {user_position}"
        
        print(f"[{agent_name}] Starting web research...")
        start_time = time.time()
        
        try:
            # Generate search queries for comprehensive research
            search_queries = self._generate_search_queries(user_position)
            
            all_results = []
            total_sources = 0
            
            # Perform web searches using Perplexity API
            async with httpx.AsyncClient(timeout=30.0) as client:
                for query in search_queries:
                    try:
                        response = await client.post(
                            "https://api.perplexity.ai/chat/completions",
                            headers={
                                "Authorization": f"Bearer {self.perplexity_api_key}",
                                "Content-Type": "application/json"
                            },
                            json={
                                "model": "llama-3.1-sonar-small-128k-online",
                                "messages": [
                                    {
                                        "role": "system",
                                        "content": "You are a research assistant. Provide factual information with sources."
                                    },
                                    {
                                        "role": "user",
                                        "content": query
                                    }
                                ],
                                "temperature": 0.2,
                                "max_tokens": 1024
                            }
                        )
                        
                        if response.status_code == 200:
                            data = response.json()
                            content = data['choices'][0]['message']['content']
                            citations = data.get('citations', [])
                            
                            all_results.append({
                                "query": query,
                                "content": content,
                                "citations": citations
                            })
                            total_sources += len(citations)
                            
                            print(f"[{agent_name}] ✅ Search completed: {query[:50]}... ({len(citations)} sources)")
                        else:
                            print(f"[{agent_name}] ⚠️ Search failed with status {response.status_code}")
                            
                    except Exception as e:
                        print(f"[{agent_name}] ⚠️ Search error for query '{query[:30]}...': {e}")
                        continue
            
            # Compile research summary
            research_summary = self._compile_research_summary(all_results)
            
            latency_ms = int((time.time() - start_time) * 1000)
            
            # Emit success event to AgentDog
            self.agent_id = self.agentdog.emit_event(
                run_id=self.run_id,
                agent_name=agent_name,
                status="success",
                prompt=prompt[:500],
                output=research_summary[:1000],
                tokens=sum(len(r['content'].split()) for r in all_results),
                cost_usd=0.002 * len(search_queries),  # Estimated cost
                latency_ms=latency_ms,
                parent_step_id=parent_step_id
            )
            
            print(f"[{agent_name}] ✅ Research complete - Found {total_sources} sources")
            
            return {
                "success": True,
                "queries": search_queries,
                "results": all_results,
                "summary": research_summary,
                "total_sources": total_sources,
                "agent_id": self.agent_id
            }
            
        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)
            
            self.agent_id = self.agentdog.fail_agent(
                run_id=self.run_id,
                agent_name=agent_name,
                error_message=str(e),
                latency_ms=latency_ms,
                parent_step_id=parent_step_id
            )
            
            print(f"[{agent_name}] ❌ Research failed: {e}")
            
            return {
                "success": False,
                "error": str(e),
                "agent_id": self.agent_id
            }
    
    def _generate_search_queries(self, user_position: str) -> List[str]:
        """Generate effective search queries to research counter-arguments"""
        # Extract key topics from user position
        queries = [
            f"arguments against {user_position}",
            f"counterpoints to {user_position}",
            f"criticism of {user_position}"
        ]
        return queries[:2]  # Limit to 2 queries for efficiency
    
    def _compile_research_summary(self, results: List[Dict]) -> str:
        """Compile research results into a coherent summary"""
        if not results:
            return "No research findings available."
        
        summary_parts = []
        for result in results:
            summary_parts.append(f"Research on '{result['query']}':\n{result['content'][:300]}...")
        
        return "\n\n".join(summary_parts)


class DebateAgent:
    """Agent responsible for constructing debate arguments using research"""
    
    def __init__(self, run_id: str, agentdog: AgentDog):
        self.run_id = run_id
        self.agentdog = agentdog
        self.llm_key = os.environ.get('EMERGENT_LLM_KEY')
        self.agent_id = None
        
    async def construct_argument(
        self, 
        user_position: str, 
        research_findings: Dict,
        parent_step_id: Optional[str] = None
    ) -> str:
        """
        Construct a debate argument against the user's position using research
        
        Args:
            user_position: The user's stated position
            research_findings: Research data from Research Agent
            parent_step_id: Optional parent agent ID for coordination
            
        Returns:
            Constructed debate argument with citations
        """
        agent_name = "debate_agent"
        
        # Build context from research
        research_context = research_findings.get('summary', 'No research available')
        
        prompt = f"""You are debating against this position: "{user_position}"

Use the following research to construct a strong counter-argument:

{research_context}

Provide a well-reasoned argument that:
1. Directly addresses the user's position
2. Uses facts and evidence from the research
3. Is respectful and logical
4. Cites sources when possible
5. Is concise (2-3 paragraphs)
"""
        
        print(f"[{agent_name}] Constructing debate argument...")
        start_time = time.time()
        
        try:
            # Use Claude 4 Sonnet for high-quality reasoning
            chat = LlmChat(
                api_key=self.llm_key,
                session_id=f"{self.run_id}-{agent_name}",
                system_message="You are an expert debater who argues using logic, evidence, and respectful discourse."
            ).with_model("anthropic", "claude-4-sonnet-20250514")
            
            user_message = UserMessage(text=prompt)
            response = await chat.send_message(user_message)
            
            latency_ms = int((time.time() - start_time) * 1000)
            
            # Emit success event to AgentDog
            self.agent_id = self.agentdog.emit_event(
                run_id=self.run_id,
                agent_name=agent_name,
                status="success",
                prompt=prompt[:500],
                output=response[:1000],
                tokens=len(response.split()),
                cost_usd=0.005,  # Estimated cost for Claude
                latency_ms=latency_ms,
                parent_step_id=parent_step_id
            )
            
            print(f"[{agent_name}] ✅ Argument constructed")
            
            return response
            
        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)
            
            self.agent_id = self.agentdog.fail_agent(
                run_id=self.run_id,
                agent_name=agent_name,
                error_message=str(e),
                latency_ms=latency_ms,
                parent_step_id=parent_step_id
            )
            
            print(f"[{agent_name}] ❌ Argument construction failed: {e}")
            
            return f"I apologize, but I encountered an error constructing my argument: {str(e)}"


class DebateMultiAgentSystem:
    """Orchestrator for multi-agent debate system"""
    
    def __init__(self, run_id: str):
        self.run_id = run_id
        self.agentdog = AgentDog(api_url="http://localhost:8001/api")
        self.research_agent = ResearchAgent(run_id, self.agentdog)
        self.debate_agent = DebateAgent(run_id, self.agentdog)
        
    async def debate_with_user(self, user_position: str) -> str:
        """
        Complete debate workflow: research then argue
        
        Args:
            user_position: The user's stated position to debate against
            
        Returns:
            AI's debate argument with research backing
        """
        print(f"\n{'='*60}")
        print(f"Debate Multi-Agent System: {self.run_id}")
        print(f"User Position: {user_position}")
        print(f"{'='*60}\n")
        
        # Step 1: Research Agent searches for counter-arguments
        research_results = await self.research_agent.research_topic(user_position)
        
        if not research_results['success']:
            return "I apologize, but I couldn't complete the research needed for this debate."
        
        # Step 2: Debate Agent constructs argument using research
        debate_response = await self.debate_agent.construct_argument(
            user_position=user_position,
            research_findings=research_results,
            parent_step_id=research_results['agent_id']
        )
        
        print(f"\n{'='*60}")
        print("Debate Complete!")
        print(f"{'='*60}\n")
        
        return debate_response


async def main():
    """Test the debate system"""
    timestamp = datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')
    run_id = f"debate-{timestamp}"
    
    system = DebateMultiAgentSystem(run_id=run_id)
    
    user_position = "Remote work is more productive than office work"
    
    response = await system.debate_with_user(user_position)
    
    print("\n" + "="*60)
    print("AI DEBATE RESPONSE")
    print("="*60)
    print(response)
    print("="*60 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
