"""
Chat workflow - Main workflow for routing and answering user queries.
"""
import json
from typing import Union, Optional
from llama_index.llms.openai import OpenAI
from llama_index.core.workflow import Workflow, Context, step
from llama_index.core.workflow.events import StartEvent, StopEvent
from llama_index.core.llms import ChatMessage, MessageRole
from llama_index.core.prompts import ChatPromptTemplate
from llama_index.core.memory import ChatMemoryBuffer
from llama_index.core.workflow.events import Event

from app.config.pydantic_outputs import RouterOutput, SlideOutput, SecurityOutput
from app.config.types import Message, Presentation
from app.config.prompts import (
    SECURITY_CHECK_PROMPT,
    ROUTER_ANSWER_PROMPT,
    SLIDE_GENERATION_PROMPT,
    TOOL_BEST_PRACTICES,
)
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
from app.utils.helpers import save_error_response
from app.tools import registry
from app.auth.context import get_current_user_id, get_current_db_session
from app.services.chat_service import validate_conversation_access
from app.services.presentation_service import detect_presentation_intent
from app.workflows.memory_manager import process_memory_truncation

llm = OpenAI(model="gpt-4o-mini", request_timeout=300.0)  # 5 minutes timeout cho generate multi-page slides
llm_security = OpenAI(model="gpt-3.5-turbo", temperature=0, request_timeout=30.0)  # Fast LLM for security check

class StreamResponseEvent(Event):
    content: str

class BusinessRouterEvent(Event):
    """Event to pass control from security_check to route_and_answer."""
    user_input: str
    conversation_id: Optional[str] = None

class GenerateSlideEvent(Event):
    user_input: str
    new_conversation_id: Optional[str] = None
    new_conversation_title: Optional[str] = None

error_output = RouterOutput(
    intent="GENERAL",
    answer="Sorry, I encountered an error processing your request. Please try again.",
)

# Get all enabled tools from registry
tools = registry.get_llama_tools()

