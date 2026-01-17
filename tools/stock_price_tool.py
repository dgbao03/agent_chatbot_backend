"""
Stock Price Tool - Lấy giá cổ phiếu hiện tại sử dụng Finnhub API
"""

import os
import logging
from typing import Optional
from dotenv import load_dotenv
import requests
from datetime import datetime

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)


def get_stock_price(symbol: str) -> str:
    """
    Lấy giá cổ phiếu hiện tại cho một mã chứng khoán
    
    Args:
        symbol: Mã chứng khoán (ví dụ: "AAPL", "GOOGL", "MSFT", "TSLA")
        
    Returns:
        str: Thông tin giá cổ phiếu đã được format
    """
    try:
        api_key = os.getenv("FINNHUB_API_KEY")
        if not api_key:
            raise ValueError("FINNHUB_API_KEY không được tìm thấy trong environment variables")
        
        # Finnhub API endpoint
        base_url = "https://finnhub.io/api/v1/quote"
        
        params = {
            "symbol": symbol.upper(),  # Chuyển thành uppercase
            "token": api_key
        }
        
        # Gọi API
        response = requests.get(base_url, params=params, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        
        # Kiểm tra lỗi từ API
        if data.get("s") == "no_data":
            return f"Không tìm thấy dữ liệu cho mã cổ phiếu: {symbol.upper()}"
        
        # Lấy các giá trị
        current_price = data.get("c", "N/A")
        change = data.get("d", "N/A")
        percent_change = data.get("dp", "N/A")
        high = data.get("h", "N/A")
        low = data.get("l", "N/A")
        open_price = data.get("o", "N/A")
        previous_close = data.get("pc", "N/A")
        timestamp = data.get("t", None)
        
        # Format timestamp nếu có
        time_str = "N/A"
        if timestamp:
            try:
                dt = datetime.fromtimestamp(timestamp)
                time_str = dt.strftime("%Y-%m-%d %H:%M:%S")
            except:
                time_str = str(timestamp)
        
        # Format kết quả
        formatted_info = [
            f"Thông tin giá cổ phiếu: {symbol.upper()}",
            f"Giá hiện tại: ${current_price}" if isinstance(current_price, (int, float)) else f"Giá hiện tại: {current_price}",
            f"Thay đổi: ${change}" if isinstance(change, (int, float)) else f"Thay đổi: {change}",
            f"Phần trăm thay đổi: {percent_change}%" if isinstance(percent_change, (int, float)) else f"Phần trăm thay đổi: {percent_change}",
            f"Giá cao nhất trong ngày: ${high}" if isinstance(high, (int, float)) else f"Giá cao nhất trong ngày: {high}",
            f"Giá thấp nhất trong ngày: ${low}" if isinstance(low, (int, float)) else f"Giá thấp nhất trong ngày: {low}",
            f"Giá mở cửa: ${open_price}" if isinstance(open_price, (int, float)) else f"Giá mở cửa: {open_price}",
            f"Giá đóng cửa trước đó: ${previous_close}" if isinstance(previous_close, (int, float)) else f"Giá đóng cửa trước đó: {previous_close}",
            f"Thời điểm cập nhật: {time_str}"
        ]
        
        return "\n".join(formatted_info)
        
    except requests.exceptions.RequestException as e:
        error_msg = f"Lỗi khi gọi Finnhub API: {str(e)}"
        logger.error(error_msg)
        return f"Lỗi: {error_msg}"
    except Exception as e:
        error_msg = f"Lỗi không xác định: {str(e)}"
        logger.error(error_msg)
        return f"Lỗi: {error_msg}"

