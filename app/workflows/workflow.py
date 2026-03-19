"""
Chat workflow - Main workflow for routing and answering user queries.
"""
import json
import time
from typing import Union, Optional
from llama_index.core.workflow import Workflow, Context, step
from llama_index.core.workflow.events import StartEvent, StopEvent
from llama_index.core.llms import ChatMessage, MessageRole
from llama_index.core.memory import ChatMemoryBuffer
from llama_index.core.workflow.events import Event

from app.types.llm.outputs import RouterOutput, SlideOutput, SecurityOutput
from app.types.internal.presentation import Presentation
from app.config.prompts import SECURITY_CHECK_PROMPT, ERROR_GENERAL
from app.services.message_service import save_error_response
from app.tools import registry
from app.exceptions import AccessDeniedError, ValidationError, DatabaseError
from app.auth.context import get_current_user_id, get_current_db_session
from app.services.conversation_service import get_or_create_conversation
from app.services.presentation_service import (
    detect_presentation_intent,
    get_presentation,
    save_new_presentation,
    save_updated_presentation,
    activate_presentation,
)
from app.services import memory_service, context_service, message_service
from app.workflows.memory_manager import process_memory_truncation
from app.config.llm import get_llm, get_security_llm
from app.config.settings import LLM_MODEL, LLM_SECURITY_MODEL
from app.logging import get_logger

logger = get_logger(__name__)

