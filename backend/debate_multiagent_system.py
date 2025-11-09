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
from observability_tracer import (
    ObservabilityTracer, 
    SpanType, 
    SpanStatus,
    create_llm_span,
    create_api_span
)


class ResearchAgent:
    """Agent responsible for web research using Perplexity API"""
    
    def __init__(self, run_id: str, agentdog: AgentDog, tracer: Optional[ObservabilityTracer] = None):
        self.run_id = run_id
        self.agentdog = agentdog
        self.perplexity_api_key = os.environ.get('PERPLEXITY_API_KEY')
        self.agent_id = None
        self.tracer = tracer
        
    async def research_topic(self, user_position: str, parent_step_id: Optional[str] = None, parent_span_id: Optional[str] = None) -> Dict:
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
        
        # Create agent span if tracer is available
        agent_span = None
        if self.tracer:
            agent_span = self.tracer.start_span(
                name=agent_name,
                span_type=SpanType.AGENT,
                parent_span_id=parent_span_id,
                metadata={"agent_type": "research", "user_position": user_position}
            )
            agent_span.input_data = prompt
        
        try:
            # Generate search queries for comprehensive research
            search_queries = self._generate_search_queries(user_position)
            
            all_results = []
            total_sources = 0
            
            # Perform web searches using Perplexity API
            async with httpx.AsyncClient(timeout=30.0) as client:
                for query in search_queries:
                    # Create API call span
                    api_span = None
                    if self.tracer and agent_span:
                        api_span = create_api_span(
                            tracer=self.tracer,
                            name=f"perplexity_search: {query[:50]}",
                            method="POST",
                            url="https://api.perplexity.ai/chat/completions",
                            parent_span_id=agent_span.span_id
                        )
                        api_span.input_data = {"query": query, "model": "sonar", "temperature": 0.2, "max_tokens": 1024}
                    
                    try:
                        api_start = time.time()
                        response = await client.post(
                            "https://api.perplexity.ai/chat/completions",
                            headers={
                                "Authorization": f"Bearer {self.perplexity_api_key}",
                                "Content-Type": "application/json"
                            },
                            json={
                                "model": "sonar",
                                "messages": [
                                    {
                                        "role": "user",
                                        "content": query
                                    }
                                ],
                                "temperature": 0.2,
                                "max_tokens": 1024,
                                "search_domain_filter": [],
                                "return_citations": True,
                                "return_related_questions": False
                            }
                        )
                        
                        if response.status_code == 200:
                            data = response.json()
                            content = data['choices'][0]['message']['content']
                            citations = data.get('citations', [])
                            search_results = data.get('search_results', [])
                            
                            # Extract title and URL from search_results if available
                            formatted_citations = []
                            for idx, citation_url in enumerate(citations):
                                # Try to find matching search result for title
                                title = f"Source {idx + 1}"
                                for sr in search_results:
                                    if sr.get('url') == citation_url:
                                        title = sr.get('title', title)
                                        break
                                
                                formatted_citations.append({
                                    "url": citation_url,
                                    "title": title
                                })
                            
                            all_results.append({
                                "query": query,
                                "content": content,
                                "citations": formatted_citations
                            })
                            total_sources += len(formatted_citations)
                            
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
            
            # Small delay to ensure event is persisted before broadcasting
            await asyncio.sleep(0.3)
            
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
    ) -> Dict:
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
        
        # Build context from research with numbered citations
        research_context = research_findings.get('summary', 'No research available')
        
        # Build citation reference list for the prompt
        citation_list = ""
        for idx, result in enumerate(research_findings.get('results', []), 1):
            citations = result.get('citations', [])
            for cit_idx, citation in enumerate(citations[:5]):  # Max 5 per query
                cit_title = citation.get('title', f'Source {idx}')
                citation_list += f"[{idx}] {cit_title}\n"
        
        prompt = f"""You are debating against this position: "{user_position}"

Use the following research to construct a strong counter-argument:

{research_context}

Available sources for citation:
{citation_list}

IMPORTANT: When referencing information from the research, add inline citations using [1], [2], etc. Place the citation number immediately after the claim. For example:
"Studies show that remote work can lead to isolation [3]. However, office environments provide better collaboration [7]."

Provide a well-reasoned argument that:
1. Directly addresses the user's position
2. Uses facts and evidence from the research with INLINE CITATIONS
3. Is respectful and logical
4. Adds citation numbers [1], [2] etc. after each claim
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
            response = chat.send_message(user_message)
            
            # Handle async if needed
            if asyncio.iscoroutine(response):
                response = await response
            
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
            
            # Small delay to ensure event is persisted before broadcasting
            await asyncio.sleep(0.3)
            
            return {
                "response": response,
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
            
            print(f"[{agent_name}] ❌ Argument construction failed: {e}")
            
            return {
                "response": f"I apologize, but I encountered an error constructing my argument: {str(e)}",
                "agent_id": self.agent_id
            }


class DebateMultiAgentSystem:
    """Orchestrator for multi-agent debate system"""
    
    def __init__(self, run_id: str, progress_callback=None):
        self.run_id = run_id
        self.agentdog = AgentDog(api_url="http://localhost:8001/api")
        self.research_agent = ResearchAgent(run_id, self.agentdog)
        self.debate_agent = DebateAgent(run_id, self.agentdog)
        self.progress_callback = progress_callback
        
    async def debate_with_user(self, user_position: str) -> Dict:
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
        
        # Update progress: Searching the web (send immediately)
        if self.progress_callback:
            await self.progress_callback("🔍 Searching the web...")
        
        # Small delay to ensure WebSocket message is sent before agent starts
        await asyncio.sleep(0.2)
        
        # Step 1: Research Agent searches for counter-arguments
        research_results = await self.research_agent.research_topic(user_position)
        
        if not research_results['success']:
            return {
                "response": "I apologize, but I couldn't complete the research needed for this debate.",
                "citations": []
            }
        
        # Update progress: Research complete (triggers observability refresh)
        if self.progress_callback:
            await self.progress_callback("✅ Research complete")
        
        await asyncio.sleep(0.5)
        
        # Update progress: Analyzing findings
        if self.progress_callback:
            await self.progress_callback("📊 Analyzing findings...")
        
        await asyncio.sleep(1)  # Brief pause for UI feedback
        
        # Update progress: Making points
        if self.progress_callback:
            await self.progress_callback("💡 Making points...")
        
        # Step 2: Debate Agent constructs argument using research
        debate_result = await self.debate_agent.construct_argument(
            user_position=user_position,
            research_findings=research_results,
            parent_step_id=research_results['agent_id']
        )
        
        debate_response = debate_result.get('response', str(debate_result))
        
        # Update progress: Final argument draft
        if self.progress_callback:
            await self.progress_callback("✍️ Final argument draft...")
        
        await asyncio.sleep(0.5)  # Brief pause
        
        print(f"\n{'='*60}")
        print("Debate Complete!")
        print(f"{'='*60}\n")
        
        # Extract citations from research results
        citations = []
        citation_id = 1
        seen_urls = set()  # Avoid duplicate citations
        
        for result in research_results.get('results', []):
            for citation_data in result.get('citations', []):
                if isinstance(citation_data, dict):
                    url = citation_data.get('url', '')
                    title = citation_data.get('title', f'Source {citation_id}')
                else:
                    url = citation_data
                    title = f'Source {citation_id}'
                
                # Skip duplicates
                if url and url not in seen_urls:
                    citations.append({
                        "id": citation_id,
                        "url": url,
                        "title": title
                    })
                    seen_urls.add(url)
                    citation_id += 1
        
        # Format response with citations
        formatted_response = self._format_with_citations(debate_response, citations)
        
        return {
            "response": formatted_response,
            "citations": citations
        }
    
    def _format_with_citations(self, response: str, citations: List[Dict]) -> str:
        """Format the response with inline citations and sources section"""
        if not citations:
            return response
        
        # Add sources section with title and URL
        sources_section = "\n\n---\n\n**Sources:**\n"
        for citation in citations[:15]:  # Limit to first 15 sources
            sources_section += f"\n[{citation['id']}] {citation['url']}"
        
        return response + sources_section


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
