"""
Sample Multi-Agent AI System: Research Assistant

This demonstrates a multi-agent system that coordinates to research a topic:
1. Query Generator - Creates search queries
2. Web Searcher - Searches the web (simulated)
3. Content Analyzer - Analyzes search results
4. Report Writer - Synthesizes final report

Each agent is instrumented with AgentDog SDK to emit telemetry.
"""

import asyncio
import os
import sys
import time
from datetime import datetime, timezone
from emergentintegrations.llm.chat import LlmChat, UserMessage

# Add backend to path to import SDK
sys.path.insert(0, '/app/backend')
from agentdog_sdk import AgentDog


class ResearchAssistant:
    """Multi-agent research assistant system"""
    
    def __init__(self, run_id: str):
        self.run_id = run_id
        self.agentdog = AgentDog(api_url="http://localhost:8001/api")
        self.llm_key = os.environ.get('EMERGENT_LLM_KEY')
        
        # Store agent IDs for parent relationships
        self.agent_ids = {}
    
    async def run_research(self, topic: str):
        """Run the complete research workflow"""
        print(f"\n{'='*60}")
        print(f"Starting Research Workflow: {self.run_id}")
        print(f"Topic: {topic}")
        print(f"{'='*60}\n")
        
        # Agent 1: Query Generator
        queries = await self.query_generator(topic)
        
        # Agent 2: Web Searcher (runs for each query)
        search_results = []
        for i, query in enumerate(queries):
            result = await self.web_searcher(query, i)
            search_results.append(result)
        
        # Agent 3: Content Analyzer
        analyzed_content = await self.content_analyzer(search_results)
        
        # Agent 4: Report Writer
        final_report = await self.report_writer(topic, analyzed_content)
        
        print(f"\n{'='*60}")
        print(f"Research Workflow Complete!")
        print(f"View results at: http://localhost:3000")
        print(f"{'='*60}\n")
        
        return final_report
    
    async def query_generator(self, topic: str) -> list:
        """Agent 1: Generate search queries for the topic"""
        agent_name = "query_generator"
        prompt = f"Generate 3 search queries to research the topic: {topic}"
        
        print(f"[{agent_name}] Starting...")
        start_time = time.time()
        
        try:
            # Use Emergent LLM key with GPT-4o-mini
            chat = LlmChat(
                api_key=self.llm_key,
                session_id=f"{self.run_id}-{agent_name}"
            ).with_model("openai", "gpt-4o-mini")
            
            user_message = UserMessage(text=prompt)
            response = await chat.send_message(user_message)
            
            # Parse queries from response
            queries = [line.strip('- ').strip() for line in response.split('\n') if line.strip()][:3]
            
            latency_ms = int((time.time() - start_time) * 1000)
            
            # Emit success event
            agent_id = self.agentdog.emit_event(
                run_id=self.run_id,
                agent_name=agent_name,
                status="success",
                prompt=prompt,
                output=f"Generated queries: {', '.join(queries)}",
                tokens=150,
                cost_usd=0.001,
                latency_ms=latency_ms
            )
            
            self.agent_ids[agent_name] = agent_id
            print(f"[{agent_name}] ✅ Complete - Generated {len(queries)} queries")
            
            return queries
            
        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)
            self.agentdog.fail_agent(
                run_id=self.run_id,
                agent_name=agent_name,
                error_message=str(e),
                latency_ms=latency_ms
            )
            print(f"[{agent_name}] ❌ Failed: {e}")
            return []
    
    async def web_searcher(self, query: str, index: int) -> dict:
        """Agent 2: Search the web for information (simulated)"""
        agent_name = f"web_searcher_{index + 1}"
        prompt = f"Search for: {query}"
        parent_id = self.agent_ids.get("query_generator")
        
        print(f"[{agent_name}] Starting search...")
        start_time = time.time()
        
        try:
            # Simulate web search with LLM
            chat = LlmChat(
                api_key=self.llm_key,
                session_id=f"{self.run_id}-{agent_name}"
            ).with_model("openai", "gpt-4o-mini")
            
            search_prompt = f"Provide 2-3 key facts about: {query}"
            user_message = UserMessage(text=search_prompt)
            response = await chat.send_message(user_message)
            
            latency_ms = int((time.time() - start_time) * 1000)
            
            # Emit success event
            agent_id = self.agentdog.emit_event(
                run_id=self.run_id,
                agent_name=agent_name,
                status="success",
                prompt=prompt,
                output=response[:200],
                tokens=200,
                cost_usd=0.002,
                latency_ms=latency_ms,
                parent_step_id=parent_id
            )
            
            self.agent_ids[agent_name] = agent_id
            print(f"[{agent_name}] ✅ Complete - Found information")
            
            return {"query": query, "results": response}
            
        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)
            self.agentdog.fail_agent(
                run_id=self.run_id,
                agent_name=agent_name,
                error_message=str(e),
                latency_ms=latency_ms,
                parent_step_id=parent_id
            )
            print(f"[{agent_name}] ❌ Failed: {e}")
            return {"query": query, "results": ""}
    
    async def content_analyzer(self, search_results: list) -> str:
        """Agent 3: Analyze and synthesize search results"""
        agent_name = "content_analyzer"
        
        # Use last searcher as parent
        parent_id = self.agent_ids.get(f"web_searcher_{len(search_results)}")
        
        # Combine search results
        combined_results = "\n\n".join([
            f"Query: {r['query']}\nResults: {r['results']}"
            for r in search_results
        ])
        
        prompt = f"Analyze and synthesize the following search results:\n\n{combined_results[:500]}"
        
        print(f"[{agent_name}] Starting analysis...")
        start_time = time.time()
        
        try:
            chat = LlmChat(
                api_key=self.llm_key,
                session_id=f"{self.run_id}-{agent_name}"
            ).with_model("openai", "gpt-4o-mini")
            
            user_message = UserMessage(text=prompt)
            response = await chat.send_message(user_message)
            
            latency_ms = int((time.time() - start_time) * 1000)
            
            # Emit success event
            agent_id = self.agentdog.emit_event(
                run_id=self.run_id,
                agent_name=agent_name,
                status="success",
                prompt=prompt[:200],
                output=response[:300],
                tokens=400,
                cost_usd=0.003,
                latency_ms=latency_ms,
                parent_step_id=parent_id
            )
            
            self.agent_ids[agent_name] = agent_id
            print(f"[{agent_name}] ✅ Complete - Analysis done")
            
            return response
            
        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)
            self.agentdog.fail_agent(
                run_id=self.run_id,
                agent_name=agent_name,
                error_message=str(e),
                latency_ms=latency_ms,
                parent_step_id=parent_id
            )
            print(f"[{agent_name}] ❌ Failed: {e}")
            return ""
    
    async def report_writer(self, topic: str, analyzed_content: str) -> str:
        """Agent 4: Write final research report"""
        agent_name = "report_writer"
        parent_id = self.agent_ids.get("content_analyzer")
        
        prompt = f"Write a concise research report about '{topic}' based on: {analyzed_content[:300]}"
        
        print(f"[{agent_name}] Writing report...")
        start_time = time.time()
        
        try:
            chat = LlmChat(
                api_key=self.llm_key,
                session_id=f"{self.run_id}-{agent_name}"
            ).with_model("openai", "gpt-4o-mini")
            
            user_message = UserMessage(text=prompt)
            response = await chat.send_message(user_message)
            
            latency_ms = int((time.time() - start_time) * 1000)
            
            # Emit success event
            agent_id = self.agentdog.emit_event(
                run_id=self.run_id,
                agent_name=agent_name,
                status="success",
                prompt=prompt[:200],
                output=response,
                tokens=500,
                cost_usd=0.004,
                latency_ms=latency_ms,
                parent_step_id=parent_id
            )
            
            self.agent_ids[agent_name] = agent_id
            print(f"[{agent_name}] ✅ Complete - Report ready")
            
            return response
            
        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)
            self.agentdog.fail_agent(
                run_id=self.run_id,
                agent_name=agent_name,
                error_message=str(e),
                latency_ms=latency_ms,
                parent_step_id=parent_id
            )
            print(f"[{agent_name}] ❌ Failed: {e}")
            return ""


async def main():
    """Run the research assistant"""
    # Generate unique run ID
    timestamp = datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')
    run_id = f"research-{timestamp}"
    
    # Topic to research
    topic = "Latest advances in AI agents and multi-agent systems"
    
    # Create and run research assistant
    assistant = ResearchAssistant(run_id=run_id)
    report = await assistant.run_research(topic)
    
    print("\n" + "="*60)
    print("FINAL REPORT")
    print("="*60)
    print(report)
    print("="*60 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
