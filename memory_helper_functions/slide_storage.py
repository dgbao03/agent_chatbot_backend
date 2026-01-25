import json
from pathlib import Path
from typing import Optional, Tuple
from datetime import datetime
from config.settings import SLIDES_DIR, SLIDE_INDEX_FILE
from config.models import SlideIndex, SlideEntry, SlideData, SlideIntentOutput, SlideOutput
from llama_index.core.llms import ChatMessage, MessageRole
from llama_index.core.prompts import ChatPromptTemplate


def _load_slide_index() -> SlideIndex:
    """
    Load slide index từ file JSON.
    Trả về SlideIndex model với structure mặc định nếu file không tồn tại hoặc lỗi.
    """
    try:
        if not SLIDE_INDEX_FILE.exists():
            return SlideIndex()

        with open(SLIDE_INDEX_FILE, "r", encoding="utf-8") as f:
            content = f.read().strip()
            if not content:
                return SlideIndex()
            index_dict = json.loads(content)
            if not isinstance(index_dict, dict):
                return SlideIndex()
            # Validate và parse với Pydantic model
            return SlideIndex(**index_dict)
    except (json.JSONDecodeError, IOError, Exception) as e:
        print(f"Lỗi khi đọc slide_index.json: {e}")
        return SlideIndex()


def _save_slide_index(index: SlideIndex) -> bool:
    """
    Lưu slide index vào file JSON.
    Trả về True nếu thành công.
    """
    try:
        SLIDE_INDEX_FILE.parent.mkdir(parents=True, exist_ok=True)
        temp_file = SLIDE_INDEX_FILE.with_suffix(".tmp")
        # Convert Pydantic model to dict for JSON serialization
        index_dict = index.model_dump()
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(index_dict, f, ensure_ascii=False, indent=2)
        temp_file.replace(SLIDE_INDEX_FILE)
        return True
    except (IOError, Exception) as e:
        print(f"Lỗi khi ghi slide_index.json: {e}")
        return False


def _load_slide_file(file_name: str) -> Optional[SlideData]:
    """
    Load slide content từ file JSON.
    
    Args:
        file_name: Tên file (ví dụ: "slide_20260125_143022.json")
    
    Returns:
        SlideData model hoặc None nếu lỗi
    """
    try:
        file_path = SLIDES_DIR / file_name
        if not file_path.exists():
            print(f"⚠️ Slide file không tồn tại: {file_name}")
            return None

        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read().strip()
            if not content:
                return None
            slide_dict = json.loads(content)
            if not isinstance(slide_dict, dict):
                return None
            # Validate và parse với Pydantic model
            return SlideData(**slide_dict)
    except (json.JSONDecodeError, IOError, Exception) as e:
        print(f"Lỗi khi đọc slide file {file_name}: {e}")
        return None


def _save_slide_file(file_name: str, slide_data: SlideData) -> bool:
    """
    Lưu slide content vào file JSON.
    
    Args:
        file_name: Tên file (ví dụ: "slide_20260125_143022.json")
        slide_data: SlideData model
    
    Returns:
        True nếu thành công
    """
    try:
        SLIDES_DIR.mkdir(parents=True, exist_ok=True)
        file_path = SLIDES_DIR / file_name
        temp_file = file_path.with_suffix(".tmp")
        # Convert Pydantic model to dict for JSON serialization
        slide_dict = slide_data.model_dump()
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(slide_dict, f, ensure_ascii=False, indent=2)
        temp_file.replace(file_path)
        return True
    except (IOError, Exception) as e:
        print(f"Lỗi khi ghi slide file {file_name}: {e}")
        return False


