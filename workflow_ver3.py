from pydantic import BaseModel, Field
from typing import Literal, Optional
import json
import os
import hashlib
from pathlib import Path

class RouterOutput(BaseModel):
    intent: Literal["PPTX", "GENERAL"] = Field(
        description="Loại intent của người dùng: PPTX nếu muốn tạo slide/presentation, GENERAL cho các câu hỏi thông thường"
    )
    answer: Optional[str] = Field(
        default=None,
        description="Câu trả lời cho câu hỏi của người dùng. Chỉ có giá trị khi intent là GENERAL, phải là null khi intent là PPTX"
    )

from dotenv import load_dotenv
load_dotenv()

from llama_index.llms.openai import OpenAI
from llama_index.core.workflow import Workflow, Context, step
from llama_index.core.workflow.events import StartEvent, StopEvent
from llama_index.core.llms import ChatMessage, MessageRole
from llama_index.core.memory import ChatMemoryBuffer

llm = OpenAI(model="gpt-4o-mini")

from llama_index.core.tools import FunctionTool

# ==================== Chat History Helper Functions ====================

CHAT_HISTORY_FILE = Path(__file__).parent / "database" / "recent_chat_history.json"
CHAT_SUMMARY_FILE = Path(__file__).parent / "database" / "chat_summary.json"

def _load_chat_history() -> list:
    """Load recent chat history từ file JSON. Trả về list rỗng nếu file không tồn tại hoặc lỗi."""
    try:
        if not CHAT_HISTORY_FILE.exists():
            return []

        with open(CHAT_HISTORY_FILE, "r", encoding="utf-8") as f:
            content = f.read().strip()
            if not content:
                return []
            history = json.loads(content)
            if not isinstance(history, list):
                return []
            return history
    except (json.JSONDecodeError, IOError, Exception) as e:
        print(f"Lỗi khi đọc recent_chat_history.json: {e}")
        return []

def _save_chat_history(history: list) -> bool:
    """Lưu recent chat history vào file JSON. Trả về True nếu thành công."""
    try:
        CHAT_HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
        temp_file = CHAT_HISTORY_FILE.with_suffix(".tmp")
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
        temp_file.replace(CHAT_HISTORY_FILE)
        return True
    except (IOError, Exception) as e:
        print(f"Lỗi khi ghi recent_chat_history.json: {e}")
        return False

# ==================== Chat Summary Helper Functions ====================

def _load_chat_summary() -> dict:
    """
    Load chat summary từ file JSON.
    
    Returns:
        dict: {"version": int, "summary_content": str} hoặc {"version": 0, "summary_content": ""} nếu không có
    """
    try:
        if not CHAT_SUMMARY_FILE.exists():
            return {"version": 0, "summary_content": ""}
        
        with open(CHAT_SUMMARY_FILE, "r", encoding="utf-8") as f:
            content = f.read().strip()
            if not content:
                return {"version": 0, "summary_content": ""}
            data = json.loads(content)
            if not isinstance(data, dict):
                return {"version": 0, "summary_content": ""}
            return {
                "version": data.get("version", 0),
                "summary_content": data.get("summary_content", "")
            }
    except (json.JSONDecodeError, IOError, Exception) as e:
        print(f"Lỗi khi đọc chat_summary.json: {e}")
        return {"version": 0, "summary_content": ""}

def _save_chat_summary(version: int, summary_content: str) -> bool:
    """
    Lưu chat summary vào file JSON.
    
    Args:
        version: Version number
        summary_content: Nội dung summary
        
    Returns:
        bool: True nếu thành công
    """
    try:
        CHAT_SUMMARY_FILE.parent.mkdir(parents=True, exist_ok=True)
        temp_file = CHAT_SUMMARY_FILE.with_suffix(".tmp")
        data = {
            "version": version,
            "summary_content": summary_content
        }
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        temp_file.replace(CHAT_SUMMARY_FILE)
        return True
    except (IOError, Exception) as e:
        print(f"Lỗi khi ghi chat_summary.json: {e}")
        return False

