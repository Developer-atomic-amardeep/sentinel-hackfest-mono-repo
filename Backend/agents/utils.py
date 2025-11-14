import os
from typing import Optional, List, Dict, Any
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


def get_deepseek_client() -> OpenAI:
    """
    Initialize and return a DeepSeek API client using OpenAI-compatible interface.
    
    Returns:
        OpenAI: Configured client for DeepSeek API
        
    Raises:
        ValueError: If DEEPSEEK_API_KEY is not set in environment
    """
    api_key = os.getenv("DEEPSEEK_API_KEY")
    
    if not api_key:
        raise ValueError(
            "DEEPSEEK_API_KEY environment variable is not set. "
            "Please set it in your .env file or environment."
        )
    
    client = OpenAI(
        api_key=api_key,
        base_url="https://api.deepseek.com"
    )
    
    return client


def call_deepseek_chat(
    messages: List[Dict[str, str]],
    model: str = "deepseek-chat",
    temperature: float = 0.7,
    max_tokens: Optional[int] = None
) -> str:
    """
    Make a chat completion call to DeepSeek API.
    
    Args:
        messages: List of message dictionaries with 'role' and 'content' keys
        model: DeepSeek model to use (default: "deepseek-chat")
        temperature: Sampling temperature (0-1)
        max_tokens: Maximum tokens to generate (optional)
        
    Returns:
        str: The generated response content
        
    Raises:
        Exception: If API call fails
    """
    try:
        client = get_deepseek_client()
        
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens
        )
        
        return response.choices[0].message.content
    
    except Exception as e:
        raise Exception(f"DeepSeek API call failed: {str(e)}")

