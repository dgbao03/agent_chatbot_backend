"""
Router workflow - Main workflow for routing and answering user queries.
"""
import json
from typing import Union, Optional
from llama_index.llms.openai import OpenAI
from llama_index.core.workflow import Workflow, Context, step
from llama_index.core.workflow.events import StartEvent, StopEvent
from llama_index.core.llms import ChatMessage, MessageRole
from llama_index.core.prompts import ChatPromptTemplate
from llama_index.core.memory import ChatMemoryBuffer
from llama_index.core.memory import ChatMemoryBuffer
from llama_index.core.tools import FunctionTool
from llama_index.core.workflow.events import Event

from app.config.models import RouterOutput, SlideOutput
from app.repositories.chat_repository import load_chat_history, save_message
from app.repositories.summary_repository import load_summary
from app.repositories.conversation_repository import create_new_conversation, update_conversation_title
from app.repositories.presentation_repository import (
    load_presentation,
    create_presentation,
    update_presentation,
    set_active_presentation,
)
from app.utils.formatters import format_user_facts_for_prompt
from app.utils.title_generator import generate_conversation_title
from app.tools.user_facts import add_user_fact, update_user_fact, delete_user_fact
from app.tools.weather import get_weather
from app.tools.stock import get_stock_price
from app.auth.context import get_current_user_id
from app.services.chat_service import validate_conversation_access
from app.services.presentation_service import detect_presentation_intent
from app.workflows.memory_manager import process_memory_truncation

llm = OpenAI(model="gpt-4o-mini", request_timeout=300.0)  # 5 minutes timeout cho generate multi-page slides

class StreamResponseEvent(Event):
    content: str

class GenerateSlideEvent(Event):
    user_input: str
    new_conversation_id: Optional[str] = None
    new_conversation_title: Optional[str] = None

