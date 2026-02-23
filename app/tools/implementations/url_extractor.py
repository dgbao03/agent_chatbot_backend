"""
URL Content Extractor Tool - Extract and read content from web pages.
"""
from newspaper import Article
from app.tools.base import BaseTool


class URLExtractorTool(BaseTool):
    """
    Tool for extracting content from website URLs using newspaper4k.
    """
    
    name = "extract_url_content"
    summary = "Extract content from a website URL for summarization. Use when user provides a URL and requests to read/summarize it."
    category = "content"
    description = """Extract and parse article text content from a web URL. Use when user provides URL and explicitly requests to read or summarize it (keywords: "summarize", "read", "extract"; examples: "Summarize https://techcrunch.com/article", "Read this article: https://..."). Requires valid http/https URL. Do NOT use when URL appears without summarize request; returns article title and text content."""
    
    def execute(self, url: str) -> str:
        """
        Extract content from a website URL.
        
        Args:
            url: Website URL (must start with http:// or https://)
            
        Returns:
            Extracted text content (title + body) or error message
        """
        try:
            # Validate URL format
            if not url or not isinstance(url, str):
                return "Error: Invalid URL. Please provide a valid URL string."
            
            url = url.strip()
            
            if not url.startswith(("http://", "https://")):
                return "Error: Invalid URL format. URL must start with http:// or https://"
            
            # Download and parse article
            article = Article(url)
            article.download()
            article.parse()
            
            # Check if content was extracted
            if not article.text or len(article.text.strip()) < 50:
                return "Error: Could not extract meaningful content from this URL. The page may be empty, require JavaScript, or contain only media content."
            
            # Get title and text
            title = article.title or "No title"
            text = article.text.strip()
            
            # Smart truncate to ~5000 characters (at sentence boundary)
            max_chars = 5000
            if len(text) > max_chars:
                truncated = text[:max_chars]
                # Find last period within limit
                last_period = truncated.rfind('.')
                if last_period > max_chars * 0.8:  # Only truncate if period is near end
                    text = truncated[:last_period + 1]
                else:
                    text = truncated + "..."
                
                text += "\n\n[Note: Article content was truncated due to length]"
            
            # Format output
            result = f"Title: {title}\n\nContent:\n{text}"
            
            return result
            
        except Exception as e:
            error_message = str(e)
            
            # Provide more specific error messages
            if "404" in error_message:
                return "Error: Page not found (404). Please check if the URL is correct."
            elif "403" in error_message or "Forbidden" in error_message:
                return "Error: Access forbidden (403). The website may be blocking automated access."
            elif "timeout" in error_message.lower():
                return "Error: Request timeout. The website took too long to respond."
            elif "connection" in error_message.lower():
                return "Error: Could not connect to the website. Please check your internet connection."
            else:
                return f"Error: Could not extract content from URL. {error_message}"
