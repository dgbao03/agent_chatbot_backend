def _split_messages_for_summary(messages: list, is_empty_truncated: bool = False) -> tuple[list, list]:
    """
    Chia messages thành 80% (để summary) và 20% (giữ lại).
    Đảm bảo:
    - 80% luôn là cặp user-assistant (từ đầu)
    - 20% luôn bắt đầu với user message (từ cuối)
    
    Nếu is_empty_truncated = True: summary toàn bộ messages, không giữ lại gì.
    
    Args:
        messages: List các ChatMessage
        is_empty_truncated: Flag cho biết truncated_messages_list rỗng
        
    Returns:
        tuple: (messages_to_summarize, messages_to_keep)
    """
    if not messages:
        return [], []
    
    # Nếu truncated_messages_list rỗng, summary toàn bộ messages
    if is_empty_truncated:
        return messages, []
    
    total_count = len(messages)
    keep_count = max(1, int(total_count * 0.2))  # 20%, tối thiểu 1 message
    
    # Tìm user message cuối cùng trong toàn bộ messages
    last_user_idx = -1
    for i in range(total_count - 1, -1, -1):
        if messages[i].role.value == "user":
            last_user_idx = i
            break
    
    if last_user_idx == -1:
        # Nếu không có user message nào, không giữ lại gì
        return messages, []
    
    # Tính số lượng messages muốn giữ (20%)
    target_keep_count = max(2, int(total_count * 0.2))  # Tối thiểu 2 (1 cặp user-assistant)
    
    # Bắt đầu từ user message cuối cùng, lấy các cặp user-assistant
    keep_start_idx = last_user_idx
    
    # Đếm số cặp user-assistant từ keep_start_idx đến cuối
    valid_pairs = 0
    i = keep_start_idx
    while i < total_count - 1:
        if messages[i].role.value == "user" and messages[i+1].role.value == "assistant":
            valid_pairs += 1
            i += 2
        else:
            break
    
    # Nếu số cặp hợp lệ ít hơn target, tìm thêm cặp từ trước đó
    if valid_pairs * 2 < target_keep_count:
        # Tìm ngược lại từ keep_start_idx - 1
        for i in range(keep_start_idx - 1, -1, -1):
            if i + 1 < total_count and messages[i].role.value == "user" and messages[i+1].role.value == "assistant":
                keep_start_idx = i
                valid_pairs += 1
                if valid_pairs * 2 >= target_keep_count:
                    break
    
    # Đảm bảo có ít nhất 1 cặp user-assistant
    if valid_pairs == 0:
        # Nếu không có cặp nào, chỉ giữ user message cuối cùng (không hợp lệ nhưng tốt hơn không có gì)
        keep_start_idx = last_user_idx
        keep_count = 1
    else:
        keep_count = valid_pairs * 2
    
    messages_to_keep = messages[keep_start_idx:keep_start_idx + keep_count]
    messages_to_summarize = messages[:keep_start_idx]
    
    return messages_to_summarize, messages_to_keep

