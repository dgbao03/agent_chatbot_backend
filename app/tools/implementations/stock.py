"""
Stock Tool - Get stock price information by symbol.
"""
from app.tools.base import BaseTool


class StockTool(BaseTool):
    """
    Tool for getting stock price information by symbol.
    """
    
    name = "get_stock_price"
    summary = "Lấy giá cổ phiếu theo mã ticker. Sử dụng khi user hỏi về giá cổ phiếu."
    category = "external_api"
    description = """
Lấy thông tin giá cổ phiếu theo mã cổ phiếu. Input: Mã cổ phiếu.
Lưu ý: Chỉ sử dụng khi User yêu cầu thông tin giá cổ phiếu của một công ty cụ thể.
Không sử dụng khi trong Request có mã cổ phiếu/địa danh/tên công ty nhưng không yêu cầu thông tin giá cổ phiếu."""
    
    def execute(self, symbol: str) -> str:
        """
        Get stock price information for a symbol.
        
        Args:
            symbol: Stock symbol/ticker
            
        Returns:
            Stock price information string
        """
        return f"[STOCK PRICE] {symbol}: 100$ (up 10%)"
