"""
Weather Tool - Get weather information for a city.
"""
from app.tools.base import BaseTool


class WeatherTool(BaseTool):
    """
    Tool for getting weather information by city name.
    """
    
    name = "get_weather"
    category = "external_api"
    description = """
Lấy thông tin thời tiết theo thành phố. Input: Tên thành phố. 
Lưu ý: Chỉ sử dụng khi User yêu cầu thông tin thời tiết về thành phố.
Không sử dụng khi trong Request có tên thành phố/địa danh nhưng không yêu cầu thông tin thời tiết."""
    
    def execute(self, city: str) -> str:
        """
        Get weather information for a city.
        
        Args:
            city: Name of the city
            
        Returns:
            Weather information string
        """
        return f"[WEATHER] {city}: 30°C, nắng nhẹ"
