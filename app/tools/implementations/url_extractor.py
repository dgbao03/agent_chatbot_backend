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
            Extracted text content (title + body) or error message for
            expected content issues (empty page, JS-only, etc.)
            
        Raises:
            Exception: Network/HTTP errors (404, 403, timeout, connection)
                       propagate to the workflow for logging as tool_call_failed.
        """
        # Input validation — return string so LLM can respond gracefully
        if not url or not isinstance(url, str):
            return "Error: Invalid URL. Please provide a valid URL string."

        url = url.strip()

        if not url.startswith(("http://", "https://")):
            return "Error: Invalid URL format. URL must start with http:// or https://"

        # Network/parsing — exceptions propagate to workflow for accurate logging
        article = Article(url)
        article.download()
        article.parse()

        # Content quality check — expected outcome, not a system failure
        if not article.text or len(article.text.strip()) < 50:
            return "Error: Could not extract meaningful content from this URL. The page may be empty, require JavaScript, or contain only media content."

        title = article.title or "No title"
        text = article.text.strip()

        # Smart truncate to ~5000 characters (at sentence boundary)
        max_chars = 5000
        if len(text) > max_chars:
            truncated = text[:max_chars]
            last_period = truncated.rfind('.')
            if last_period > max_chars * 0.8:
                text = truncated[:last_period + 1]
            else:
                text = truncated + "..."
            text += "\n\n[Note: Article content was truncated due to length]"

        return f"Title: {title}\n\nContent:\n{text}"
