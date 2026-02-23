"""
Title generator - N-gram + Pattern matching approach
Fast, no external dependencies, no LLM calls
"""
import re
from typing import Optional


def generate_conversation_title(user_input: str) -> str:
    """
    Generate conversation title from user input.
    Prioritizes speed - no LLM calls, no NLP library required.
    
    Args:
        user_input: First user message
        
    Returns:
        Title string (max 60 characters)
    """
    user_input = user_input.strip()
    
    # Case 1: Short input (< 60 chars) → use directly
    if len(user_input) <= 60:
        return user_input
    
    # Case 2: Extract important phrase via pattern matching
    important_phrase = extract_important_phrase(user_input)
    if important_phrase and len(important_phrase) <= 60:
        return format_title(important_phrase)
    
    # Case 3: Extract single keyword
    keyword = extract_main_keyword(user_input)
    if keyword and len(keyword) <= 60:
        return format_title(keyword)
    
    # Case 4: Fallback - smart truncate
    return smart_truncate(user_input, max_length=60)


def extract_important_phrase(text: str) -> Optional[str]:
    """
    Find important phrase (2-3 words) via pattern matching.
    Prioritizes patterns: "about X", "for X", "on X", "regarding X"
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
            # Take the first match (usually the most important)
            phrase = matches[0].strip()
            if 5 <= len(phrase) <= 50:  # Reasonable length
                return phrase
    
    # Pattern 2: Find technical phrases (2-3 consecutive words, no stop words)
    technical_phrases = find_technical_phrases(text_lower)
    if technical_phrases:
        return technical_phrases[0]
    
    return None


def find_technical_phrases(text: str) -> list[str]:
    """
    Find technical phrases (2-3 words) without stop words.
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
    
    # Build bigrams (2 words)
    for i in range(len(words) - 1):
        word1 = words[i].lower()
        word2 = words[i + 1].lower()
        if word1 not in stop_words and word2 not in stop_words:
            phrase = f"{word1} {word2}"
            if 5 <= len(phrase) <= 50:
                phrases.append(phrase)
    
    # Build trigrams (3 words) if no bigrams found
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
    
    # Sort by length (prefer longer phrases - usually more descriptive)
    phrases.sort(key=len, reverse=True)
    return phrases


def extract_main_keyword(text: str) -> Optional[str]:
    """
    Extract the most important single keyword.
    Prioritizes: nouns, proper nouns, long words (> 3 chars)
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
    
    # Remove stop words and short words
    keywords = [w for w in words if w not in stop_words and len(w) > 3]
    
    if not keywords:
        return None
    
    # Prefer longer words (usually more important keywords)
    keywords.sort(key=len, reverse=True)
    return keywords[0]


def format_title(text: str) -> str:
    """
    Format title: capitalize each word, remove trailing punctuation.
    """
    # Remove trailing punctuation
    text = text.rstrip('.,!?;:')
    
    # Capitalize each word
    words = text.split()
    formatted_words = [word.capitalize() for word in words]
    
    return ' '.join(formatted_words)


def smart_truncate(text: str, max_length: int = 60) -> str:
    """
    Smart truncate: cut at punctuation or word boundary, never mid-word.
    """
    if len(text) <= max_length:
        return text
    
    # Find the best cut position (at punctuation or space)
    cut_pos = max_length
    
    # Prefer cutting at punctuation
    for punct in ['.', '!', '?', ';', ':']:
        pos = text.rfind(punct, 0, max_length)
        if pos > max_length * 0.5:  # Only cut if not too early
            cut_pos = pos + 1
            break
    
    # If no punctuation found, cut at space
    if cut_pos == max_length:
        pos = text.rfind(' ', 0, max_length)
        if pos > max_length * 0.5:
            cut_pos = pos
    
    result = text[:cut_pos].strip()
    
    # Append '...' if truncated
    if len(text) > cut_pos:
        result += "..."
    
    return result