def _format_messages_for_summary(messages: list) -> str:
    """
    Format messages thành text để gửi cho LLM summary.
    
    Args:
        messages: List các ChatMessage
        
    Returns:
        str: Formatted text
    """
    formatted_lines = []
    for i, msg in enumerate(messages, 1):
        role = msg.role.value
        content = msg.content if hasattr(msg, 'content') else str(msg)
        formatted_lines.append(f"{role.capitalize()}: {content}")
    
    return "\n".join(formatted_lines)

async def _create_summary(messages: list) -> str:
    """
    Tạo summary từ messages, kết hợp với summary cũ nếu có.
    
    Args:
        messages: List các ChatMessage cần summary
        
    Returns:
        str: Summary text
    """
    try:
        # Load summary cũ
        old_summary_data = _load_chat_summary()
        old_version = old_summary_data["version"]
        old_summary = old_summary_data["summary_content"]
        
        # Format messages mới
        formatted_messages = _format_messages_for_summary(messages)
        
        # Tạo prompt cho LLM
        if old_version == 0:
            # Lần đầu tiên, không có summary cũ
            system_prompt = (
                "Bạn là một AI chuyên tạo tóm tắt cuộc hội thoại.\n"
                "Nhiệm vụ: Tóm tắt ngắn gọn các điểm chính của cuộc hội thoại.\n"
                "Tập trung vào:\n"
                "- Các chủ đề chính được thảo luận\n"
                "- Thông tin quan trọng được chia sẻ\n"
                "- Kết luận hoặc kết quả (nếu có)"
            )
            user_prompt = f"Hãy tóm tắt cuộc hội thoại sau đây:\n\n{formatted_messages}"
        else:
            # Có summary cũ, kết hợp với messages mới
            system_prompt = (
                "Bạn là một AI chuyên tạo tóm tắt tích lũy cuộc hội thoại.\n"
                "Nhiệm vụ: Tạo tóm tắt mới bằng cách kết hợp tóm tắt cũ với cuộc hội thoại mới.\n"
                "Yêu cầu:\n"
                "- Giữ lại thông tin quan trọng từ tóm tắt cũ\n"
                "- Bổ sung thông tin mới từ cuộc hội thoại\n"
                "- Tạo tóm tắt ngắn gọn, không lặp lại"
            )
            user_prompt = (
                f"Tóm tắt cũ (version {old_version}):\n{old_summary}\n\n"
                f"Cuộc hội thoại mới:\n{formatted_messages}\n\n"
                f"Hãy tạo tóm tắt mới kết hợp cả hai phần trên."
            )
        
        # Gọi LLM để tạo summary
        llm_messages = [
            ChatMessage(role=MessageRole.SYSTEM, content=system_prompt),
            ChatMessage(role=MessageRole.USER, content=user_prompt)
        ]
        
        response = await llm.achat(llm_messages)
        
        # Lấy content từ response
        if hasattr(response, 'message') and hasattr(response.message, 'content'):
            summary_text = str(response.message.content)
        elif hasattr(response, 'content'):
            summary_text = str(response.content)
        else:
            summary_text = str(response)
        
        # Lưu summary mới với version tăng lên
        new_version = old_version + 1
        _save_chat_summary(new_version, summary_text)
        
        print(f"Summary created: version {new_version} (previous: {old_version})")
        
        return summary_text
        
    except Exception as e:
        print(f"Lỗi khi tạo summary: {e}")
        # Fallback: trả về summary đơn giản
        user_count = sum(1 for msg in messages if msg.role.value == "user")
        assistant_count = sum(1 for msg in messages if msg.role.value == "assistant")
        return f"[SUMMARY] Đã tóm tắt {user_count} lượt hỏi và {assistant_count} lượt trả lời từ cuộc hội thoại trước đó."

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

# ==================== User Facts Helper Functions ====================

USER_FACTS_FILE = Path(__file__).parent / "database" / "user_facts.json"

def _load_user_facts() -> list:
    """Load user facts từ file JSON. Trả về list rỗng nếu file không tồn tại hoặc lỗi."""
    try:
        if not USER_FACTS_FILE.exists():
            return []
        
        with open(USER_FACTS_FILE, "r", encoding="utf-8") as f:
            content = f.read().strip()
            if not content:
                return []
            facts = json.loads(content)
            if not isinstance(facts, list):
                return []
            return facts
    except (json.JSONDecodeError, IOError, Exception) as e:
        print(f"Lỗi khi đọc user_facts.json: {e}")
        return []

