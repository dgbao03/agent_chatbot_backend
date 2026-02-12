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
    category = "content"
    description = """
Trích xuất và đọc nội dung từ một trang web URL để tóm tắt.

Sử dụng công cụ này khi:
- User cung cấp URL và yêu cầu tóm tắt/đọc nội dung
- Keywords: "tóm tắt link", "tóm tắt URL", "đọc bài viết từ", "summarize", "đọc nội dung"

Input: URL đầy đủ (phải bắt đầu với http:// hoặc https://)
Output: Tiêu đề và nội dung văn bản của bài viết

Ví dụ sử dụng:
- "Tóm tắt https://techcrunch.com/article"
- "Đọc và tóm tắt nội dung từ link này: https://..."
- "Summarize the article at https://..."

KHÔNG sử dụng khi:
- Câu hỏi chung không có URL
- URL chỉ là ngữ cảnh nhưng không yêu cầu tóm tắt

Sau khi nhận được nội dung, hãy tạo bản tóm tắt ngắn gọn, rõ ràng cho người dùng."""
    
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
