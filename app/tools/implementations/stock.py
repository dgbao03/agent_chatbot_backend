"""
Stock Tool - Get stock price information by symbol.
"""
from app.tools.base import BaseTool


class StockTool(BaseTool):
    """
    Tool for getting stock price information by symbol.
    """
    
    name = "get_stock_price"
    summary = "Get stock price by ticker symbol. Use when user asks about stock prices."
    category = "external_api"
    description = """Fetch real-time stock price by ticker symbol. Use when user explicitly asks about stock price of a specific company (e.g., "AAPL price?", "stock price of TSLA"). Do NOT use when company name appears in context without a price request; returns current price and change percentage."""
    
    def execute(self, symbol: str) -> str:
        """
        Get stock price information for a symbol.
        
        Args:
            symbol: Stock symbol/ticker
            
        Returns:
            Stock price information string
        """
        return f"[STOCK PRICE] {symbol}: 100$ (up 10%)"
