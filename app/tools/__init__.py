"""
Tools Module - Centralized tool management with registry pattern.

This module provides:
- Tool registry for automatic tool discovery
- Easy tool registration and management
- Conversion to LlamaIndex tools
"""
from app.tools.registry import ToolRegistry
from app.tools.implementations import (
    WeatherTool,
    StockTool,
    AddUserFactTool,
    UpdateUserFactTool,
    DeleteUserFactTool,
    URLExtractorTool,
)

# Create global registry
registry = ToolRegistry()

# Auto-register all tools
_ALL_TOOLS = [
    # External API Tools
    WeatherTool(),
    StockTool(),
    
    # User Data Tools
    AddUserFactTool(),
    UpdateUserFactTool(),
    DeleteUserFactTool(),
    
    # Content Tools
    URLExtractorTool(),
]

# Register all tools
for tool in _ALL_TOOLS:
    registry.register(tool)

# Export registry for use in other modules
__all__ = ["registry"]
