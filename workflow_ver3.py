from pydantic import BaseModel, Field
from typing import Literal, Optional
import json
import os
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
        user_input = ev.input

        openai_tools = [tool.metadata.to_openai_tool() for tool in tools]

        # Memory
        memory: ChatMemoryBuffer = await ctx.store.get("chat_history")
        if memory is None:
            memory = ChatMemoryBuffer.from_defaults(token_limit=2000)
            await ctx.store.set("chat_history", memory)

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

        messages = [
            ChatMessage(
                role=MessageRole.SYSTEM,
                content=system_content
            )
        ]

        if history:
            messages.extend(history)

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

        await ctx.store.set("chat_history", memory)

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

         # Log messages với format dễ đọc
        print("\n" + "="*60)
        print("MESSAGES:")
        print("="*60)
        for i, msg in enumerate(messages, 1):
            print(f"\n[{i}] {msg.role.value}:")
            if msg.content:
                # Truncate nếu quá dài
                content = msg.content
                if len(content) > 500:
                    content = content[:500] + "... [truncated]"
                print(f"    Content: {content}")
            if msg.additional_kwargs:
                tool_calls = msg.additional_kwargs.get("tool_calls")
                tool_call_id = msg.additional_kwargs.get("tool_call_id")
                if tool_calls:
                    print(f"    Tool Calls: {len(tool_calls)} call(s)")
                    for j, call in enumerate(tool_calls, 1):
                        print(f"      [{j}] {call.function.name}({call.function.arguments})")
                elif tool_call_id:
                    print(f"    Tool Call ID: {tool_call_id}")
        print("="*60 + "\n")

        # 🔀 Backend routing
        if output.intent == "PPTX":
            return StopEvent(result="This is a PPTX Generation Mission")
        else:
            return StopEvent(result=output.answer)


async def main():
    workflow = RouterWorkflow()
    ctx = Context(workflow)

    # Khởi tạo memory và set vào context
    memory = ChatMemoryBuffer.from_defaults(token_limit=10000)
    await ctx.store.set("chat_history", memory)

    # GENERAL
    # result1 = await workflow.run(
    #     input="Bạn có biết tên tôi là gì không?",
    #     ctx=ctx
    # )
    # print("\nResponse 1:", result1)

    result2 = await workflow.run(
        input="Tôi tên là gì? và đang sống ở đâu?",
        ctx=ctx
    )
    print("\nResponse 2:", result2)
    
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
