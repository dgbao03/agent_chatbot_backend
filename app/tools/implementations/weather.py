"""
Weather Tool - Get weather information for a city.
"""
from app.tools.base import BaseTool


class WeatherTool(BaseTool):
    """
    Tool for getting weather information by city name.
    """
    
    name = "get_weather"
    summary = "Get current weather information for a city. Use when user asks about weather."
    category = "external_api"
    description = """Fetch current weather information for a specific city. Use when user explicitly asks about weather conditions (e.g., "weather in Hanoi?", "weather in Tokyo today"). Do NOT use when city name appears in context without a weather request; returns temperature and weather summary."""
    
    def execute(self, city: str) -> str:
        """
        Get weather information for a city.
        
        Args:
            city: Name of the city
            
        Returns:
            Weather information string
        """
        return f"[WEATHER] {city}: 30°C, partly sunny"
