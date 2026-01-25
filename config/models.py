from pydantic import BaseModel, Field
from typing import Literal, Optional

class RouterOutput(BaseModel):
    intent: Literal["PPTX", "GENERAL"] = Field(
        description="Loại intent của người dùng: PPTX nếu muốn tạo slide/presentation, GENERAL cho các câu hỏi thông thường"
    )
    answer: Optional[str] = Field(
        default=None,
        description="Câu trả lời cho câu hỏi của người dùng. Chỉ có giá trị khi intent là GENERAL, phải là null khi intent là PPTX"
    )


class SlideOutput(BaseModel):
    intent: Literal["PPTX"] = Field(
        default="PPTX",
        description="Intent luôn luôn là PPTX cho slide generation output. Đây là identifier để frontend biết đây là response từ slide generation workflow."
    )
    answer: str = Field(
        description="Câu trả lời thông báo cho người dùng về kết quả tạo slide. Ví dụ: 'Tôi đã tạo slide thành công về chủ đề Machine Learning', 'Slide đã được tạo với nội dung về lịch sử Việt Nam', etc. Câu trả lời phải ngắn gọn, rõ ràng và thân thiện với người dùng."
    )
    html_slide: str = Field(
        description="Nội dung HTML đầy đủ của slide presentation. Đây là HTML document hoàn chỉnh có thể render trực tiếp trong browser."
    )
    topic: str = Field(
        description="Chủ đề chính/Tiêu đề của slide, ngắn gọn và rõ ràng. Ví dụ: 'Artificial Intelligence Basics', 'Machine Learning Deep Dive', 'Sự khác biệt giữa Hà Nội và TP.HCM, ...'"
    )


class SlideIntentOutput(BaseModel):
    action: Literal["CREATE_NEW", "EDIT_SPECIFIC", "EDIT_ACTIVE"] = Field(
        description="Hành động của người dùng: CREATE_NEW nếu muốn tạo slide mới, EDIT_SPECIFIC nếu muốn sửa slide cụ thể (có chỉ rõ slide nào), EDIT_ACTIVE nếu muốn sửa slide hiện tại (không chỉ rõ slide nào)."
    )
    target_slide_id: Optional[str] = Field(
        default=None,
        description="ID của slide cần sửa (ví dụ: 'slide_001', 'slide_002'). Chỉ có giá trị khi action là EDIT_SPECIFIC hoặc EDIT_ACTIVE. Phải là null khi action là CREATE_NEW."
    )


class SlideEntry(BaseModel):
    """Model cho mỗi entry trong slides array của slide_index.json"""
    id: str = Field(description="Slide ID (ví dụ: 'slide_001')")
    file: str = Field(description="Tên file chứa slide content (ví dụ: 'slide_20260125_143022.json')")
    topic: str = Field(description="Chủ đề của slide")


class SlideIndex(BaseModel):
    """Model cho slide_index.json structure"""
    slides: list[SlideEntry] = Field(default_factory=list, description="Danh sách các slides")
    active_slide_id: Optional[str] = Field(default=None, description="ID của slide đang active")
    next_id_counter: int = Field(default=1, description="Counter để generate slide ID tiếp theo")


class SlideData(BaseModel):
    """Model cho slide_XXXXXX.json structure"""
    slide_id: str = Field(description="Slide ID (ví dụ: 'slide_001')")
    topic: str = Field(description="Chủ đề của slide")
    html_content: str = Field(description="Nội dung HTML đầy đủ của slide")
    created_at: str = Field(description="Timestamp tạo slide (ISO format)")
    last_modified: str = Field(description="Timestamp sửa lần cuối (ISO format)")
    version: int = Field(description="Version number, tăng mỗi lần edit")
    metadata: dict = Field(default_factory=dict, description="Metadata bổ sung (user_request, etc.)")
