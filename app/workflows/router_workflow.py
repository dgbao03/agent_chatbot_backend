"""
Router workflow - Main workflow for routing and answering user queries.
"""
import json
from typing import Union
from llama_index.llms.openai import OpenAI
from llama_index.core.workflow import Workflow, Context, step
from llama_index.core.workflow.events import StartEvent, StopEvent
from llama_index.core.llms import ChatMessage, MessageRole
from llama_index.core.prompts import ChatPromptTemplate
from llama_index.core.memory import ChatMemoryBuffer
from llama_index.core.tools import FunctionTool
from llama_index.core.workflow.events import Event

from app.config.models import RouterOutput
from app.repositories.chat_repository import load_chat_history, save_message
from app.repositories.summary_repository import load_summary
from app.utils.formatters import format_user_facts_for_prompt
from app.tools.user_facts import add_user_fact, update_user_fact, delete_user_fact
from app.tools.weather import get_weather
from app.tools.stock import get_stock_price
from app.config.workflow_context import get_current_user_id
from app.services.chat_service import validate_conversation_access
from app.workflows.memory_manager import process_memory_truncation

llm = OpenAI(model="gpt-4o-mini", request_timeout=300.0)  # 5 minutes timeout cho generate multi-page slides

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
        description="""
        Lấy thông tin thời tiết theo thành phố. Input: Tên thành phố. 
        Lưu ý: Chỉ sử dụng khi User yêu cầu thông tin thời tiết về thành phố.
        Không sử dụng khi trong Request có tên thành phố/địa danh nhưng không yêu cầu thông tin thời tiết."""
    ), 
    FunctionTool.from_defaults(
        fn=get_stock_price,
        name="get_stock_price",
        description="""
        Lấy thông tin giá cổ phiếu theo mã cổ phiếu. Input: Mã cổ phiếu.
        Lưu ý: Chỉ sử dụng khi User yêu cầu thông tin giá cổ phiếu của một công ty cụ thể.
        Không sử dụng khi trong Request có mã cổ phiếu/địa danh/tên công ty nhưng không yêu cầu thông tin giá cổ phiếu."""
    ),
    FunctionTool.from_defaults(
        fn=add_user_fact,
        name="add_user_fact",
        description="""
        Định nghĩa User Fact: Các thông tin quan trọng/cá nhân về User cần ghi nhớ.
        Sử dụng hàm khi thêm User Fact. 
        Lưu ý: Chỉ sử dụng khi người dùng yêu cầu nhớ thông tin của họ. Không tự ý dùng hàm này.
        Khi người dùng yêu cầu thêm thông tin, ví dụ: 'Lưu lại rằng tôi tên là Bao Do', 'Nhớ rằng tôi sống ở Hà Nội'. 
        Các thông tin sẽ được lưu dưới dạng key-value (ví dụ: 'name': 'Bao Do', 'location': 'Hà Nội')."""
    ),
    FunctionTool.from_defaults(
        fn=update_user_fact,
        name="update_user_fact",
        description="""
        Sử dụng hàm khi cập nhật User Fact theo key.
        Lưu ý: Chỉ sử dụng khi người dùng yêu cầu cập nhật thông tin của họ. Không tự ý dùng hàm này.
        Nếu key không tồn tại, công cụ sẽ báo lỗi. 
        Ví dụ: khi người dùng yêu cầu sửa đổi 'tuổi tôi là 30' hoặc 'tên tôi là Bao Do', công cụ sẽ cập nhật thông tin tương ứng. 
        Nếu key không có, sẽ trả về lỗi như 'Key không tồn tại'."""
    ),
    FunctionTool.from_defaults(
        fn=delete_user_fact,
        name="delete_user_fact",
        description="""
        Sử dụng hàm khi xóa User Fact theo key.
        Lưu ý: Chỉ sử dụng khi người dùng yêu cầu xóa thông tin của họ. Không tự ý dùng hàm này.
        Ví dụ: nếu người dùng yêu cầu 'Xóa tên tôi' hoặc 'Xóa tuổi tôi', công cụ sẽ xóa key tương ứng. 
        Nếu không tìm thấy key, trả về lỗi như 'Không tìm thấy thông tin'."""
    )
]