def _save_user_facts(facts: list) -> bool:
    """Lưu user facts vào file JSON. Trả về True nếu thành công."""
    try:
        # Đảm bảo thư mục tồn tại
        USER_FACTS_FILE.parent.mkdir(parents=True, exist_ok=True)
        
        # Atomic write: ghi vào file tạm rồi rename
        temp_file = USER_FACTS_FILE.with_suffix(".tmp")
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(facts, f, ensure_ascii=False, indent=2)
        
        # Rename file tạm thành file chính
        temp_file.replace(USER_FACTS_FILE)
        return True
    except (IOError, Exception) as e:
        print(f"Lỗi khi ghi user_facts.json: {e}")
        return False

def _find_fact_by_key(facts: list, key: str) -> Optional[dict]:
    """Tìm fact theo key (không phân biệt hoa thường). Trả về dict hoặc None."""
    key_lower = key.lower().strip()
    for fact in facts:
        if isinstance(fact, dict) and fact.get("key", "").lower().strip() == key_lower:
            return fact
    return None

def _format_user_facts_for_prompt() -> str:
    """Format user facts thành text để thêm vào System Prompt. Trả về chuỗi rỗng nếu không có facts."""
    try:
        facts = _load_user_facts()
        if not facts:
            return ""
        
        formatted_lines = ["USER FACTS (Thông tin về người dùng):"]
        for fact in facts:
            if isinstance(fact, dict) and "key" in fact and "value" in fact:
                formatted_lines.append(f"- {fact['key']}: {fact['value']}")
        
        if len(formatted_lines) == 1:  # Chỉ có header, không có facts
            return ""
        
        return "\n".join(formatted_lines)
    except Exception as e:
        print(f"Lỗi khi format user facts cho prompt: {e}")
        return ""

# ==================== User Facts Tool Functions ====================

def add_user_fact(key: str, value: str) -> str:
    try:
        if not key or not key.strip():
            return "Lỗi: Key không được để trống."
        
        if not value or not value.strip():
            return "Lỗi: Value không được để trống."
        
        facts = _load_user_facts()
        key_clean = key.strip()
        value_clean = value.strip()
        
        # Kiểm tra key đã tồn tại chưa
        existing_fact = _find_fact_by_key(facts, key_clean)
        
        if existing_fact:
            # Cập nhật fact hiện có
            existing_fact["value"] = value_clean
            if _save_user_facts(facts):
                return f"Đã cập nhật: {key_clean} = {value_clean}"
            else:
                return "Lỗi: Không thể lưu thông tin."
        else:
            # Thêm fact mới
            new_fact = {"key": key_clean, "value": value_clean}
            facts.append(new_fact)
            if _save_user_facts(facts):
                return f"Đã lưu: {key_clean} = {value_clean}"
            else:
                return "Lỗi: Không thể lưu thông tin."
                
    except Exception as e:
        return f"Lỗi khi thêm user fact: {str(e)}"

def update_user_fact(key: str, value: str) -> str:
    try:
        if not key or not key.strip():
            return "Lỗi: Key không được để trống."
        
        if not value or not value.strip():
            return "Lỗi: Value không được để trống."
        
        facts = _load_user_facts()
        key_clean = key.strip()
        value_clean = value.strip()
        
        # Tìm fact theo key
        fact = _find_fact_by_key(facts, key_clean)
        
        if fact:
            fact["value"] = value_clean
            if _save_user_facts(facts):
                return f"Đã cập nhật: {key_clean} = {value_clean}"
            else:
                return "Lỗi: Không thể lưu thông tin."
        else:
            return f"Không tìm thấy thông tin với key: {key_clean}. Sử dụng add_user_fact để thêm mới."
                
    except Exception as e:
        return f"Lỗi khi cập nhật user fact: {str(e)}"

def delete_user_fact(key: str) -> str:
    try:
        if not key or not key.strip():
            return "Lỗi: Key không được để trống."
        
        facts = _load_user_facts()
        key_clean = key.strip()
        
        # Tìm và xóa fact
        fact = _find_fact_by_key(facts, key_clean)
        
        if fact:
            facts.remove(fact)
            if _save_user_facts(facts):
                return f"Đã xóa thông tin: {key_clean}"
            else:
                return "Lỗi: Không thể lưu thông tin."
        else:
            return f"Không tìm thấy thông tin với key: {key_clean}"
                
    except Exception as e:
        return f"Lỗi khi xóa user fact: {str(e)}"

