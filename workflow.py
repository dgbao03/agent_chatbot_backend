import json
import hashlib
from typing import Union
from dotenv import load_dotenv
load_dotenv()

import asyncio
from llama_index.llms.openai import OpenAI
from llama_index.core.workflow import Workflow, Context, step
from llama_index.core.workflow.events import StartEvent, StopEvent
from llama_index.core.llms import ChatMessage, MessageRole
from llama_index.core.prompts import ChatPromptTemplate
from llama_index.core.memory import ChatMemoryBuffer
from llama_index.core.tools import FunctionTool
from llama_index.core.workflow.events import Event

# Import từ các module mới
from config.models import RouterOutput, SlideOutput
from memory_helper_functions.chat_history import _load_chat_history, _save_chat_history
from memory_helper_functions.chat_summary import _load_chat_summary, _create_summary, _split_messages_for_summary
from memory_helper_functions.user_facts import _format_user_facts_for_prompt
from tools.user_facts import add_user_fact, update_user_fact, delete_user_fact
from tools.weather import get_weather
from tools.stock import get_stock_price

llm = OpenAI(model="gpt-4o-mini")

class StreamResponseEvent(Event):
    content: str
class GenerateSlideEvent(Event):
    user_input: str

error_output = RouterOutput(
    intent="GENERAL",
    answer="Sorry, I encountered an error processing your request. Please try again."
)

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

    async def _process_memory_and_truncate(self, ctx: Context, memory: ChatMemoryBuffer) -> None:
        """
        Xử lý memory truncation và summary.
        
        Args:
            ctx: Workflow context
            memory: ChatMemoryBuffer cần xử lý
        """
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

    @step
    async def route_and_answer(self, ctx: Context, ev: StartEvent) -> Union[StopEvent, "GenerateSlideEvent"]:

        # Dùng khi chạy trực tiếp với hàm main()
        # user_input = ev.input

        # Dùng khi chạy WorkflowServer
        user_input = ev.user_input

        openai_tools = [tool.metadata.to_openai_tool() for tool in tools]

        chat_history = _load_chat_history()

        # Memory
        memory = ChatMemoryBuffer.from_defaults(token_limit=3000)
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
            "- If intent is GENERAL → answer MUST be provided, answer must be in String format, always return a response, cannot be none or null, ...\n"
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
            # raise ValueError(f"Invalid LLM JSON output:\n{raw_text}") from e
            print(f"ERROR: Invalid JSON output:\n{raw_text}\nException: {e}")
            
            return StopEvent(result=error_output.model_dump())

        if output.intent == "GENERAL":
            memory.put(
                ChatMessage(
                    role=MessageRole.ASSISTANT,
                    content=output.answer
                )
            )
        
        await ctx.store.set("chat_history", memory)

        # Xử lý memory truncation và summary cho GENERAL case
        if output.intent == "GENERAL":
            await self._process_memory_and_truncate(ctx, memory)

        # 🔀 Backend routing
        if output.intent == "GENERAL":
            return StopEvent(result=output.model_dump())
        elif output.intent == "PPTX":
            # Running Generate Slide Step (Step 2)
            return GenerateSlideEvent(user_input=user_input)
        else:
            return StopEvent(result=error_output.model_dump())
    
    @step
    async def generate_slide(self, ctx: Context, ev: GenerateSlideEvent) -> StopEvent:
        # Lấy memory từ context
        memory: ChatMemoryBuffer = await ctx.store.get("chat_history")
        history = memory.get() if memory else []
        
        # Tạo System Prompt content
        system_content = (
            "You are an expert HTML slide designer. Your task is to create a beautiful, professional HTML slide presentation.\n\n"
            "REQUIREMENTS:\n"
            "- MUST: Slide dimensions: 1280 x 720 pixels (width x height), no border radius in the corners\n"
            "- Create a single slide only\n"
            "- HTML must be complete and valid, ready to render in browser\n"
            "- Use modern, clean design with good typography\n"
            "- Make it visually appealing with appropriate colors and spacing\n"
            "- Include CSS styles inline or in <style> tag\n"
            "- Content should be clear, well-organized, and easy to read\n\n"
            "GUIDELINES:\n"
            "- Use a clean layout with proper margins and padding\n"
            "- Choose a professional color scheme\n"
            "- Use appropriate font sizes for headings and body text\n"
            "- Ensure text is readable and well-contrasted\n"
            "- Add visual elements like gradients, shadows, or borders if appropriate\n"
            "- Keep the design simple but elegant\n\n"
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
        
        system_content += "\n\nCreate an HTML slide based on the user's request below."
        
        messages = [
            ChatMessage(
                role=MessageRole.SYSTEM,
                content=system_content
            )
        ]
        
        user_content = f"User Request: {ev.user_input}"
        messages.append(ChatMessage(role=MessageRole.USER, content=user_content))
        
        prompt_messages = [
            (msg.role, msg.content) for msg in messages
        ]
        prompt = ChatPromptTemplate.from_messages(prompt_messages)
        
        # Call LLM với astructured_predict (async version)
        slide_output = await llm.astructured_predict(
            SlideOutput,
            prompt
        )
        
        # Append answer vào memory
        if memory:
            # Append assistant message với answer
            memory.put(
                ChatMessage(
                    role=MessageRole.ASSISTANT,
                    content=slide_output.answer
                )
            )
            
            await ctx.store.set("chat_history", memory)
            
            # Xử lý memory truncation và summary
            await self._process_memory_and_truncate(ctx, memory)
        
        return StopEvent(result=slide_output.model_dump())