error_output = RouterOutput(
    intent="GENERAL",
    answer="Sorry, I encountered an error processing your request. Please try again.",
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

class RouterWorkflow(Workflow):

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
        
        # Validate required params
        if not user_id or user_id == "None":
            raise ValueError("user_id is missing or invalid. Authentication failed.")
        
        # Variables to track new conversation (if created)
        new_conv_id: Optional[str] = None
        new_conv_title: Optional[str] = None
        
        # Check if conversation_id is null/empty (new conversation)
        is_new_conversation = not conversation_id or conversation_id == "null" or conversation_id == ""
        
        if is_new_conversation:
            # Create new conversation
            conversation_id = create_new_conversation(user_id)
            new_conv_id = conversation_id
            
            # Generate title from user input
            try:
                title = generate_conversation_title(user_input)
                update_conversation_title(conversation_id, title)
                new_conv_title = title
            except Exception as e:
                # Fallback: use truncated user input
                title = user_input[:60].strip()
                if len(user_input) > 60:
                    title += "..."
                update_conversation_title(conversation_id, title)
                new_conv_title = title
        else:
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
            summary_text = (
                "\n===== CONVERSATION SUMMARY =====\n"
                f"{summary_data['summary_content']}"
            )
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
            role="user",
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
                    result = get_weather(**args)
                elif name == "get_stock_price":
                    result = get_stock_price(**args)
                elif name == "add_user_fact":
                    result = add_user_fact(**args)
                elif name == "update_user_fact":
                    result = update_user_fact(**args)
                elif name == "delete_user_fact":
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

        try:
            output = RouterOutput.model_validate_json(raw_text)
        except Exception as e:
            # raise ValueError(f"Invalid LLM JSON output:\n{raw_text}") from e
            return StopEvent(result=error_output.model_dump())

        if output.intent == "GENERAL":
            # Save ASSISTANT message to DB first and get ID
            assistant_msg_id = save_message(
                conversation_id=conversation_id,
                role="assistant",
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

        # Prepare result
        result = output.model_dump()
        
        # Add conversation_id and title if new conversation was created
        if new_conv_id:
            result["conversation_id"] = new_conv_id
            result["title"] = new_conv_title
        
        # 🔀 Backend routing
        if output.intent == "GENERAL":
            return StopEvent(result=result)
        elif output.intent == "PPTX":
            # Run generate_slide step (same workflow)
            return GenerateSlideEvent(
                user_input=user_input,
                new_conversation_id=new_conv_id,
                new_conversation_title=new_conv_title
            )
        else:
            return StopEvent(result=error_output.model_dump())

    @step
    async def generate_slide(self, ctx: Context, ev: GenerateSlideEvent) -> StopEvent:
        """Slide generation step (merged from SlideWorkflow)."""
        conversation_id = await ctx.store.get("conversation_id")
        memory: ChatMemoryBuffer = await ctx.store.get("chat_history")
        history = memory.get() if memory else []

        try:
            action, target_presentation_id, target_page_number = await detect_presentation_intent(
                ev.user_input, conversation_id, llm
            )
        except Exception:
            return StopEvent(result=error_output.model_dump())

        previous_pages = None
        total_pages = None
        if target_presentation_id:
            presentation_data = load_presentation(target_presentation_id)
            if presentation_data:
                previous_pages = presentation_data.get("pages")
                total_pages = presentation_data.get("total_pages")

        system_content = (
            "You are an expert HTML slide designer. Your task is to create a beautiful, professional HTML slide presentation.\n\n"
            "REQUIREMENTS:\n"
            "- MUST: Each slide dimensions: 1280 x 720 pixels (width x height), no border radius in the corners\n"
            "- Generate MULTIPLE slides (3-7 slides depending on topic complexity)\n"
            "- Each HTML slide must be complete and valid, ready to render in browser\n"
            "- Use modern, clean design with good typography\n"
            "- Make it visually appealing with appropriate colors and spacing\n"
            "- Include CSS styles inline or in <style> tag within each slide\n"
            "- Content should be clear, well-organized, and easy to read\n\n"
            "SLIDE STRUCTURE:\n"
            "- Slide 1: Introduction/Title slide (topic overview, eye-catching design)\n"
            "- Slides 2-N: Content slides (main points, explanations, examples)\n"
            "- Last Slide: Conclusion/Summary (key takeaways, closing thoughts)\n"
            "- Each slide should have a clear page_title describing its purpose\n\n"
            "DESIGN GUIDELINES:\n"
            "- Use a clean layout with proper margins and padding\n"
            "- Choose a professional color scheme consistent across all slides\n"
            "- Use appropriate font sizes for headings and body text\n"
            "- Ensure text is readable and well-contrasted\n"
            "- Add visual elements like gradients, shadows, or borders if appropriate\n"
            "- Keep the design simple but elegant\n"
            "- Maintain visual consistency across all slides\n\n"
            "OUTPUT REQUIREMENTS:\n"
            "- You MUST return a list of PageContent objects in the 'pages' field\n"
            "- Each PageContent must have: page_number (starting from 1), html_content (complete HTML), and page_title\n"
            "- You MUST provide the 'total_pages' count\n"
            "- You MUST provide a clear 'topic' for the presentation\n"
            "- You MUST provide an 'answer' telling the user about the slide creation\n\n"
        )

        if history:
            history_text = "\n===== RECENT CHAT HISTORY =====\n"
            for msg in history:
                history_text += f"{msg.role.value}: {msg.content}\n"
            system_content += "\n\n" + history_text

        summary_data = load_summary(conversation_id)
        if summary_data.get("summary_content"):
            summary_text = (
                "\n===== CONVERSATION SUMMARY =====\n"
                f"{summary_data['summary_content']}"
            )
            system_content += summary_text

        if previous_pages:
            if target_page_number is not None:
                target_page = next((p for p in previous_pages if p.page_number == target_page_number), None)
                if target_page:
                    system_content += f"\n\n===== PREVIOUS SLIDE - Page {target_page_number} (TARGET PAGE TO EDIT) =====\n"
                    system_content += f"Page Title: {target_page.page_title or 'No title'}\n"
                    system_content += f"HTML Content:\n{target_page.html_content}\n\n"
                    system_content += (
                        "INSTRUCTIONS FOR EDITING SPECIFIC PAGE:\n"
                        f"- Edit ONLY Page {target_page_number}\n"
                        "- Keep the same page_number\n"
                        "- Modify html_content according to user request\n"
                        "- Output should contain ONLY this page (not other pages)\n"
                        "- Backend will merge this with other unchanged pages\n\n"
                    )
                else:
                    target_page_number = None

            if target_page_number is None:
                system_content += f"\n\n===== PREVIOUS SLIDE - All {total_pages} Pages (for reference) =====\n"
                for page in previous_pages:
                    system_content += f"\n--- Page {page.page_number}: {page.page_title or 'No title'} ---\n"
                    system_content += f"{page.html_content}\n"
                system_content += "\n"
                system_content += (
                    "INSTRUCTIONS FOR EDITING ENTIRE PRESENTATION:\n"
                    "- You can add, remove, or modify any pages\n"
                    "- Return complete new presentation (all pages)\n"
                    "- Maintain consistent design across all pages\n"
                    "- Preserve good elements unless explicitly asked to change\n\n"
                )

        if action == "CREATE_NEW":
            system_content += "\n\nCreate a NEW HTML slide presentation based on the user's request below."
        elif target_page_number is not None:
            system_content += f"\n\nEDIT Page {target_page_number} based on the user's request below."
        else:
            system_content += "\n\nEDIT the entire presentation based on the user's request below."

        messages = [
            ChatMessage(role=MessageRole.SYSTEM, content=system_content),
        ]
        messages.append(ChatMessage(role=MessageRole.USER, content=f"User Request: {ev.user_input}"))
        prompt_messages = [(msg.role, msg.content) for msg in messages]
        prompt = ChatPromptTemplate.from_messages(prompt_messages)

        slide_output = await llm.astructured_predict(SlideOutput, prompt)

        if target_page_number is not None and previous_pages:
            if len(slide_output.pages) == 1:
                new_page = slide_output.pages[0]
                merged_pages = []
                for old_page in previous_pages:
                    if old_page.page_number == target_page_number:
                        merged_pages.append(new_page)
                    else:
                        merged_pages.append(old_page)
                slide_output.pages = merged_pages
                slide_output.total_pages = len(merged_pages)

        try:
            if action == "CREATE_NEW":
                presentation_id = create_presentation(
                    conversation_id=conversation_id,
                    topic=slide_output.topic,
                    pages=slide_output.pages,
                    total_pages=slide_output.total_pages,
                    user_request=ev.user_input,
                )
                if not presentation_id:
                    raise ValueError("Failed to create presentation")
            else:
                if not target_presentation_id:
                    raise ValueError("target_presentation_id required for EDIT action")
                new_version = update_presentation(
                    presentation_id=target_presentation_id,
                    topic=slide_output.topic,
                    pages=slide_output.pages,
                    total_pages=slide_output.total_pages,
                    user_request=ev.user_input,
                )
                if not new_version:
                    raise ValueError("Failed to update presentation")
                presentation_id = target_presentation_id
                set_active_presentation(conversation_id, presentation_id)
        except (ValueError, Exception):
            return StopEvent(result=error_output.model_dump())

        try:
            assistant_msg_id = save_message(
                conversation_id=conversation_id,
                role="assistant",
                content=slide_output.answer,
                intent="PPTX",
                metadata={
                    "pages": [p.model_dump() for p in slide_output.pages],
                    "total_pages": slide_output.total_pages,
                    "topic": slide_output.topic,
                    "slide_id": presentation_id,
                },
            )
        except Exception:
            assistant_msg_id = None

        if memory:
            memory.put(
                ChatMessage(
                    role=MessageRole.ASSISTANT,
                    content=slide_output.answer,
                    additional_kwargs={"message_id": assistant_msg_id},
                )
            )
        await ctx.store.set("chat_history", memory)
        await process_memory_truncation(ctx, memory)

        result = slide_output.model_dump()
        if ev.new_conversation_id:
            result["conversation_id"] = ev.new_conversation_id
            result["title"] = ev.new_conversation_title

        return StopEvent(result=result)

