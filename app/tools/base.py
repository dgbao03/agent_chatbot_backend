"""
Base Tool - Abstract class for all tools.
All tools must inherit from BaseTool and implement the execute method.
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from llama_index.core.tools import FunctionTool


class BaseTool(ABC):
    """
    Abstract base class for all tools.
    
    Attributes:
        name: Unique identifier for the tool
        summary: Short one-line description for system prompt tool instructions
        description: Detailed description for OpenAI function calling format
        category: Category of the tool (external_api, user_data, content, etc.)
        enabled: Whether the tool is currently enabled
    """
    
    name: str
    summary: str
    description: str
    category: str
    enabled: bool = True
    
    _REQUIRED_ATTRS = ("name", "summary", "description", "category")
    
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if not getattr(cls, "__abstractmethods__", None):
            for attr in cls._REQUIRED_ATTRS:
                if not hasattr(cls, attr):
                    raise TypeError(
                        f"{cls.__name__} must define class attribute '{attr}'"
                    )
    
    @abstractmethod
    def execute(self, **kwargs) -> Any:
        """
        Execute the tool with given arguments.
        
        Args:
            **kwargs: Tool-specific arguments
            
        Returns:
            Tool execution result
        """
        raise NotImplementedError("Subclasses must implement execute method")
    
    def to_llama_tool(self) -> FunctionTool:
        """
        Convert this tool to a LlamaIndex FunctionTool.
        
        Returns:
            FunctionTool instance configured with this tool's metadata
        """
        return FunctionTool.from_defaults(
            fn=self.execute,
            name=self.name,
            description=self.description
        )
    
    def get_metadata(self) -> Dict[str, Any]:
        """
        Get tool metadata.
        
        Returns:
            Dictionary containing tool metadata
        """
        return {
            "name": self.name,
            "summary": self.summary,
            "description": self.description,
            "category": self.category,
            "enabled": self.enabled,
        }
    
    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}(name={self.name}, category={self.category}, enabled={self.enabled})>"
