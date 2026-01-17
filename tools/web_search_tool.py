"""
Web Search Tool - Sử dụng Tavily API để tìm kiếm thông tin trên web
"""

import os
import logging
from typing import Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)


def web_search_tool(query: str) -> str:
    """
    Khi người dùng yêu cầu tìm kiếm thông tin trên web, hãy sử dụng công cụ này để tìm kiếm thông tin trên web.
    
    Args:
        query: Câu truy vấn tìm kiếm
        
    Returns:
        str: Kết quả tìm kiếm đã được format
    """
    try:
        from tavily import TavilyClient
        
        api_key = os.getenv("TAVILY_API_KEY")
        if not api_key:
            raise ValueError("TAVILY_API_KEY không được tìm thấy trong environment variables")
        
        # Khởi tạo Tavily client
        client = TavilyClient(api_key=api_key)
        
        # Thực hiện search
        response = client.search(
            query=query,
            search_depth="advanced",  # advanced để có kết quả chi tiết hơn
            max_results=5,  # Lấy tối đa 5 kết quả
        )
        
        # Format kết quả
        if not response.get("results"):
            return f"Không tìm thấy kết quả nào cho query: {query}"
        
        formatted_results = []
        formatted_results.append(f"Kết quả tìm kiếm cho: {query}\n")
        
        for i, result in enumerate(response["results"], 1):
            title = result.get("title", "Không có tiêu đề")
            url = result.get("url", "")
            content = result.get("content", "")
            
            formatted_results.append(f"[{i}] {title}")
            formatted_results.append(f"URL: {url}")
            formatted_results.append(f"Nội dung: {content[:500]}...")  # Giới hạn 500 ký tự
            formatted_results.append("")  # Dòng trống
        
        return "\n".join(formatted_results)
        
    except ImportError:
        error_msg = "Tavily client chưa được cài đặt. Vui lòng cài đặt: pip install tavily-python"
        logger.error(error_msg)
        return f"Lỗi: {error_msg}"
    except Exception as e:
        error_msg = f"Lỗi khi tìm kiếm: {str(e)}"
        logger.error(error_msg)
        return f"Lỗi: {error_msg}"

