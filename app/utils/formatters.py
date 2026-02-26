"""
Format functions for converting data to text formats.
Pure utility functions with no domain dependencies.
"""
from typing import List
from llama_index.core.llms import ChatMessage


def format_messages_for_summary(messages: List[ChatMessage]) -> str:
    """
    Format messages into text for LLM summary.
    
    Args:
        messages: List of ChatMessage objects from LlamaIndex memory
        
    Returns:
        str: Formatted text
    """
    formatted_lines = []
    for i, msg in enumerate(messages, 1):
        role = msg.role.value
        content = msg.content if hasattr(msg, 'content') else str(msg)
        formatted_lines.append(f"{role.capitalize()}: {content}")
    
    return "\n".join(formatted_lines)

