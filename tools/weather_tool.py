"""
Weather Tool - Lấy thông tin thời tiết sử dụng Weather API
"""

import os
import logging
from typing import Optional
from dotenv import load_dotenv
import requests

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)


def get_weather(location: str, units: str = "metric") -> str:
    """
    Lấy thông tin thời tiết cho một địa điểm cụ thể
    
    Args:
        location: Tên địa điểm (ví dụ: "Hanoi, Vietnam", "London, UK")
        units: Đơn vị nhiệt độ - "metric" (Celsius) hoặc "imperial" (Fahrenheit). Mặc định: "metric"
        
    Returns:
        str: Thông tin thời tiết đã được format
    """
    try:
        api_key = os.getenv("WEATHER_API_KEY")
        if not api_key:
            raise ValueError("WEATHER_API_KEY không được tìm thấy trong environment variables")
        
        # Weather API endpoint (OpenWeatherMap)
        base_url = "https://api.openweathermap.org/data/2.5/weather"
        
        params = {
            "q": location,
            "appid": api_key,
            "units": units,
            "lang": "vi"  # Tiếng Việt
        }
        
        # Gọi API
        response = requests.get(base_url, params=params, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        
        # Format kết quả
        city = data.get("name", location)
        country = data.get("sys", {}).get("country", "")
        temp = data.get("main", {}).get("temp", "N/A")
        feels_like = data.get("main", {}).get("feels_like", "N/A")
        humidity = data.get("main", {}).get("humidity", "N/A")
        description = data.get("weather", [{}])[0].get("description", "N/A")
        wind_speed = data.get("wind", {}).get("speed", "N/A")
        
        temp_unit = "°C" if units == "metric" else "°F"
        speed_unit = "m/s" if units == "metric" else "mph"
        
        formatted_info = [
            f"Thông tin thời tiết tại: {city}, {country}",
            f"Nhiệt độ: {temp} {temp_unit}",
            f"Cảm giác như: {feels_like} {temp_unit}",
            f"Độ ẩm: {humidity}%",
            f"Mô tả: {description}",
            f"Tốc độ gió: {wind_speed} {speed_unit}"
        ]
        
        return "\n".join(formatted_info)
        
    except requests.exceptions.RequestException as e:
        error_msg = f"Lỗi khi gọi Weather API: {str(e)}"
        logger.error(error_msg)
        return f"Lỗi: {error_msg}"
    except Exception as e:
        error_msg = f"Lỗi không xác định: {str(e)}"
        logger.error(error_msg)
        return f"Lỗi: {error_msg}"

