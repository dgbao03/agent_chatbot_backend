"""
Title generator - N-gram + Pattern matching approach
Fast, no external dependencies, no LLM calls
"""
import re
from typing import Optional


def generate_conversation_title(user_input: str) -> str:
    """
    Generate conversation title từ user input.
    Ưu tiên tốc độ - không dùng LLM, không cần NLP library.
    
    Args:
        user_input: User message đầu tiên
        
    Returns:
        Title string (max 60 characters)
    """
    user_input = user_input.strip()
    
    # Case 1: Input ngắn (< 60 chars) → dùng trực tiếp
    if len(user_input) <= 60:
        return user_input
    
    # Case 2: Extract cụm từ quan trọng bằng pattern matching
    important_phrase = extract_important_phrase(user_input)
    if important_phrase and len(important_phrase) <= 60:
        return format_title(important_phrase)
    
    # Case 3: Extract keyword đơn lẻ
    keyword = extract_main_keyword(user_input)
    if keyword and len(keyword) <= 60:
        return format_title(keyword)
    
    # Case 4: Fallback - truncate thông minh
    return smart_truncate(user_input, max_length=60)


def extract_important_phrase(text: str) -> Optional[str]:
    """
    Tìm cụm từ quan trọng (2-3 words) bằng pattern matching.
    Ưu tiên các pattern: "about X", "for X", "on X", "regarding X"
    """
    text_lower = text.lower()
    
    # Pattern 1: "about/for/on/regarding [phrase]"
    patterns = [
        r'\b(?:about|for|on|regarding|concerning)\s+([a-z]+(?:\s+[a-z]+){0,2})',
        r'\b(?:create|make|build|design|develop)\s+(?:a|an|the)?\s*([a-z]+(?:\s+[a-z]+){0,2})',
        r'\b(?:presentation|document|report|article|essay|paper)\s+(?:about|on|for)\s+([a-z]+(?:\s+[a-z]+){0,2})',
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, text_lower)
        if matches:
            # Lấy match đầu tiên (thường là quan trọng nhất)
            phrase = matches[0].strip()
            if 5 <= len(phrase) <= 50:  # Độ dài hợp lý
                return phrase
    
    # Pattern 2: Tìm cụm từ kỹ thuật (2-3 words liên tiếp, không có stop words)
    technical_phrases = find_technical_phrases(text_lower)
    if technical_phrases:
        return technical_phrases[0]
    
    return None


def find_technical_phrases(text: str) -> list[str]:
    """
    Tìm các cụm từ kỹ thuật (2-3 words) không chứa stop words.
    """
    stop_words = {
        'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
        'of', 'with', 'by', 'from', 'as', 'is', 'are', 'was', 'were', 'be',
        'been', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would',
        'could', 'should', 'may', 'might', 'can', 'this', 'that', 'these',
        'those', 'i', 'you', 'he', 'she', 'it', 'we', 'they', 'me', 'him',
        'her', 'us', 'them', 'my', 'your', 'his', 'her', 'its', 'our', 'their',
        'what', 'which', 'who', 'whom', 'whose', 'where', 'when', 'why', 'how',
        'about', 'help', 'want', 'need', 'create', 'make', 'build', 'get', 'some'
    }
    
    words = re.findall(r'\b\w+\b', text)
    phrases = []
    
    # Tạo bigrams (2 words)
    for i in range(len(words) - 1):
        word1 = words[i].lower()
        word2 = words[i + 1].lower()
        if word1 not in stop_words and word2 not in stop_words:
            phrase = f"{word1} {word2}"
            if 5 <= len(phrase) <= 50:
                phrases.append(phrase)
    
    # Tạo trigrams (3 words) nếu bigram không đủ
    if not phrases:
        for i in range(len(words) - 2):
            word1 = words[i].lower()
            word2 = words[i + 1].lower()
            word3 = words[i + 2].lower()
            if (word1 not in stop_words and 
                word2 not in stop_words and 
                word3 not in stop_words):
                phrase = f"{word1} {word2} {word3}"
                if 5 <= len(phrase) <= 50:
                    phrases.append(phrase)
    
    # Sort by length (ưu tiên cụm từ dài hơn - thường mô tả rõ hơn)
    phrases.sort(key=len, reverse=True)
    return phrases


def extract_main_keyword(text: str) -> Optional[str]:
    """
    Extract keyword đơn lẻ quan trọng nhất.
    Ưu tiên: danh từ, tên riêng, từ dài (> 3 chars)
    """
    stop_words = {
        'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
        'of', 'with', 'by', 'from', 'as', 'is', 'are', 'was', 'were', 'be',
        'been', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would',
        'could', 'should', 'may', 'might', 'can', 'this', 'that', 'these',
        'those', 'i', 'you', 'he', 'she', 'it', 'we', 'they', 'me', 'him',
        'her', 'us', 'them', 'my', 'your', 'his', 'her', 'its', 'our', 'their',
        'what', 'which', 'who', 'whom', 'whose', 'where', 'when', 'why', 'how',
        'about', 'help', 'want', 'need', 'create', 'make', 'build', 'get', 'some',
        'hi', 'hello', 'hey', 'thanks', 'thank', 'please'
    }
    
    words = re.findall(r'\b\w+\b', text.lower())
    
    # Loại bỏ stop words và từ ngắn
    keywords = [w for w in words if w not in stop_words and len(w) > 3]
    
    if not keywords:
        return None
    
    # Ưu tiên từ dài hơn (thường là keyword quan trọng hơn)
    keywords.sort(key=len, reverse=True)
    return keywords[0]


def format_title(text: str) -> str:
    """
    Format title: capitalize mỗi từ, loại bỏ punctuation cuối.
    """
    # Loại bỏ punctuation ở cuối
    text = text.rstrip('.,!?;:')
    
    # Capitalize mỗi từ
    words = text.split()
    formatted_words = [word.capitalize() for word in words]
    
    return ' '.join(formatted_words)


def smart_truncate(text: str, max_length: int = 60) -> str:
    """
    Truncate thông minh: cắt tại dấu câu hoặc từ, không cắt giữa từ.
    """
    if len(text) <= max_length:
        return text
    
    # Tìm vị trí cắt tốt nhất (tại dấu câu hoặc space)
    cut_pos = max_length
    
    # Ưu tiên cắt tại dấu câu
    for punct in ['.', '!', '?', ';', ':']:
        pos = text.rfind(punct, 0, max_length)
        if pos > max_length * 0.5:  # Chỉ cắt nếu không quá sớm
            cut_pos = pos + 1
            break
    
    # Nếu không có dấu câu, cắt tại space
    if cut_pos == max_length:
        pos = text.rfind(' ', 0, max_length)
        if pos > max_length * 0.5:
            cut_pos = pos
    
    result = text[:cut_pos].strip()
    
    # Thêm "..." nếu bị cắt
    if len(text) > cut_pos:
        result += "..."
    
    return result

