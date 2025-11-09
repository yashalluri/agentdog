"""
Social Media Content Creator Multi-Agent System

This system creates optimized content for multiple social media platforms:
1. Content Strategist - Analyzes topic and creates strategy
2. Twitter Thread Agent - Creates engaging Twitter thread
3. LinkedIn Post Agent - Creates professional LinkedIn post
4. Instagram Caption Agent - Creates visual-focused Instagram caption
5. Facebook Post Agent - Creates community-focused Facebook post
6. Hashtag Generator - Creates platform-specific hashtags
7. Engagement Optimizer - Provides engagement tips

All agents instrumented with AgentDog SDK for full observability.
"""

import asyncio
import os
import sys
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional
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
    create_llm_span
)


class ContentStrategistAgent:
    """Analyzes topic and creates content strategy"""
    
    def __init__(self, run_id: str, agentdog: AgentDog, tracer: Optional[ObservabilityTracer] = None):
        self.run_id = run_id
        self.agentdog = agentdog
        self.llm_key = os.environ.get('EMERGENT_LLM_KEY')
        self.agent_id = None
        self.tracer = tracer
        
    async def analyze_topic(self, user_topic: str, parent_span_id: Optional[str] = None) -> Dict:
        """Analyze the topic and create content strategy"""
        agent_name = "content_strategist"
        
        prompt = f"""Analyze this topic for social media content: "{user_topic}"

Provide a content strategy including:
1. Key message/angle
2. Target audience
3. Tone (professional/casual/inspiring/etc)
4. 3 key points to emphasize
5. Call-to-action suggestions

Be concise and strategic."""
        
        print(f"[{agent_name}] Analyzing topic and creating strategy...")
        start_time = time.time()
        
        # Create agent span
        agent_span = None
        if self.tracer:
            agent_span = self.tracer.start_span(
                name=agent_name,
                span_type=SpanType.AGENT,
                parent_span_id=parent_span_id,
                metadata={"agent_type": "content_strategist", "topic": user_topic}
            )
            agent_span.input_data = prompt
        
        try:
            # Create LLM call span
            llm_span = None
            if self.tracer and agent_span:
                llm_span = create_llm_span(
                    tracer=self.tracer,
                    name="claude_content_strategy",
                    model="claude-4-sonnet-20250514",
                    parent_span_id=agent_span.span_id
                )
                llm_span.input_data = prompt
            
            chat = LlmChat(
                api_key=self.llm_key,
                session_id=f"{self.run_id}-{agent_name}",
                system_message="You are a professional content strategist."
            ).with_model("anthropic", "claude-4-sonnet-20250514")
            
            user_msg = UserMessage(text=prompt)
            response = chat.send_message(user_msg)
            
            if asyncio.iscoroutine(response):
                response = await response
            
            # Complete LLM span
            if llm_span:
                llm_span.output_data = response
                llm_span.add_llm_details(
                    model="claude-4-sonnet-20250514",
                    tokens_input=len(prompt.split()),
                    tokens_output=len(response.split()),
                    cost_usd=0.003
                )
                self.tracer.end_span(llm_span.span_id, SpanStatus.SUCCESS)
            
            latency_ms = int((time.time() - start_time) * 1000)
            
            self.agent_id = self.agentdog.emit_event(
                run_id=self.run_id,
                agent_name=agent_name,
                status="success",
                prompt=prompt[:500],
                output=response[:1000],
                tokens=len(response.split()),
                cost_usd=0.003,
                latency_ms=latency_ms
            )
            
            print(f"[{agent_name}] ✅ Strategy created")
            
            # Complete agent span
            if agent_span:
                agent_span.output_data = response[:1000]
                self.tracer.end_span(agent_span.span_id, SpanStatus.SUCCESS)
            
            await asyncio.sleep(0.3)  # Ensure persistence
            
            return {
                "success": True,
                "strategy": response,
                "agent_id": self.agent_id,
                "span_id": agent_span.span_id if agent_span else None
            }
            
        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)
            
            # Complete agent span with error
            if agent_span:
                self.tracer.end_span(agent_span.span_id, SpanStatus.ERROR, error=str(e))
            
            self.agent_id = self.agentdog.fail_agent(
                run_id=self.run_id,
                agent_name=agent_name,
                error_message=str(e),
                latency_ms=latency_ms
            )
            
            print(f"[{agent_name}] ❌ Failed: {e}")
            
            return {
                "success": False,
                "error": str(e),
                "agent_id": self.agent_id,
                "span_id": agent_span.span_id if agent_span else None
            }


