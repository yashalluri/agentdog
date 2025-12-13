"""
Local LLM Client - Direct OpenAI SDK Integration

Provides a simple interface for LLM calls using OpenAI API.
"""

import os
from openai import OpenAI, AsyncOpenAI
from typing import Optional, List, Dict


class LlmClient:
    """Simple LLM client using OpenAI SDK directly"""
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        system_message: Optional[str] = None,
        model: str = "gpt-4o-mini"
    ):
        """
        Initialize LLM client
        
        Args:
            api_key: OpenAI API key (defaults to OPENAI_API_KEY env var)
            system_message: System prompt for the conversation
            model: Model to use (default: gpt-4o-mini)
        """
        self.api_key = api_key or os.environ.get('OPENAI_API_KEY')
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY environment variable is required")
        
        self.system_message = system_message or "You are a helpful AI assistant."
        self.model = model
        self.client = OpenAI(api_key=self.api_key)
        self.async_client = AsyncOpenAI(api_key=self.api_key)
        self.messages: List[Dict] = []
    
    def send_message(self, text: str) -> str:
        """
        Send a message and get a response (synchronous)
        
        Args:
            text: User message text
            
        Returns:
            Assistant's response text
        """
        self.messages.append({"role": "user", "content": text})
        
        all_messages = [{"role": "system", "content": self.system_message}] + self.messages
        
        response = self.client.chat.completions.create(
            model=self.model,
            messages=all_messages,
            max_tokens=4096
        )
        
        assistant_message = response.choices[0].message.content
        self.messages.append({"role": "assistant", "content": assistant_message})
        
        return assistant_message
    
    async def send_message_async(self, text: str) -> str:
        """
        Send a message and get a response (asynchronous)
        
        Args:
            text: User message text
            
        Returns:
            Assistant's response text
        """
        self.messages.append({"role": "user", "content": text})
        
        all_messages = [{"role": "system", "content": self.system_message}] + self.messages
        
        response = await self.async_client.chat.completions.create(
            model=self.model,
            messages=all_messages,
            max_tokens=4096
        )
        
        assistant_message = response.choices[0].message.content
        self.messages.append({"role": "assistant", "content": assistant_message})
        
        return assistant_message
    
    def clear_history(self):
        """Clear conversation history"""
        self.messages = []


# Convenience function for one-off completions
def get_completion(
    prompt: str,
    system_message: Optional[str] = None,
    model: str = "gpt-4o-mini",
    api_key: Optional[str] = None
) -> str:
    """
    Get a one-off completion without maintaining conversation state
    
    Args:
        prompt: User prompt
        system_message: Optional system prompt
        model: Model to use
        api_key: API key (defaults to env var)
        
    Returns:
        Model response text
    """
    client = LlmClient(
        api_key=api_key,
        system_message=system_message,
        model=model
    )
    return client.send_message(prompt)


async def get_completion_async(
    prompt: str,
    system_message: Optional[str] = None,
    model: str = "gpt-4o-mini",
    api_key: Optional[str] = None
) -> str:
    """
    Get a one-off completion without maintaining conversation state (async)
    
    Args:
        prompt: User prompt
        system_message: Optional system prompt
        model: Model to use
        api_key: API key (defaults to env var)
        
    Returns:
        Model response text
    """
    client = LlmClient(
        api_key=api_key,
        system_message=system_message,
        model=model
    )
    return await client.send_message_async(prompt)
