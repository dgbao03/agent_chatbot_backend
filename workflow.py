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
from memory_helper_functions.chat_history import _load_chat_history, _save_chat_history, _save_message
from memory_helper_functions.chat_summary import _load_chat_summary, _create_summary, _split_messages_for_summary, _mark_messages_as_summarized
from memory_helper_functions.user_facts import _format_user_facts_for_prompt
from memory_helper_functions.presentation_storage import (
    _detect_intent,
    _create_presentation,
    _update_presentation,
    _load_presentation,
    _get_active_presentation,
    _set_active_presentation
)
from tools.user_facts import add_user_fact, update_user_fact, delete_user_fact
from tools.weather import get_weather
from tools.stock import get_stock_price
from config.workflow_context import set_current_user_id, get_current_user_id
from config.supabase_client import get_supabase_client

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

class RouterWorkflow(Workflow):

    async def _process_memory_and_truncate(self, ctx: Context, memory: ChatMemoryBuffer) -> None:
        """
        Xử lý memory truncation và summary.
        
        Args:
            ctx: Workflow context
            memory: ChatMemoryBuffer cần xử lý
        """
        # Get conversation_id from context
        conversation_id = await ctx.store.get("conversation_id")
        
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
            summary_text = await _create_summary(conversation_id, messages_to_summarize)
            print(f"Summary created: {summary_text[:100]}...")
            
            # Mark messages as summarized in DB (set is_in_working_memory = FALSE)
            message_ids_to_summarize = []
            for msg in messages_to_summarize:
                msg_id = msg.additional_kwargs.get("message_id")
                if msg_id:
                    message_ids_to_summarize.append(msg_id)
            
            if message_ids_to_summarize:
                _mark_messages_as_summarized(message_ids_to_summarize)
                print(f"✅ Marked {len(message_ids_to_summarize)} messages as summarized (is_in_working_memory = FALSE)")
            else:
                print("⚠️ No message IDs found to mark as summarized")
            
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
                
                # Messages are now saved individually to Supabase, no need to save entire history
                # _save_chat_history is deprecated
            else:
                # Không có messages để giữ lại (is_empty_truncated): tạo memory rỗng
                new_memory = ChatMemoryBuffer.from_defaults(token_limit=memory.token_limit)
                await ctx.store.set("chat_history", new_memory)
                memory = new_memory
                
                print(f"Memory updated: 0 messages (all messages summarized, memory cleared)\n")
                
                # Messages are now saved individually to Supabase, no need to save entire history
                # _save_chat_history is deprecated
        else:
            print("\nTRUNCATE STATUS: Not Truncated\n")
            # Messages are now saved individually to Supabase, no need to save entire history
            # _save_chat_history is deprecated

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
        try:
            supabase = get_supabase_client()
            conversation_response = supabase.from_('conversations').select('user_id').eq('id', conversation_id).single().execute()
            
            if not conversation_response.data:
                raise ValueError(f"Conversation {conversation_id} not found.")
            
            conversation_owner_id = conversation_response.data.get('user_id')
            if conversation_owner_id != user_id:
                raise ValueError(f"Access denied: You can only access your own conversations. This conversation belongs to user {conversation_owner_id}.")
            
            print(f"✅ Conversation ownership validated: user_id={user_id}, conversation_id={conversation_id}")
        except Exception as e:
            print(f"❌ Conversation ownership validation failed: {e}")
            raise ValueError(f"Access denied: {str(e)}")

        # Store user_id and conversation_id in context for later use
        await ctx.store.set("user_id", user_id)
        await ctx.store.set("conversation_id", conversation_id)

        openai_tools = [tool.metadata.to_openai_tool() for tool in tools]

        # Load chat history for this conversation
        chat_history = _load_chat_history(conversation_id)

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
        user_facts_text = _format_user_facts_for_prompt(user_id)
        
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
        summary_data = _load_chat_summary(conversation_id)
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
        
        # Save USER message to DB first and get ID
        user_msg_id = _save_message(
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
            assistant_msg_id = _save_message(
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
        # Lấy conversation_id từ context
        conversation_id = await ctx.store.get("conversation_id")
        
        # Lấy memory từ context
        memory: ChatMemoryBuffer = await ctx.store.get("chat_history")
        history = memory.get() if memory else []
        
        # Detect intent (now uses Supabase)
        try:
            action, target_presentation_id, target_page_number = await _detect_intent(ev.user_input, conversation_id, llm)
        except Exception as e:
            print(f"❌ Intent detection error: {e}")
            return StopEvent(result=error_output.model_dump())
        print(f"Slide Output:\naction: {action}, target_presentation_id: {target_presentation_id}, target_page_number: {target_page_number}")
        
        # Load previous presentation data nếu EDIT
        previous_pages = None
        total_pages = None
        if target_presentation_id:
            presentation_data = _load_presentation(target_presentation_id)
            if presentation_data:
                previous_pages = presentation_data['pages']
                total_pages = presentation_data['total_pages']
        
        # Tạo System Prompt content
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
        
        # Format history vào System Prompt nếu có
        if history:
            history_text = "\n===== RECENT CHAT HISTORY =====\n"
            for msg in history:
                history_text += f"{msg.role.value}: {msg.content}\n"
            system_content += "\n\n" + history_text
        
        # Load và thêm chat summary nếu có (sau Chat History)
        summary_data = _load_chat_summary(conversation_id)
        if summary_data["version"] > 0 and summary_data["summary_content"]:
            summary_text = f"\n===== CONVERSATION SUMMARY =====\n{summary_data['summary_content']}"
            system_content += summary_text
        
        # Thêm previous slide pages nếu EDIT
        if previous_pages:
            if target_page_number is not None:
                # EDIT SPECIFIC PAGE
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
                    # Page number không tồn tại, fallback to edit all
                    target_page_number = None
            
            if target_page_number is None:
                # EDIT ALL PAGES
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
        
        # Merge logic nếu EDIT SPECIFIC PAGE
        if target_page_number is not None and previous_pages:
            # LLM trả về 1 page mới
            if len(slide_output.pages) == 1:
                new_page = slide_output.pages[0]
                
                # Merge vào previous_pages
                merged_pages = []
                for old_page in previous_pages:
                    if old_page.page_number == target_page_number:
                        # Replace page cũ bằng page mới
                        merged_pages.append(new_page)
                    else:
                        # Giữ nguyên page cũ
                        merged_pages.append(old_page)
                
                # Update slide_output với merged pages
                slide_output.pages = merged_pages
                slide_output.total_pages = len(merged_pages)
                print(f"✅ Merged: Replaced page {target_page_number}, total {len(merged_pages)} pages")
            else:
                print(f"⚠️ LLM returned {len(slide_output.pages)} pages for EDIT_SPECIFIC_PAGE, expected 1. Using LLM output as-is.")
        
        # Save presentation result (to Supabase)
        try:
            if action == "CREATE_NEW":
                # Create new presentation (automatically sets as active)
                presentation_id = _create_presentation(
                    conversation_id=conversation_id,
                    topic=slide_output.topic,
                    pages=slide_output.pages,
                    total_pages=slide_output.total_pages,
                    user_request=ev.user_input
                )
                if not presentation_id:
                    raise ValueError("Failed to create presentation")
                
                print(f"✅ Created and set as active: {presentation_id}")
            else:
                # Update existing presentation
                if not target_presentation_id:
                    raise ValueError("target_presentation_id required for EDIT action")
                
                new_version = _update_presentation(
                    presentation_id=target_presentation_id,
                    topic=slide_output.topic,
                    pages=slide_output.pages,
                    total_pages=slide_output.total_pages,
                    user_request=ev.user_input
            )
                if not new_version:
                    raise ValueError("Failed to update presentation")
                
                presentation_id = target_presentation_id
                
                # Update active_presentation_id (user is working with this presentation)
                _set_active_presentation(conversation_id, presentation_id)
                print(f"✅ Updated active_presentation_id: {presentation_id}")
                
        except (ValueError, Exception) as e:
            print(f"❌ Failed to save presentation: {e}")
            return StopEvent(result=error_output.model_dump())
        
        # Save assistant message to database
        print(f"\n=== SAVING ASSISTANT MESSAGE (PPTX) ===")
        print(f"Conversation ID: {conversation_id}")
        print(f"Answer: {slide_output.answer[:100]}...")
        print(f"Presentation ID: {presentation_id}")
        
        try:
            assistant_msg_id = _save_message(
                conversation_id=conversation_id,
                role='assistant',
                content=slide_output.answer,
                intent='PPTX',
                metadata={
                    'pages': [p.model_dump() for p in slide_output.pages],
                    'total_pages': slide_output.total_pages,
                    'topic': slide_output.topic,
                    'slide_id': presentation_id
                }
            )
            
            if assistant_msg_id:
                print(f"✅ Saved assistant message: {assistant_msg_id}")
            else:
                print(f"❌ Failed to save assistant message (returned None)!")
        except Exception as e:
            print(f"❌ Exception saving assistant message: {e}")
            assistant_msg_id = None
        
        print(f"========================================\n")
        
        # Append answer vào memory with message_id
        if memory:
            memory.put(
                ChatMessage(
                    role=MessageRole.ASSISTANT,
                    content=slide_output.answer,
                    additional_kwargs={"message_id": assistant_msg_id}
                )
            )
        
        await ctx.store.set("chat_history", memory)

            # Xử lý memory truncation và summary
        await self._process_memory_and_truncate(ctx, memory)

        print(messages)
            
        return StopEvent(result=slide_output.model_dump())