class ChatWorkflow(Workflow):

    @step
    async def security_check(self, ctx: Context, ev: StartEvent) -> Union[StopEvent, BusinessRouterEvent]:
        """
        Step 1: Security layer - Check for system exploitation attempts.
        Returns StopEvent with rejection if EXPLOIT, otherwise continues to route_and_answer.
        """
        user_input = ev.get("user_input")
        conversation_id = ev.get("conversation_id")
        
        # Get db session from ContextVar (set by workflow router)
        db = get_current_db_session()
        
        # Store db in context for other steps
        await ctx.store.set("db", db)
        
        # Security check system prompt
        system_prompt = SECURITY_CHECK_PROMPT

        try:
            # Call LLM for security classification
            result = await llm_security.astructured_predict(
                SecurityOutput,
                ChatPromptTemplate.from_messages([
                    ("system", system_prompt),
                    ("user", user_input)
                ])
            )
            
            if result.classification == "EXPLOIT":
                # Get user_id from context
                user_id = get_current_user_id()
                
                if not user_id or user_id == "None":
                    raise ValueError("user_id is missing or invalid. Authentication failed.")
                
                # Variables to track if new conversation was created
                new_conv_id: Optional[str] = None
                new_conv_title: Optional[str] = None
                
                # Check if conversation_id is null/empty (new conversation)
                is_new_conversation = not conversation_id or conversation_id == "null" or conversation_id == ""
                
                if is_new_conversation:
                    # Create new conversation
                    conversation_id = create_new_conversation(user_id, db)
                    new_conv_id = conversation_id
                    
                    # Generate title from user input
                    try:
                        title = generate_conversation_title(user_input)
                        update_conversation_title(conversation_id, title, db)
                        new_conv_title = title
                    except Exception as e:
                        # Fallback: use truncated user input
                        title = user_input[:60].strip()
                        if len(user_input) > 60:
                            title += "..."
                        update_conversation_title(conversation_id, title, db)
                        new_conv_title = title
                else:
                    # Validate conversation ownership for existing conversation
                    validate_conversation_access(user_id, conversation_id, db)
                
                # Save user message
                user_message: Message = {
                    "conversation_id": conversation_id,
                    "role": "user",
                    "content": user_input,
                    "intent": None,
                    "metadata": {},
                }
                save_message(user_message, db)
                
                # Save assistant rejection message
                assistant_message: Message = {
                    "conversation_id": conversation_id,
                    "role": "assistant",
                    "content": result.answer or "I cannot assist with that request.",
                    "intent": "GENERAL",  # Use GENERAL intent (SYSTEM_EXPLOIT not allowed in DB)
                    "metadata": {"security_classification": "EXPLOIT"},  # Store in metadata instead
                }
                save_message(assistant_message, db)
                
                # Prepare response
                response_result = {
                    "intent": "SYSTEM_EXPLOIT",
                    "answer": result.answer or "I cannot assist with that request."
                }
                
                # Add conversation_id and title if new conversation was created
                if new_conv_id:
                    response_result["conversation_id"] = new_conv_id
                    response_result["title"] = new_conv_title
                
                # Return rejection response
                return StopEvent(result=response_result)
            
            # SAFE - Continue to business router
            return BusinessRouterEvent(
                user_input=user_input,
                conversation_id=conversation_id
            )
            
        except Exception as e:
            # On error, fail-safe: allow request to continue
            return BusinessRouterEvent(
                user_input=user_input,
                conversation_id=conversation_id
            )

    @step
    async def route_and_answer(self, ctx: Context, ev: BusinessRouterEvent) -> Union[StopEvent, "GenerateSlideEvent"]:

        # Get params from BusinessRouterEvent (passed from security_check)
        user_input = ev.user_input
        conversation_id = ev.conversation_id
        
        # Get db session from context (stored in security_check)
        db = await ctx.store.get("db")
        
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
            conversation_id = create_new_conversation(user_id, db)
            new_conv_id = conversation_id
            
            # Generate title from user input
            try:
                title = generate_conversation_title(user_input)
                update_conversation_title(conversation_id, title, db)
                new_conv_title = title
            except Exception as e:
                # Fallback: use truncated user input
                title = user_input[:60].strip()
                if len(user_input) > 60:
                    title += "..."
                update_conversation_title(conversation_id, title, db)
                new_conv_title = title
        else:
            # ✅ Validate conversation ownership (fail early before processing)
            validate_conversation_access(user_id, conversation_id, db)

        # Store user_id and conversation_id in context for later use
        await ctx.store.set("user_id", user_id)
        await ctx.store.set("conversation_id", conversation_id)

        openai_tools = [tool.metadata.to_openai_tool() for tool in tools]

        # Load chat history for this conversation
        chat_history = load_chat_history(conversation_id, db)

        # Memory
        memory = ChatMemoryBuffer.from_defaults(token_limit=2000)
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
        system_content = ROUTER_ANSWER_PROMPT + "\n\n"
        
        # Thêm tool instructions + best practices
        tool_instructions = registry.get_tool_instructions()
        if tool_instructions:
            system_content += tool_instructions + "\n\n"
        system_content += TOOL_BEST_PRACTICES + "\n\n"
        
        # Thêm user facts nếu có
        if user_facts_text:
            system_content += user_facts_text + "\n\n"
        
        # Format history vào System Prompt nếu có
        if history:
            history_text = "\n===== RECENT CHAT HISTORY =====\n"
            for msg in history:
                history_text += f"{msg.role.value}: {msg.content}\n"
            system_content += "\n\n" + history_text
        
        # Load và thêm chat summary nếu có (sau Chat History)
        summary_data = load_summary(conversation_id, db)
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
        user_message: Message = {
            "conversation_id": conversation_id,
            "role": "user",
            "content": user_input,
            "intent": None,
            "metadata": {},
        }
        saved_user_msg = save_message(user_message, db)
        user_msg_id = saved_user_msg["id"] if saved_user_msg else None
        
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

                # Execute tool via registry
                result = registry.execute_tool(name, **args)

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
            result = await save_error_response(
                conversation_id, db, error_output.answer, error_output.model_dump(),
                memory, ctx
            )
            return StopEvent(result=result)

        if output.intent == "GENERAL":
            # Save ASSISTANT message to DB first and get ID
            assistant_message: Message = {
                "conversation_id": conversation_id,
                "role": "assistant",
                "content": output.answer,
                "intent": output.intent,
                "metadata": {},
            }
            saved_assistant_msg = save_message(assistant_message, db)
            assistant_msg_id = saved_assistant_msg["id"] if saved_assistant_msg else None
            
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
            result = await save_error_response(
                conversation_id, db, error_output.answer, error_output.model_dump(),
                memory, ctx
            )
            return StopEvent(result=result)

    @step
    async def generate_slide(self, ctx: Context, ev: GenerateSlideEvent) -> StopEvent:
        """Slide generation step (merged from SlideWorkflow)."""
        conversation_id = await ctx.store.get("conversation_id")
        db = await ctx.store.get("db")  # Get db from context
        memory: ChatMemoryBuffer = await ctx.store.get("chat_history")
        history = memory.get() if memory else []

        try:
            action, target_presentation_id, target_page_number = await detect_presentation_intent(
                ev.user_input, conversation_id, llm, db
            )
        except Exception:
            result = await save_error_response(
                conversation_id, db, error_output.answer, error_output.model_dump(),
                memory, ctx
            )
            return StopEvent(result=result)

        previous_pages = None
        total_pages = None
        if target_presentation_id:
            presentation_data = load_presentation(target_presentation_id, db)
            if presentation_data:
                previous_pages = presentation_data["pages"]
                total_pages = presentation_data["total_pages"]

        system_content = SLIDE_GENERATION_PROMPT

        if history:
            history_text = "\n===== RECENT CHAT HISTORY =====\n"
            for msg in history:
                history_text += f"{msg.role.value}: {msg.content}\n"
            system_content += "\n\n" + history_text

        summary_data = load_summary(conversation_id, db)
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
                presentation: Presentation = {
                    "conversation_id": conversation_id,
                    "topic": slide_output.topic,
                    "total_pages": slide_output.total_pages,
                    "version": 1,
                }
                saved_presentation = create_presentation(
                    presentation=presentation,
                    pages=slide_output.pages,
                    user_request=ev.user_input,
                    db=db
                )
                if not saved_presentation:
                    raise ValueError("Failed to create presentation")
                presentation_id = saved_presentation["id"]
            else:
                if not target_presentation_id:
                    raise ValueError("target_presentation_id required for EDIT action")
                presentation: Presentation = {
                    "id": target_presentation_id,
                    "conversation_id": conversation_id,
                    "topic": slide_output.topic,
                    "total_pages": slide_output.total_pages,
                    "version": 1,  # Will be incremented in update_presentation
                }
                updated_presentation = update_presentation(
                    presentation=presentation,
                    pages=slide_output.pages,
                    user_request=ev.user_input,
                    db=db
                )
                if not updated_presentation:
                    raise ValueError("Failed to update presentation")
                presentation_id = updated_presentation["id"]
                set_active_presentation(conversation_id, presentation_id, db)
        except (ValueError, Exception):
            result = await save_error_response(
                conversation_id, db, error_output.answer, error_output.model_dump(),
                memory, ctx
            )
            return StopEvent(result=result)

        try:
            assistant_message: Message = {
                "conversation_id": conversation_id,
                "role": "assistant",
                "content": slide_output.answer,
                "intent": "PPTX",
                "metadata": {
                    "pages": [p.model_dump() for p in slide_output.pages],
                    "total_pages": slide_output.total_pages,
                    "topic": slide_output.topic,
                    "slide_id": presentation_id,
                },
            }
            saved_assistant_msg = save_message(assistant_message, db)
            assistant_msg_id = saved_assistant_msg["id"] if saved_assistant_msg else None
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
        result["slide_id"] = presentation_id
        if ev.new_conversation_id:
            result["conversation_id"] = ev.new_conversation_id
            result["title"] = ev.new_conversation_title

        return StopEvent(result=result)