llm = get_llm()
llm_security = get_security_llm()


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
    answer=ERROR_GENERAL,
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
        step_start = time.perf_counter()
        user_input = ev.get("user_input")
        conversation_id = ev.get("conversation_id")

        logger.info("security_check_started", conversation_id=conversation_id)

        # Get db session from ContextVar (set by workflow router)
        db = get_current_db_session()

        # Store db in context for other steps
        await ctx.store.set("db", db)

        system_prompt = SECURITY_CHECK_PROMPT

        try:
            # Call LLM for security classification
            llm_start = time.perf_counter()
            security_messages = [
                ChatMessage(role=MessageRole.SYSTEM, content=system_prompt),
                ChatMessage(role=MessageRole.USER, content=user_input),
            ]
            resp = await llm_security.achat(security_messages, response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "SecurityOutput",
                    "schema": SecurityOutput.model_json_schema(),
                },
            })
            result = SecurityOutput.model_validate_json(resp.message.content)
            llm_duration = round((time.perf_counter() - llm_start) * 1000)

            token_info = {}
            raw_resp = getattr(resp, "raw", None)
            if raw_resp and hasattr(raw_resp, "usage") and raw_resp.usage:
                token_info = {
                    "prompt_tokens": raw_resp.usage.prompt_tokens,
                    "completion_tokens": raw_resp.usage.completion_tokens,
                    "total_tokens": raw_resp.usage.total_tokens,
                }

            logger.info(
                "security_check_llm_call",
                model=LLM_SECURITY_MODEL,
                duration_ms=llm_duration,
                **token_info,
            )

            if result.classification == "EXPLOIT":
                logger.info(
                    "security_check_completed",
                    classification="EXPLOIT",
                    duration_ms=round((time.perf_counter() - step_start) * 1000),
                )

                user_id = get_current_user_id()

                if not user_id:
                    raise AccessDeniedError("user_id is missing or invalid. Authentication failed.")

                # Conversation management (create new or validate existing)
                conversation_id, new_conv_id, new_conv_title = get_or_create_conversation(
                    user_id, conversation_id, user_input, db
                )

                # Persist user + rejection messages
                message_service.save_user_message(conversation_id, user_input, db)
                message_service.save_assistant_message(
                    conversation_id,
                    result.answer or "I cannot assist with that request.",
                    "GENERAL",  # DB does not allow SYSTEM_EXPLOIT; store in metadata
                    {"security_classification": "EXPLOIT"},
                    db,
                )

                response_result = {
                    "intent": "SYSTEM_EXPLOIT",
                    "answer": result.answer or "I cannot assist with that request.",
                }

                if new_conv_id:
                    response_result["conversation_id"] = new_conv_id
                    response_result["title"] = new_conv_title

                return StopEvent(result=response_result)

            # SAFE — continue to business router
            logger.info(
                "security_check_completed",
                classification="SAFE",
                duration_ms=round((time.perf_counter() - step_start) * 1000),
            )
            return BusinessRouterEvent(
                user_input=user_input,
                conversation_id=conversation_id
            )

        except Exception as e:
            logger.error(
                "security_check_failed",
                error_type=type(e).__name__,
                error_message=str(e),
                duration_ms=round((time.perf_counter() - step_start) * 1000),
            )
            # On error, fail-safe: allow request to continue
            return BusinessRouterEvent(
                user_input=user_input,
                conversation_id=conversation_id
            )

    @step
    async def route_and_answer(self, ctx: Context, ev: BusinessRouterEvent) -> Union[StopEvent, "GenerateSlideEvent"]:

        step_start = time.perf_counter()

        user_input = ev.user_input
        conversation_id = ev.conversation_id

        db = await ctx.store.get("db")
        user_id = get_current_user_id()

        if not user_id:
            raise AccessDeniedError("user_id is missing or invalid. Authentication failed.")

        # 1. Conversation management
        conversation_id, new_conv_id, new_conv_title = get_or_create_conversation(
            user_id, conversation_id, user_input, db
        )

        await ctx.store.set("user_id", user_id)
        await ctx.store.set("conversation_id", conversation_id)

        openai_tools = [tool.metadata.to_openai_tool() for tool in tools]

        # 2. Memory management
        memory = memory_service.load_conversation_memory(conversation_id, user_id, db)
        await ctx.store.set("chat_history", memory)
        history = memory.get()

        # 3. Context assembly
        system_content = context_service.build_chat_context(user_id, conversation_id, history, db)

        messages = [
            ChatMessage(role=MessageRole.SYSTEM, content=system_content)
        ]
        messages.append(ChatMessage(role=MessageRole.USER, content=user_input))

        # 4. Save user message
        user_msg_id = message_service.save_user_message(conversation_id, user_input, db)
        logger.debug("message_saved", conversation_id=conversation_id, role="user")

        memory.put(ChatMessage(
            role=MessageRole.USER,
            content=user_input,
            additional_kwargs={"message_id": user_msg_id}
        ))

        # 5. LLM orchestration — tool calling loop
        llm_call_count = 0
        tool_call_count = 0

        while True:
            llm_call_count += 1
            llm_start = time.perf_counter()

            try:
                resp = await llm.achat(messages, tools=openai_tools)
            except Exception as e:
                logger.error(
                    "llm_call_failed",
                    model=LLM_MODEL,
                    llm_call_number=llm_call_count,
                    error_type=type(e).__name__,
                    error_message=str(e),
                )
                result = await save_error_response(
                    conversation_id, db, error_output.answer, error_output.model_dump(),
                    memory, ctx
                )
                return StopEvent(result=result)

            llm_duration = round((time.perf_counter() - llm_start) * 1000)

            token_info = {}
            raw_resp = getattr(resp, "raw", None)
            if raw_resp and hasattr(raw_resp, "usage") and raw_resp.usage:
                token_info = {
                    "prompt_tokens": raw_resp.usage.prompt_tokens,
                    "completion_tokens": raw_resp.usage.completion_tokens,
                    "total_tokens": raw_resp.usage.total_tokens,
                }

            logger.info(
                "llm_call_completed",
                model=LLM_MODEL,
                llm_call_number=llm_call_count,
                duration_ms=llm_duration,
                **token_info,
            )

            # Append assistant message (with tool_calls OR final text)
            messages.append(resp.message)

            tool_calls = resp.message.additional_kwargs.get("tool_calls")
            if not tool_calls:
                break  # Final JSON response expected

            # Execute all tool calls returned in this turn
            for call in tool_calls:
                tool_call_count += 1
                name = call.function.name
                args_str = call.function.arguments

                if isinstance(args_str, str):
                    args = json.loads(args_str)
                else:
                    args = args_str

                logger.info("tool_call_started", tool_name=name, tool_args=args)

                tool_start = time.perf_counter()
                try:
                    tool_result = registry.execute_tool(name, **args)
                    tool_duration = round((time.perf_counter() - tool_start) * 1000)
                    logger.info("tool_call_completed", tool_name=name, success=True, duration_ms=tool_duration)
                except Exception as e:
                    tool_duration = round((time.perf_counter() - tool_start) * 1000)
                    logger.error(
                        "tool_call_failed",
                        tool_name=name,
                        error_type=type(e).__name__,
                        error_message=str(e),
                        duration_ms=tool_duration,
                    )
                    tool_result = f"Error executing tool {name}: {str(e)}"

                messages.append(ChatMessage(
                    role=MessageRole.TOOL,
                    content=tool_result,
                    additional_kwargs={"tool_call_id": call.id}
                ))

        raw_text = resp.message.content.strip()

        try:
            output = RouterOutput.model_validate_json(raw_text)
        except Exception as e:
            logger.warning(
                "llm_invalid_json",
                error_type=type(e).__name__,
                raw_output_length=len(raw_text),
            )
            result = await save_error_response(
                conversation_id, db, error_output.answer, error_output.model_dump(),
                memory, ctx
            )
            return StopEvent(result=result)

        logger.info(
            "intent_detected",
            intent=output.intent,
            conversation_id=conversation_id,
            llm_calls=llm_call_count,
            tool_calls=tool_call_count,
            duration_ms=round((time.perf_counter() - step_start) * 1000),
        )

        # 6. Save assistant message and update memory (GENERAL intent only)
        if output.intent == "GENERAL":
            assistant_msg_id = message_service.save_assistant_message(
                conversation_id, output.answer, output.intent, {}, db
            )
            logger.debug("message_saved", conversation_id=conversation_id, role="assistant", intent="GENERAL")

            memory.put(ChatMessage(
                role=MessageRole.ASSISTANT,
                content=output.answer,
                additional_kwargs={"message_id": assistant_msg_id}
            ))

        await ctx.store.set("chat_history", memory)

        if output.intent == "GENERAL":
            await process_memory_truncation(ctx, memory)

        result = output.model_dump()

        if new_conv_id:
            result["conversation_id"] = new_conv_id
            result["title"] = new_conv_title

        if output.intent == "GENERAL":
            return StopEvent(result=result)
        elif output.intent == "PPTX":
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
        """Slide generation step."""
        step_start = time.perf_counter()
        conversation_id = await ctx.store.get("conversation_id")
        user_id = await ctx.store.get("user_id")
        db = await ctx.store.get("db")
        memory: ChatMemoryBuffer = await ctx.store.get("chat_history")
        history = memory.get() if memory else []

        logger.info("slide_generation_started", conversation_id=conversation_id)

        try:
            intent_start = time.perf_counter()
            action, target_presentation_id, target_page_number = await detect_presentation_intent(
                ev.user_input, conversation_id, user_id, llm, db
            )
            logger.info(
                "presentation_intent_detected",
                action=action,
                target_presentation_id=target_presentation_id,
                target_page_number=target_page_number,
                duration_ms=round((time.perf_counter() - intent_start) * 1000),
            )
        except Exception as e:
            logger.error(
                "slide_generation_failed",
                phase="intent_detection",
                error_type=type(e).__name__,
                error_message=str(e),
                duration_ms=round((time.perf_counter() - step_start) * 1000),
            )
            result = await save_error_response(
                conversation_id, db, error_output.answer, error_output.model_dump(),
                memory, ctx
            )
            return StopEvent(result=result)

        previous_pages = None
        total_pages = None
        if target_presentation_id:
            presentation_data = get_presentation(target_presentation_id, user_id, db)
            if presentation_data:
                previous_pages = presentation_data["pages"]
                total_pages = presentation_data["total_pages"]

        # Context assembly for slide generation
        system_content, target_page_number = context_service.build_slide_context(
            conversation_id, user_id, history, action, previous_pages, total_pages, target_page_number, db
        )

        slide_messages = [
            ChatMessage(role=MessageRole.SYSTEM, content=system_content),
            ChatMessage(role=MessageRole.USER, content=f"User Request: {ev.user_input}"),
        ]

        llm_start = time.perf_counter()
        try:
            resp = await llm.achat(slide_messages, response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "SlideOutput",
                    "schema": SlideOutput.model_json_schema(),
                },
            })
            slide_output = SlideOutput.model_validate_json(resp.message.content)
        except Exception as e:
            logger.error(
                "slide_generation_failed",
                phase="llm_call",
                error_type=type(e).__name__,
                error_message=str(e),
                duration_ms=round((time.perf_counter() - step_start) * 1000),
            )
            result = await save_error_response(
                conversation_id, db, error_output.answer, error_output.model_dump(),
                memory, ctx
            )
            return StopEvent(result=result)

        llm_duration = round((time.perf_counter() - llm_start) * 1000)

        token_info = {}
        raw_resp = getattr(resp, "raw", None)
        if raw_resp and hasattr(raw_resp, "usage") and raw_resp.usage:
            token_info = {
                "prompt_tokens": raw_resp.usage.prompt_tokens,
                "completion_tokens": raw_resp.usage.completion_tokens,
                "total_tokens": raw_resp.usage.total_tokens,
            }

        logger.info(
            "slide_llm_call_completed",
            model=LLM_MODEL,
            duration_ms=llm_duration,
            total_pages=slide_output.total_pages,
            **token_info,
        )

        # Page merging: if editing a single page, merge it back into the full deck
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
                saved_presentation = save_new_presentation(
                    presentation=presentation,
                    pages=slide_output.pages,
                    user_request=ev.user_input,
                    user_id=user_id,
                    db=db,
                )
                presentation_id = saved_presentation["id"]
                logger.info(
                    "presentation_created",
                    presentation_id=presentation_id,
                    topic=slide_output.topic,
                    total_pages=slide_output.total_pages,
                )
            else:
                if not target_presentation_id:
                    raise ValidationError("target_presentation_id required for EDIT action")
                presentation: Presentation = {
                    "id": target_presentation_id,
                    "conversation_id": conversation_id,
                    "topic": slide_output.topic,
                    "total_pages": slide_output.total_pages,
                    "version": 1,
                }
                updated_presentation = save_updated_presentation(
                    presentation=presentation,
                    pages=slide_output.pages,
                    user_request=ev.user_input,
                    user_id=user_id,
                    db=db,
                )
                presentation_id = updated_presentation["id"]
                activate_presentation(conversation_id, presentation_id, user_id, db)
                logger.info(
                    "presentation_updated",
                    presentation_id=presentation_id,
                    topic=slide_output.topic,
                    total_pages=slide_output.total_pages,
                )
        except Exception as e:
            logger.error(
                "slide_generation_failed",
                phase="save_presentation",
                error_type=type(e).__name__,
                error_message=str(e),
                duration_ms=round((time.perf_counter() - step_start) * 1000),
            )
            result = await save_error_response(
                conversation_id, db, error_output.answer, error_output.model_dump(),
                memory, ctx
            )
            return StopEvent(result=result)

        # Save assistant message
        try:
            assistant_msg_id = message_service.save_assistant_message(
                conversation_id,
                slide_output.answer,
                "PPTX",
                {
                    "pages": [p.model_dump() for p in slide_output.pages],
                    "total_pages": slide_output.total_pages,
                    "topic": slide_output.topic,
                    "slide_id": presentation_id,
                },
                db,
            )
        except Exception:
            assistant_msg_id = None

        if memory:
            memory.put(ChatMessage(
                role=MessageRole.ASSISTANT,
                content=slide_output.answer,
                additional_kwargs={"message_id": assistant_msg_id},
            ))
        await ctx.store.set("chat_history", memory)
        await process_memory_truncation(ctx, memory)

        logger.info(
            "slide_generation_completed",
            action=action,
            presentation_id=presentation_id,
            total_pages=slide_output.total_pages,
            duration_ms=round((time.perf_counter() - step_start) * 1000),
        )

        result = slide_output.model_dump()
        result["slide_id"] = presentation_id
        if ev.new_conversation_id:
            result["conversation_id"] = ev.new_conversation_id
            result["title"] = ev.new_conversation_title

        return StopEvent(result=result)
