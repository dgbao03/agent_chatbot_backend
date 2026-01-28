from pydantic import BaseModel, Field
from typing import Literal, Optional, List

class RouterOutput(BaseModel):
    intent: Literal["PPTX", "GENERAL"] = Field(
        description="Loại intent của người dùng: PPTX nếu muốn tạo slide/presentation, GENERAL cho các câu hỏi thông thường"
    )
    answer: Optional[str] = Field(
        default=None,
        description="Câu trả lời cho câu hỏi của người dùng. Chỉ có giá trị khi intent là GENERAL, phải là null khi intent là PPTX"
    )


class PageContent(BaseModel):
    """Model cho nội dung của một trang slide (dùng cho cả LLM output và storage)"""
    page_number: int = Field(description="Số thứ tự của trang slide (bắt đầu từ 1)")
    html_content: str = Field(description="Nội dung HTML đầy đủ của trang slide này. HTML document hoàn chỉnh với tỷ lệ 1280x720.")
    page_title: Optional[str] = Field(default=None, description="Tiêu đề của trang slide này (ví dụ: 'Introduction', 'Main Content', 'Conclusion')")


class SlideOutput(BaseModel):
    intent: Literal["PPTX"] = Field(
        default="PPTX",
        description="Intent luôn luôn là PPTX cho slide generation output. Đây là identifier để frontend biết đây là response từ slide generation workflow."
    )
    answer: str = Field(
        description="Câu trả lời thông báo cho người dùng về kết quả tạo slide. Ví dụ: 'Tôi đã tạo slide thành công về chủ đề Machine Learning', 'Slide đã được tạo với nội dung về lịch sử Việt Nam', etc. Câu trả lời phải ngắn gọn, rõ ràng và thân thiện với người dùng."
    )
    topic: str = Field(
        description="Chủ đề chính/Tiêu đề của slide, ngắn gọn và rõ ràng. Ví dụ: 'Artificial Intelligence Basics', 'Machine Learning Deep Dive', 'Sự khác biệt giữa Hà Nội và TP.HCM, ...'"
    )
    pages: List[PageContent] = Field(
        description="Danh sách các trang slide. Mỗi presentation nên có 3-7 trang với cấu trúc: trang đầu (giới thiệu), các trang giữa (nội dung chính), trang cuối (kết luận)."
    )
    total_pages: int = Field(
        description="Tổng số trang slide trong presentation này."
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


class VersionEntry(BaseModel):
    """Model cho mỗi version entry trong version_history"""
    version: int = Field(description="Version number")
    pages: List[PageContent] = Field(description="Nội dung các trang slide của version này")
    total_pages: int = Field(description="Tổng số trang của version này")
    timestamp: str = Field(description="Timestamp của version này (ISO format)")
    user_request: str = Field(description="User request dẫn đến version này")


class SlideData(BaseModel):
    """Model cho slide_XXXXXX.json structure"""
    slide_id: str = Field(description="Slide ID (ví dụ: 'slide_001')")
    topic: str = Field(description="Chủ đề của slide")
    pages: List[PageContent] = Field(description="Nội dung các trang slide (current version)")
    total_pages: int = Field(description="Tổng số trang slide trong presentation này")
    created_at: str = Field(description="Timestamp tạo slide (ISO format)")
    last_modified: str = Field(description="Timestamp sửa lần cuối (ISO format)")
    version: int = Field(description="Version number hiện tại, tăng mỗi lần edit")
    metadata: dict = Field(default_factory=dict, description="Metadata bổ sung (user_request, etc.)")
    version_history: List[VersionEntry] = Field(
        default_factory=list,
        description="Lịch sử các version trước đó. Version hiện tại nằm ở pages, không nằm trong history."
    )
