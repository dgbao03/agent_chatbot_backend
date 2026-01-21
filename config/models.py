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