def _build_slides_context(index: SlideIndex) -> str:
    """
    Format slide index thành text context để inject vào LLM prompt.
    
    Args:
        index: SlideIndex model
    
    Returns:
        Formatted string context
    """
    slides = index.slides
    active_id = index.active_slide_id
    
    if not slides:
        return "Chưa có slide nào trong conversation."
    
    context = "===== AVAILABLE SLIDES =====\n\n"
    
    for i, slide in enumerate(slides, 1):
        is_active = " (ACTIVE)" if slide.id == active_id else ""
        context += f"Slide {i}{is_active}:\n"
        context += f"  - ID: {slide.id}\n"
        context += f"  - Topic: {slide.topic}\n"
        context += "\n"
    
    if active_id:
        context += f"Currently active slide: {active_id}\n"
    context += f"Total slides: {len(slides)}\n"
    
    return context


def _generate_slide_id(index: SlideIndex) -> str:
    """
    Generate slide ID mới dựa trên next_id_counter.
    
    Args:
        index: SlideIndex model
    
    Returns:
        Slide ID string (ví dụ: "slide_001")
    """
    counter = index.next_id_counter
    slide_id = f"slide_{counter:03d}"
    return slide_id


def _generate_file_name() -> str:
    """
    Generate file name mới dựa trên timestamp.
    
    Returns:
        File name string (ví dụ: "slide_20260125_143022.json")
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_name = f"slide_{timestamp}.json"
    return file_name


async def _detect_intent(
    user_input: str,
    index: SlideIndex,
    llm
) -> Tuple[str, Optional[str]]:
    # Build slides context
    slides_context = _build_slides_context(index)
    
    # System prompt cho intent detection
    system_prompt = """You are a slide intent classifier for a presentation system.

    Your task is to analyze user input and determine:
    1. What action the user wants: CREATE_NEW, EDIT_SPECIFIC, or EDIT_ACTIVE
    2. Which slide to target (if editing)

    RULES:

    1. CREATE_NEW - When user wants to create a NEW slide:
    - Keywords: "tạo", "create", "make", "new slide"
    - Example: "Tạo slide về Java", "Create a slide about Docker"
    - target_slide_id: null

    2. EDIT_SPECIFIC - When user explicitly references a SPECIFIC slide:
    - By number: "slide 1", "slide 2", "slide đầu", "slide cuối"
    - By topic: "slide AI", "slide về Python", "slide Machine Learning"
    - Example: "Sửa slide 1", "Edit the AI slide", "Change color on first slide"
    - target_slide_id: the specific slide's ID from the available slides list

    3. EDIT_ACTIVE - When user wants to edit but doesn't specify which slide:
    - Has edit keywords but NO specific slide reference
    - Keywords: "sửa", "đổi", "edit", "change", "add", "remove", "thêm", "xóa"
    - Example: "Đổi màu nền", "Add a section", "Change font"
    - target_slide_id: the currently active slide's ID

    MATCHING LOGIC:
    - For "slide [number]": Match by the order (Slide 1, Slide 2, etc.)
    - For "slide [keyword]": Search in 'topic' field (case-insensitive, partial match OK)
    - For position words (đầu/first/cuối/last): Use first or last slide
    - If multiple matches: Choose the most relevant one
    - If no clear match: Use active slide or create new (based on keywords)

    Always provide clear reasoning for your classification."""
    
    # Build user message
    user_message = f"""
    ===== AVAILABLE SLIDES =====
    {slides_context}

    ===== USER REQUEST =====
    {user_input}

    ===== YOUR TASK =====
    Analyze the user request and classify:
    1. What action? (CREATE_NEW, EDIT_SPECIFIC, or EDIT_ACTIVE)
    2. Which slide? (if editing, provide the slide_id from the list above)
    """
    
    try:
        # Create prompt
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("user", user_message)
        ])
        
        # Call LLM with structured output
        result = await llm.astructured_predict(
            SlideIntentOutput,
            prompt
        )
        
        # Validate result
        if result.action in ["EDIT_SPECIFIC", "EDIT_ACTIVE"]:
            if not result.target_slide_id:
                # LLM forgot to provide target_slide_id, use active slide
                print("⚠️ LLM didn't provide target_slide_id, using active slide")
                result.target_slide_id = index.active_slide_id
        
        if result.action == "CREATE_NEW":
            if result.target_slide_id:
                # LLM incorrectly provided target_slide_id for CREATE
                print("⚠️ LLM provided target_slide_id for CREATE_NEW, ignoring")
                result.target_slide_id = None
        
        return (result.action, result.target_slide_id)
        
    except Exception as e:
        print(f"❌ LLM intent detection failed: {e}")
        raise ValueError(f"LLM intent detection failed: {e}") from e


def _save_slide_result(
    action: str,
    target_slide_id: Optional[str],
    slide_output: SlideOutput,
    user_input: str
) -> str:
    """
    Save slide result sau khi LLM generate/edit.
    
    Args:
        action: "CREATE_NEW" | "EDIT_SPECIFIC" | "EDIT_ACTIVE"
        target_slide_id: Slide ID cần edit (None nếu CREATE_NEW)
        slide_output: SlideOutput từ LLM
        user_input: User request string
    
    Returns:
        slide_id của slide đã lưu
    """
    # Load index
    index = _load_slide_index()
    now = datetime.now().isoformat()
    
    if action == "CREATE_NEW":
        # === CREATE NEW SLIDE ===
        
        # Generate IDs
        slide_id = _generate_slide_id(index)
        file_name = _generate_file_name()
        
        # Create slide data
        slide_data = SlideData(
            slide_id=slide_id,
            topic=slide_output.topic,
            html_content=slide_output.html_slide,
            created_at=now,
            last_modified=now,
            version=1,
            metadata={
                "user_request": user_input
            }
        )
        
        # Save slide file
        if not _save_slide_file(file_name, slide_data):
            raise IOError(f"Failed to save slide file: {file_name}")
        
        # Create slide entry
        slide_entry = SlideEntry(
            id=slide_id,
            file=file_name,
            topic=slide_output.topic
        )
        
        # Update index
        index.slides.append(slide_entry)
        index.active_slide_id = slide_id
        index.next_id_counter += 1
        
        # Save index
        if not _save_slide_index(index):
            raise IOError("Failed to save slide index")
        
        print(f"✅ Created new slide: {slide_id} ({slide_output.topic})")
        return slide_id
        
    else:
        # === EDIT EXISTING SLIDE ===
        
        if not target_slide_id:
            raise ValueError(f"target_slide_id is required for {action}")
        
        # Find slide in index
        slide_entry = None
        for slide in index.slides:
            if slide.id == target_slide_id:
                slide_entry = slide
                break
        
        if not slide_entry:
            raise ValueError(f"Slide {target_slide_id} not found in index")
        
        file_name = slide_entry.file
        
        # Load existing slide data
        existing_slide = _load_slide_file(file_name)
        if not existing_slide:
            raise ValueError(f"Slide file not found: {file_name}")
        
        # Update slide data
        updated_slide = SlideData(
            slide_id=existing_slide.slide_id,
            topic=slide_output.topic,  # Update topic từ LLM output
            html_content=slide_output.html_slide,
            created_at=existing_slide.created_at,
            last_modified=now,
            version=existing_slide.version + 1,
            metadata={
                **existing_slide.metadata,
                "last_user_request": user_input
            }
        )
        
        # Save (overwrite)
        if not _save_slide_file(file_name, updated_slide):
            raise IOError(f"Failed to save slide file: {file_name}")
        
        # Update index metadata
        # Update topic trong index entry
        for slide in index.slides:
            if slide.id == target_slide_id:
                slide.topic = slide_output.topic
                break
        
        # Set as active if EDIT_SPECIFIC
        if action == "EDIT_SPECIFIC":
            index.active_slide_id = target_slide_id
        
        # Save index
        if not _save_slide_index(index):
            raise IOError("Failed to save slide index")
        
        print(f"✅ Updated slide: {target_slide_id} (v{existing_slide.version} → v{updated_slide.version})")
        return target_slide_id 
