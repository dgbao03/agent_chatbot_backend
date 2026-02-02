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
    target_page_number: Optional[int] = Field(
        default=None,
        description="Số thứ tự trang slide cần sửa (ví dụ: 1, 2, 3). Chỉ có giá trị khi user muốn sửa 1 trang cụ thể (ví dụ: 'sửa trang 2'). Nếu null = sửa toàn bộ presentation."
    )
