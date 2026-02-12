"""
Tool Registry - Centralized registry for managing all tools.
"""
from typing import Dict, List, Optional, Any
from llama_index.core.tools import FunctionTool
from app.tools.base import BaseTool


class ToolRegistry:
    """
    Centralized registry for managing tools.
    
    This class provides:
    - Tool registration and discovery
    - Tool execution by name
    - Tool filtering by category, enabled status
    - Conversion to LlamaIndex tools
    """
    
    def __init__(self):
        """Initialize empty tool registry."""
        self._tools: Dict[str, BaseTool] = {}
    
    def register(self, tool: BaseTool) -> None:
        """
        Register a tool in the registry.
        
        Args:
            tool: BaseTool instance to register
            
        Raises:
            ValueError: If tool with same name already exists
        """
        if tool.name in self._tools:
            raise ValueError(f"Tool with name '{tool.name}' already registered")
        
        self._tools[tool.name] = tool
        # Removed log for cleaner output
        # print(f"[ToolRegistry] Registered tool: {tool.name} (category: {tool.category})")
    
    def get(self, name: str) -> Optional[BaseTool]:
        """
        Get a tool by name.
        
        Args:
            name: Tool name
            
        Returns:
            BaseTool instance or None if not found
        """
        return self._tools.get(name)
    
    def get_all(self) -> List[BaseTool]:
        """
        Get all registered tools.
        
        Returns:
            List of all tools
        """
        return list(self._tools.values())
    
    def get_all_enabled(self) -> List[BaseTool]:
        """
        Get all enabled tools.
        
        Returns:
            List of enabled tools
        """
        return [tool for tool in self._tools.values() if tool.enabled]
    
    def get_by_category(self, category: str) -> List[BaseTool]:
        """
        Get all tools in a specific category.
        
        Args:
            category: Category name
            
        Returns:
            List of tools in the category
        """
        return [tool for tool in self._tools.values() if tool.category == category]
    
    def execute_tool(self, name: str, **kwargs) -> Any:
        """
        Execute a tool by name.
        
        Args:
            name: Tool name
            **kwargs: Tool-specific arguments
            
        Returns:
            Tool execution result
            
        Raises:
            ValueError: If tool not found or disabled
        """
        tool = self.get(name)
        
        if tool is None:
            return f"Error: Tool '{name}' not found"
        
        if not tool.enabled:
            return f"Error: Tool '{name}' is disabled"
        
        try:
            return tool.execute(**kwargs)
        except Exception as e:
            return f"Error executing tool '{name}': {str(e)}"
    
    def get_llama_tools(self) -> List[FunctionTool]:
        """
        Get all enabled tools as LlamaIndex FunctionTool instances.
        
        Returns:
            List of FunctionTool instances
        """
        return [tool.to_llama_tool() for tool in self.get_all_enabled()]
    
    def get_tools_summary(self) -> Dict[str, Any]:
        """
        Get summary of registered tools.
        
        Returns:
            Dictionary with tool statistics
        """
        all_tools = self.get_all()
        enabled_tools = self.get_all_enabled()
        
        categories = {}
        for tool in all_tools:
            categories[tool.category] = categories.get(tool.category, 0) + 1
        
        return {
            "total": len(all_tools),
            "enabled": len(enabled_tools),
            "disabled": len(all_tools) - len(enabled_tools),
            "categories": categories,
            "tools": [tool.get_metadata() for tool in all_tools]
        }
    
    def __repr__(self) -> str:
        return f"<ToolRegistry(tools={len(self._tools)}, enabled={len(self.get_all_enabled())})>"
