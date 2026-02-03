"""
Slide workflow - Handles slide generation and editing.
"""
from llama_index.llms.openai import OpenAI
from llama_index.core.workflow import Context, step
from llama_index.core.workflow.events import StopEvent
from llama_index.core.llms import ChatMessage, MessageRole
from llama_index.core.prompts import ChatPromptTemplate
from llama_index.core.memory import ChatMemoryBuffer

from app.config.models import SlideOutput, RouterOutput
from app.config.constants import (
    ROLE_ASSISTANT,
    INTENT_PPTX,
    INTENT_GENERAL,
    FIELD_SUMMARY_CONTENT,
    METADATA_KEY_PAGES,
    METADATA_KEY_TOTAL_PAGES,
    METADATA_KEY_TOPIC,
    METADATA_KEY_SLIDE_ID
)
from app.services.presentation_service import detect_presentation_intent
from app.repositories.presentation_repository import (
    load_presentation,
    create_presentation,
    update_presentation,
    set_active_presentation
)
from app.repositories.chat_repository import save_message
from app.repositories.summary_repository import load_summary
from app.workflows.memory_manager import process_memory_truncation
# Import GenerateSlideEvent after it's defined in router_workflow to avoid circular import
from app.workflows.router_workflow import GenerateSlideEvent

error_output = RouterOutput(
    intent=INTENT_GENERAL,
    answer="Sorry, I encountered an error processing your request. Please try again."
)

llm = OpenAI(model="gpt-4o-mini", request_timeout=300.0)  # 5 minutes timeout cho generate multi-page slides


class SlideWorkflow:
    """Slide generation workflow - can be used as a mixin or standalone."""

    @step
    async def generate_slide(self, ctx: Context, ev: GenerateSlideEvent) -> StopEvent:
        # Lấy conversation_id từ context
        conversation_id = await ctx.store.get("conversation_id")
        
        # Lấy memory từ context
        memory: ChatMemoryBuffer = await ctx.store.get("chat_history")
        history = memory.get() if memory else []
        
        # Detect intent (now uses Supabase)
        try:
            action, target_presentation_id, target_page_number = await detect_presentation_intent(ev.user_input, conversation_id, llm)
        except Exception as e:
            print(f"❌ Intent detection error: {e}")
            return StopEvent(result=error_output.model_dump())
        print(f"Slide Output:\naction: {action}, target_presentation_id: {target_presentation_id}, target_page_number: {target_page_number}")
        
        # Load previous presentation data nếu EDIT
        previous_pages = None
        total_pages = None
        if target_presentation_id:
            presentation_data = load_presentation(target_presentation_id)
            if presentation_data:
                previous_pages = presentation_data.get('pages')
                total_pages = presentation_data.get('total_pages')
        
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
        summary_data = load_summary(conversation_id)
        if summary_data.get(FIELD_SUMMARY_CONTENT):
            summary_text = f"\n===== CONVERSATION SUMMARY =====\n{summary_data[FIELD_SUMMARY_CONTENT]}"
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
                presentation_id = create_presentation(
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
                
                new_version = update_presentation(
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
                set_active_presentation(conversation_id, presentation_id)
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
            assistant_msg_id = save_message(
                conversation_id=conversation_id,
                role=ROLE_ASSISTANT,
                content=slide_output.answer,
                intent=INTENT_PPTX,
                metadata={
                    METADATA_KEY_PAGES: [p.model_dump() for p in slide_output.pages],
                    METADATA_KEY_TOTAL_PAGES: slide_output.total_pages,
                    METADATA_KEY_TOPIC: slide_output.topic,
                    METADATA_KEY_SLIDE_ID: presentation_id
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
        await process_memory_truncation(ctx, memory)

        print(messages)
        
        # Prepare result
        result = slide_output.model_dump()
        
        # Add conversation_id and title if new conversation was created
        # Get from event (passed from router_workflow)
        new_conv_id = ev.get("new_conversation_id")
        new_conv_title = ev.get("new_conversation_title")
        if new_conv_id:
            result["conversation_id"] = new_conv_id
            result["title"] = new_conv_title
            print(f"📤 Returning new conversation_id: {new_conv_id}, title: {new_conv_title}")
            
        return StopEvent(result=result)