# Import SlideWorkflow after GenerateSlideEvent is defined to avoid circular import
from app.workflows.slide_workflow import SlideWorkflow

class RouterWorkflow(Workflow, SlideWorkflow):

    @step
    async def route_and_answer(self, ctx: Context, ev: StartEvent) -> Union[StopEvent, "GenerateSlideEvent"]:

        # Dùng khi chạy trực tiếp với hàm main()
        # user_input = ev.input

        # Dùng khi chạy WorkflowServer - Get params from StartEvent
        # Access as dict since StartEvent can have dynamic fields from request body
        user_input = ev.get("user_input")
        conversation_id = ev.get("conversation_id")  # From frontend
        
        # Get user_id from context var (set by Auth middleware)
        user_id = get_current_user_id()
        
        # Debug log
        print(f"\n=== WORKFLOW DEBUG ===")
        print(f"user_input: {user_input}")
        print(f"user_id (from context): {user_id} (type: {type(user_id)})")
        print(f"conversation_id: {conversation_id}")
        print(f"======================\n")

        # Validate required params
        if not user_id or user_id == "None":
            raise ValueError("user_id is missing or invalid. Authentication failed.")
        if not conversation_id:
            raise ValueError("conversation_id is required.")

        # ✅ Validate conversation ownership (fail early before processing)
        validate_conversation_access(user_id, conversation_id)

        # Store user_id and conversation_id in context for later use
        await ctx.store.set("user_id", user_id)
        await ctx.store.set("conversation_id", conversation_id)

        openai_tools = [tool.metadata.to_openai_tool() for tool in tools]

        # Load chat history for this conversation
        chat_history = load_chat_history(conversation_id)

        # Memory
        memory = ChatMemoryBuffer.from_defaults(token_limit=200)
        await ctx.store.set("chat_history", memory)

        for chat in chat_history:
            memory.put(ChatMessage(
                role=chat["role"], 
                content=chat["content"],
                additional_kwargs={"message_id": chat.get("id")}  # Store ID in additional_kwargs
            ))

        history = memory.get()

        # Load và format user facts để thêm vào System Prompt
        user_facts_text = format_user_facts_for_prompt(user_id)
        
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
            "- If user wants to EDIT/MODIFY/CHANGE existing slides → intent = PPTX\n"
            "- If user asks about slides that were created before → intent = PPTX\n"
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
        summary_data = load_summary(conversation_id)
        if summary_data.get("summary_content"):
            summary_text = f"\n===== CONVERSATION SUMMARY =====\n{summary_data['summary_content']}"
            system_content += summary_text

        messages = [
            ChatMessage(
                role=MessageRole.SYSTEM,
                content=system_content
            )
        ]

        messages.append(ChatMessage(role=MessageRole.USER, content=user_input))
        
        # Save USER message to DB first and get ID
        user_msg_id = save_message(
            conversation_id=conversation_id,
            role='user',
            content=user_input,
            intent=None,
            metadata={}
        )
        
        # Put into memory with ID from DB
        memory.put(ChatMessage(
            role=MessageRole.USER, 
            content=user_input,
            additional_kwargs={"message_id": user_msg_id}
        ))

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
            # Save ASSISTANT message to DB first and get ID
            assistant_msg_id = save_message(
                conversation_id=conversation_id,
                role='assistant',
                content=output.answer,
                intent=output.intent,
                metadata={}
            )
            
            # Put into memory with ID from DB
            memory.put(
                ChatMessage(
                    role=MessageRole.ASSISTANT,
                    content=output.answer,
                    additional_kwargs={"message_id": assistant_msg_id}
                )
            )
        
        await ctx.store.set("chat_history", memory)

        # Xử lý memory truncation và summary cho GENERAL case
        if output.intent == "GENERAL":
            await process_memory_truncation(ctx, memory)
        
        print(messages)

        # 🔀 Backend routing
        if output.intent == "GENERAL":
            return StopEvent(result=output.model_dump())
        elif output.intent == "PPTX":
            # Running Generate Slide Step (Step 2)
            return GenerateSlideEvent(user_input=user_input)
        else:
            return StopEvent(result=error_output.model_dump())