class PlatformWriterAgent:
    """Base class for platform-specific content writers"""
    
    def __init__(self, run_id: str, agentdog: AgentDog, platform: str, tracer: Optional[ObservabilityTracer] = None):
        self.run_id = run_id
        self.agentdog = agentdog
        self.platform = platform
        self.llm_key = os.environ.get('EMERGENT_LLM_KEY')
        self.agent_id = None
        self.tracer = tracer
        
    async def write_content(self, topic: str, strategy: str, parent_step_id: str) -> Dict:
        """Write platform-specific content"""
        agent_name = f"{self.platform.lower()}_writer"
        
        platform_specs = {
            "Twitter": {
                "format": "Thread of 3-5 tweets",
                "style": "Concise, punchy, with emojis",
                "length": "Each tweet max 280 characters",
                "special": "Number tweets (1/5, 2/5, etc.)"
            },
            "LinkedIn": {
                "format": "Professional post",
                "style": "Thought leadership, insights-driven",
                "length": "3-5 paragraphs, ~1500 characters",
                "special": "Start with hook, include line breaks for readability"
            },
            "Instagram": {
                "format": "Caption with visual description",
                "style": "Visual, lifestyle-focused, emojis",
                "length": "2-3 paragraphs, ~2000 characters",
                "special": "Describe ideal image/video, use emojis strategically"
            },
            "Facebook": {
                "format": "Community post",
                "style": "Conversational, community-building",
                "length": "2-4 paragraphs, ~1200 characters",
                "special": "Encourage comments/discussion"
            }
        }
        
        specs = platform_specs[self.platform]
        
        prompt = f"""Create {self.platform} content for: "{topic}"

Strategy Context:
{strategy}

Platform Requirements:
- Format: {specs['format']}
- Style: {specs['style']}
- Length: {specs['length']}
- Special: {specs['special']}

Create engaging, platform-optimized content that follows these specs exactly."""
        
        print(f"[{agent_name}] Writing {self.platform} content...")
        start_time = time.time()
        
        try:
            chat = LlmChat(
                api_key=self.llm_key,
                session_id=f"{self.run_id}-{agent_name}",
                system_message=f"You are an expert {self.platform} content writer."
            ).with_model("anthropic", "claude-4-sonnet-20250514")
            
            user_msg = UserMessage(text=prompt)
            response = chat.send_message(user_msg)
            
            if asyncio.iscoroutine(response):
                response = await response
            
            latency_ms = int((time.time() - start_time) * 1000)
            
            self.agent_id = self.agentdog.emit_event(
                run_id=self.run_id,
                agent_name=agent_name,
                status="success",
                prompt=prompt[:500],
                output=response[:1000],
                tokens=len(response.split()),
                cost_usd=0.003,
                latency_ms=latency_ms,
                parent_step_id=parent_step_id
            )
            
            print(f"[{agent_name}] ✅ Content created")
            
            await asyncio.sleep(0.3)  # Ensure persistence
            
            return {
                "success": True,
                "platform": self.platform,
                "content": response,
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
            
            print(f"[{agent_name}] ❌ Failed: {e}")
            
            return {
                "success": False,
                "platform": self.platform,
                "error": str(e),
                "agent_id": self.agent_id
            }


class HashtagGeneratorAgent:
    """Generates platform-specific hashtags"""
    
    def __init__(self, run_id: str, agentdog: AgentDog):
        self.run_id = run_id
        self.agentdog = agentdog
        self.llm_key = os.environ.get('EMERGENT_LLM_KEY')
        self.agent_id = None
        
    async def generate_hashtags(self, topic: str, platform_contents: List[Dict], parent_step_id: str) -> Dict:
        """Generate hashtags for all platforms"""
        agent_name = "hashtag_generator"
        
        prompt = f"""Generate hashtags for this topic: "{topic}"

Create hashtags for each platform:
- Twitter: 3-5 hashtags (trending + niche)
- LinkedIn: 3-5 hashtags (professional)
- Instagram: 20-30 hashtags (mix of popular + niche)
- Facebook: 3-5 hashtags (broad reach)

Format:
TWITTER: #hashtag1 #hashtag2 #hashtag3
LINKEDIN: #hashtag1 #hashtag2 #hashtag3
INSTAGRAM: #hashtag1 #hashtag2 ... (up to 30)
FACEBOOK: #hashtag1 #hashtag2 #hashtag3"""
        
        print(f"[{agent_name}] Generating hashtags...")
        start_time = time.time()
        
        try:
            chat = LlmChat(
                api_key=self.llm_key,
                session_id=f"{self.run_id}-{agent_name}",
                system_message="You are an expert social media hashtag strategist."
            ).with_model("anthropic", "claude-4-sonnet-20250514")
            
            user_msg = UserMessage(text=prompt)
            response = chat.send_message(user_msg)
            
            if asyncio.iscoroutine(response):
                response = await response
            
            latency_ms = int((time.time() - start_time) * 1000)
            
            self.agent_id = self.agentdog.emit_event(
                run_id=self.run_id,
                agent_name=agent_name,
                status="success",
                prompt=prompt[:500],
                output=response[:1000],
                tokens=len(response.split()),
                cost_usd=0.002,
                latency_ms=latency_ms,
                parent_step_id=parent_step_id
            )
            
            print(f"[{agent_name}] ✅ Hashtags generated")
            
            await asyncio.sleep(0.3)  # Ensure persistence
            
            return {
                "success": True,
                "hashtags": response,
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
            
            print(f"[{agent_name}] ❌ Failed: {e}")
            
            return {
                "success": False,
                "error": str(e),
                "agent_id": self.agent_id
            }


class EngagementOptimizerAgent:
    """Provides engagement optimization tips"""
    
    def __init__(self, run_id: str, agentdog: AgentDog):
        self.run_id = run_id
        self.agentdog = agentdog
        self.llm_key = os.environ.get('EMERGENT_LLM_KEY')
        self.agent_id = None
        
    async def optimize(self, topic: str, all_content: Dict, parent_step_id: str) -> Dict:
        """Provide engagement optimization tips"""
        agent_name = "engagement_optimizer"
        
        prompt = f"""Analyze the social media content for: "{topic}"

Provide engagement optimization tips:
1. Best posting times for each platform
2. Engagement tactics (polls, questions, CTAs)
3. Cross-promotion strategy
4. A/B testing suggestions
5. Metrics to track

Be specific and actionable."""
        
        print(f"[{agent_name}] Optimizing for engagement...")
        start_time = time.time()
        
        try:
            chat = LlmChat(
                api_key=self.llm_key,
                session_id=f"{self.run_id}-{agent_name}",
                system_message="You are an expert social media engagement strategist."
            ).with_model("anthropic", "claude-4-sonnet-20250514")
            
            user_msg = UserMessage(text=prompt)
            response = chat.send_message(user_msg)
            
            if asyncio.iscoroutine(response):
                response = await response
            
            latency_ms = int((time.time() - start_time) * 1000)
            
            self.agent_id = self.agentdog.emit_event(
                run_id=self.run_id,
                agent_name=agent_name,
                status="success",
                prompt=prompt[:500],
                output=response[:1000],
                tokens=len(response.split()),
                cost_usd=0.003,
                latency_ms=latency_ms,
                parent_step_id=parent_step_id
            )
            
            print(f"[{agent_name}] ✅ Optimization complete")
            
            await asyncio.sleep(0.3)  # Ensure persistence
            
            return {
                "success": True,
                "optimization_tips": response,
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
            
            print(f"[{agent_name}] ❌ Failed: {e}")
            
            return {
                "success": False,
                "error": str(e),
                "agent_id": self.agent_id
            }


class SocialMediaMultiAgentSystem:
    """Orchestrator for social media content creation"""
    
    def __init__(self, run_id: str, progress_callback=None):
        self.run_id = run_id
        self.agentdog = AgentDog(api_url="http://localhost:8001/api")
        self.progress_callback = progress_callback
        
        # Initialize agents
        self.strategist = ContentStrategistAgent(run_id, self.agentdog)
        self.twitter_writer = PlatformWriterAgent(run_id, self.agentdog, "Twitter")
        self.linkedin_writer = PlatformWriterAgent(run_id, self.agentdog, "LinkedIn")
        self.instagram_writer = PlatformWriterAgent(run_id, self.agentdog, "Instagram")
        self.facebook_writer = PlatformWriterAgent(run_id, self.agentdog, "Facebook")
        self.hashtag_generator = HashtagGeneratorAgent(run_id, self.agentdog)
        self.engagement_optimizer = EngagementOptimizerAgent(run_id, self.agentdog)
        
    async def create_content(self, user_topic: str) -> str:
        """Complete social media content creation workflow"""
        print(f"\n{'='*60}")
        print(f"Social Media Content Creator: {self.run_id}")
        print(f"Topic: {user_topic}")
        print(f"{'='*60}\n")
        
        # Step 1: Content Strategy
        if self.progress_callback:
            await self.progress_callback("🎯 Creating content strategy...")
        
        await asyncio.sleep(0.2)
        
        strategy_result = await self.strategist.analyze_topic(user_topic)
        
        if not strategy_result['success']:
            return "I apologize, but I couldn't create a content strategy."
        
        strategy = strategy_result['strategy']
        strategist_id = strategy_result['agent_id']
        
        # Step 2: Parallel Platform Content Creation
        if self.progress_callback:
            await self.progress_callback("✍️ Writing content for all platforms...")
        
        await asyncio.sleep(0.2)
        
        # Run all platform writers in parallel
        platform_tasks = [
            self.twitter_writer.write_content(user_topic, strategy, strategist_id),
            self.linkedin_writer.write_content(user_topic, strategy, strategist_id),
            self.instagram_writer.write_content(user_topic, strategy, strategist_id),
            self.facebook_writer.write_content(user_topic, strategy, strategist_id)
        ]
        
        platform_results = await asyncio.gather(*platform_tasks)
        
        # Step 3: Generate Hashtags
        if self.progress_callback:
            await self.progress_callback("🏷️ Generating hashtags...")
        
        await asyncio.sleep(0.2)
        
        hashtag_result = await self.hashtag_generator.generate_hashtags(
            user_topic,
            platform_results,
            strategist_id
        )
        
        # Step 4: Engagement Optimization
        if self.progress_callback:
            await self.progress_callback("📈 Optimizing for engagement...")
        
        await asyncio.sleep(0.2)
        
        optimization_result = await self.engagement_optimizer.optimize(
            user_topic,
            {"platforms": platform_results, "hashtags": hashtag_result},
            strategist_id
        )
        
        # Compile final response
        response = self._format_final_output(
            strategy_result,
            platform_results,
            hashtag_result,
            optimization_result
        )
        
        print(f"\n{'='*60}")
        print("Social Media Content Complete!")
        print(f"{'='*60}\n")
        
        return response
    
    def _format_final_output(self, strategy, platforms, hashtags, optimization) -> str:
        """Format all content into a cohesive response"""
        output = f"""# 🎯 CONTENT STRATEGY\n\n{strategy['strategy']}\n\n"""
        output += "---\n\n"
        
        # Add platform content
        for platform_result in platforms:
            if platform_result['success']:
                platform_name = platform_result['platform']
                content = platform_result['content']
                output += f"## {platform_name.upper()} 📱\n\n{content}\n\n---\n\n"
        
        # Add hashtags
        if hashtags['success']:
            output += f"## HASHTAGS 🏷️\n\n{hashtags['hashtags']}\n\n---\n\n"
        
        # Add optimization tips
        if optimization['success']:
            output += f"## ENGAGEMENT TIPS 📈\n\n{optimization['optimization_tips']}\n\n"
        
        return output


async def main():
    """Test the social media system"""
    timestamp = datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')
    run_id = f"social-media-{timestamp}"
    
    system = SocialMediaMultiAgentSystem(run_id=run_id)
    
    user_topic = "The benefits of remote work for tech companies"
    
    response = await system.create_content(user_topic)
    
    print("\n" + "="*60)
    print("SOCIAL MEDIA CONTENT")
    print("="*60)
    print(response[:2000])  # Print first 2000 chars
    print("="*60 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
