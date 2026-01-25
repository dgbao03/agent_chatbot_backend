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