# ==================== Existing Tools ====================

def get_weather(city: str) -> str:
    return f"[WEATHER] {city}: 30°C, nắng nhẹ"

def get_stock_price(symbol: str) -> str:
    return f"[STOCK PRICE] {symbol}: 100$ (up 10%)"

tools = [
    FunctionTool.from_defaults(
        fn=get_weather,
        name="get_weather",
        description="Lấy thông tin thời tiết theo thành phố. Sử dụng khi người dùng hỏi về thời tiết của một thành phố cụ thể"
    ), 
    FunctionTool.from_defaults(
        fn=get_stock_price,
        name="get_stock_price",
        description="Lấy thông tin giá cổ phiếu theo mã cổ phiếu. Sử dụng khi người dùng hỏi về giá cổ phiếu của một công ty cụ thể"
    ),
    FunctionTool.from_defaults(
        fn=add_user_fact,
        name="add_user_fact",
        description="Thêm hoặc cập nhật user fact. Khi người dùng yêu cầu thêm thông tin, ví dụ: 'Lưu lại rằng tôi tên là Bao Do', 'Nhớ rằng tôi sống ở Hà Nội'. Nếu key đã tồn tại, giá trị mới sẽ thay thế giá trị cũ. Các thông tin sẽ được lưu dưới dạng key-value (ví dụ: 'name': 'Bao Do', 'location': 'Hà Nội')."
    ),
    FunctionTool.from_defaults(
        fn=update_user_fact,
        name="update_user_fact",
        description="Cập nhật user fact theo key. Nếu key không tồn tại, công cụ sẽ báo lỗi. Ví dụ: khi người dùng yêu cầu sửa đổi 'tuổi tôi là 30' hoặc 'tên tôi là Bao Do', công cụ sẽ cập nhật thông tin tương ứng. Nếu key không có, sẽ trả về lỗi như 'Key không tồn tại'."
    ),
    FunctionTool.from_defaults(
        fn=delete_user_fact,
        name="delete_user_fact",
        description="Xóa user fact theo key. Ví dụ: nếu người dùng yêu cầu 'Xóa tên tôi' hoặc 'Xóa tuổi tôi', công cụ sẽ xóa key tương ứng. Nếu không tìm thấy key, trả về lỗi như 'Không tìm thấy thông tin'. Sau khi xóa, trả về thông báo thành công."
    )
]

class RouterWorkflow(Workflow):

    @step
    async def route_and_answer(self, ctx: Context, ev: StartEvent) -> StopEvent:
        user_input = ev.user_input

        openai_tools = [tool.metadata.to_openai_tool() for tool in tools]

        chat_history = _load_chat_history()

        # Memory
        memory = ChatMemoryBuffer.from_defaults(token_limit=200)
        await ctx.store.set("chat_history", memory)

        for chat in chat_history:
            memory.put(ChatMessage(role=chat["role"], content=chat["content"]))

        history = memory.get()

        # Load và format user facts để thêm vào System Prompt
        user_facts_text = _format_user_facts_for_prompt()
        
        # Tạo System Prompt content
        system_content = (
            "You are an AI router and answerer.\n\n"
            "Decide intent and answer if needed.\n\n"
        )
        
        # Thêm user facts nếu có
        if user_facts_text:
            system_content += user_facts_text + "\n\n"
        
        system_content += (
            "INTENT RULES:\n"
            "- If user wants slides / presentation / PPT → intent = PPTX\n"
            "- Otherwise → intent = GENERAL\n\n"
            "TOOL RULES:\n"
            "- Use tools ONLY if intent is GENERAL and information is needed\n"
            "- You may call multiple tools\n\n"
            "FINAL RESPONSE RULES (QUAN TRỌNG - KHÔNG CÓ NGOẠI LỆ):\n"
            "BẮT BUỘC: Bạn PHẢI luôn luôn trả về đúng format JSON, KHÔNG CÓ NGOẠI LỆ!\n"
            "Dù bạn đã biết thông tin từ System Prompt hay từ bất kỳ nguồn nào, bạn VẪN PHẢI trả về JSON format!\n"
            "KHÔNG BAO GIỜ trả về plain text, chỉ trả về JSON!\n\n"
            "- When you are done, respond ONLY with valid JSON:\n"
            "{\n"
            '  "intent": "PPTX | GENERAL",\n'
            '  "answer": "string | null"\n'
            "}\n"
            "- If intent is PPTX → answer MUST be null\n"
            "- If intent is GENERAL → answer MUST be provided, always return a response, cannot be none or null, ...\n"
            "- Do NOT include any extra text outside JSON\n"
            "- REMEMBER: ALWAYS return JSON format, NO EXCEPTIONS, NO PLAIN TEXT!"
        )
        
        # Format history vào System Prompt nếu có
        if history:
            history_text = "\n===== RECENT CHAT HISTORY =====\n"
            for msg in history:
                history_text += f"{msg.role.value}: {msg.content}\n"
            system_content += "\n\n" + history_text
        
        # Load và thêm chat summary nếu có (sau Chat History)
        summary_data = _load_chat_summary()
        if summary_data["version"] > 0 and summary_data["summary_content"]:
            summary_text = f"\n===== CONVERSATION SUMMARY =====\n{summary_data['summary_content']}"
            system_content += summary_text

        messages = [
            ChatMessage(
                role=MessageRole.SYSTEM,
                content=system_content
            )
        ]

        messages.append(ChatMessage(role=MessageRole.USER, content=user_input))
        memory.put(ChatMessage(role=MessageRole.USER, content=user_input))

        # 🔁 Tool calling loop
        while True:
            resp = await llm.achat(messages, tools=openai_tools)

            # Append assistant message (tool_calls OR final)
            messages.append(resp.message)

            tool_calls = resp.message.additional_kwargs.get("tool_calls")
            if not tool_calls:
                break  # FINAL JSON expected

            # Execute ALL tool calls
            for call in tool_calls:
                name = call.function.name
                args_str = call.function.arguments
                
                # Parse arguments từ JSON string
                if isinstance(args_str, str):
                    args = json.loads(args_str)
                else:
                    args = args_str

                if name == "get_weather":
                    print(f"==== Calling get_weather with args: {args} ====")
                    result = get_weather(**args)
                elif name == "get_stock_price":
                    print(f"==== Calling get_stock_price with args: {args} ====")
                    result = get_stock_price(**args)
                elif name == "add_user_fact":
                    print(f"==== Calling add_user_fact with args: {args} ====")
                    result = add_user_fact(**args)
                elif name == "update_user_fact":
                    print(f"==== Calling update_user_fact with args: {args} ====")
                    result = update_user_fact(**args)
                elif name == "delete_user_fact":
                    print(f"==== Calling delete_user_fact with args: {args} ====")
                    result = delete_user_fact(**args)
                else:
                    result = "Unknown tool"

                tool_msg = ChatMessage(
                    role=MessageRole.TOOL,
                    content=result,
                    additional_kwargs={"tool_call_id": call.id}
                )

                messages.append(tool_msg)

        raw_text = resp.message.content.strip()

        print(f"\n==== Raw text: {raw_text} ====\n")

        try:
            output = RouterOutput.model_validate_json(raw_text)
        except Exception as e:
            raise ValueError(f"Invalid LLM JSON output:\n{raw_text}") from e

        if output.intent == "GENERAL":
            memory.put(
                ChatMessage(
                    role=MessageRole.ASSISTANT,
                    content=output.answer
                )
            )
        else:
            memory.put(
                ChatMessage(
                    role=MessageRole.ASSISTANT,
                    content="This is a PPTX Generation Mission"
                )
            )
        
        await ctx.store.set("chat_history", memory)

        all_messages = memory.get_all()
        truncated_messages_list = memory.get()
        
        print(f"\n===== MEMORY (BEFORE) =====\nTotal messages: {len(all_messages)}\n")
        print(f"\n===== MEMORY (AFTER) =====\nTruncated messages count: {len(truncated_messages_list)}\n")
        
        # Kiểm tra truncate bằng hash của message đầu tiên
        is_truncated = False
        is_empty_truncated = False  # Flag: truncated_messages_list rỗng
        
        # Kiểm tra trường hợp đặc biệt: all_messages có nhưng truncated_messages_list rỗng
        if all_messages and not truncated_messages_list:
            is_truncated = True
            is_empty_truncated = True
        elif all_messages and truncated_messages_list:
            # Lấy message đầu tiên từ get_all()
            first_msg_all = all_messages[0]
            first_content_all = first_msg_all.content if hasattr(first_msg_all, 'content') else str(first_msg_all)
            
            # Lấy message đầu tiên từ get()
            first_msg_truncated = truncated_messages_list[0]
            first_content_truncated = first_msg_truncated.content if hasattr(first_msg_truncated, 'content') else str(first_msg_truncated)
            
            # Tạo hash từ 20 ký tự đầu + 20 ký tự cuối
            def create_hash(content: str) -> str:
                if len(content) < 40:
                    # Nếu content ngắn hơn 40 ký tự, dùng toàn bộ
                    combined = content
                else:
                    combined = content[:20] + content[-20:]
                return hashlib.md5(combined.encode('utf-8')).hexdigest()
            
            hash_all = create_hash(first_content_all)
            hash_truncated = create_hash(first_content_truncated)
            
            # So sánh hash
            is_truncated = (hash_all != hash_truncated)
        
        if is_truncated:
            if is_empty_truncated:
                print("\nTRUNCATE STATUS: Truncated (Empty - summary all messages)\n")
            else:
                print("\nTRUNCATE STATUS: Truncated\n")
            
            # Xử lý truncate: lấy 80% để summary, giữ lại 20% (hoặc summary toàn bộ nếu is_empty_truncated)
            messages_to_summarize, messages_to_keep = _split_messages_for_summary(all_messages, is_empty_truncated)
            
            print(f"Messages to summarize: {len(messages_to_summarize)}")
            print(f"Messages to keep: {len(messages_to_keep)}")
            
            # Tạo summary
            summary_text = await _create_summary(messages_to_summarize)
            print(f"Summary created: {summary_text[:100]}...")
            
            # Tạo memory mới
            if messages_to_keep:
                # Có messages để giữ lại: tạo memory với 20% messages
                new_memory = ChatMemoryBuffer.from_defaults(token_limit=memory.token_limit)
                for msg in messages_to_keep:
                    new_memory.put(msg)
                
                # Cập nhật memory trong context
                await ctx.store.set("chat_history", new_memory)
                memory = new_memory
                
                print(f"Memory updated: {len(memory.get_all())} messages (only kept messages, no summary)\n")
                
                # Lưu lại chat history với memory mới
                _save_chat_history([{"role": msg.role.value, "content": msg.content} for msg in memory.get()])
            else:
                # Không có messages để giữ lại (is_empty_truncated): tạo memory rỗng
                new_memory = ChatMemoryBuffer.from_defaults(token_limit=memory.token_limit)
                await ctx.store.set("chat_history", new_memory)
                memory = new_memory
                
                print(f"Memory updated: 0 messages (all messages summarized, memory cleared)\n")
                
                # Lưu chat history rỗng
                _save_chat_history([])
        else:
            print("\nTRUNCATE STATUS: Not Truncated\n")
            # Lưu chat history bình thường
            _save_chat_history([{"role": msg.role.value, "content": msg.content} for msg in memory.get()])

        # 🔀 Backend routing
        if output.intent == "PPTX":
            return StopEvent(result="This is a PPTX Generation Mission")
        else:
            return StopEvent(result=output.answer)


async def main():
    workflow = RouterWorkflow()
    ctx = Context(workflow)

    result1 = await workflow.run(
        input="Tại sao yêu đơn phương lại đau?",
        ctx=ctx
    )
    print("\nResponse 1:", result1)
    
    # chat_history
    chat_history: ChatMemoryBuffer = await ctx.store.get("chat_history")
    if chat_history:
        history_messages = chat_history.get()
        print("\n" + "="*60)
        print("CHAT HISTORY:")
        print("="*60)
        for i, msg in enumerate(history_messages, 1):
            print(f"\n[{i}] {msg.role.value}:")
            print(f"    {msg.content}")
        print("="*60 + "\n")

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
